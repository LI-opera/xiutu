"""Offline migration and persistent metering checks; never touch LIVE_LEDGER."""

import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from app.infrastructure.model_budget import METERED_POLICY, BudgetError, BudgetLedger


def test_v1_migration_preserves_bytes_and_all_historical_call_data(tmp_path):
    path = tmp_path / "ledger.json"
    prior = {
        "version": 1,
        "authorization": "historical five yuan approval",
        "limit_cny": "5",
        "reserved_cny": "2.329216",
        "calls": {
            "old:1": {"status": "received", "usage": {"input_tokens": 9},
                      "usage_status": "reported", "reserved_cny": "0.2"},
            "old:2": {"status": "failed", "error_code": "PROVIDER_HTTP_503",
                      "usage": None, "usage_status": "unknown", "reserved_cny": "0.1"},
        },
    }
    raw = json.dumps(prior, ensure_ascii=False).encode()
    path.write_bytes(raw)
    ledger = BudgetLedger(path)
    with pytest.raises(BudgetError, match="BUDGET_POLICY_MIGRATION_REQUIRED"):
        ledger.reserve("new:1", "deepseek-flash", "safe", 768)
    backup = ledger.migrate_to_metered()
    assert backup is not None and backup.parent == tmp_path and backup.read_bytes() == raw
    current = ledger.read()
    assert current["version"] == 2 and current["policy"] == METERED_POLICY
    assert current["historical_limit_cny"] == "5"
    for key in ("authorization", "reserved_cny", "calls"):
        assert current[key] == prior[key]
    assert ledger.migrate_to_metered() is None
    assert len(list(tmp_path.glob("ledger.json.v1-backup-*.json"))) == 1


def test_cross_process_reserve_restart_duplicate_and_no_cumulative_rejection(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = BudgetLedger(path)
    ledger.initialize("offline synthetic")
    state = ledger.read()
    state["reserved_cny"] = "4.99"
    ledger.save(state)
    backend = str(Path(__file__).resolve().parents[2] / "backend")
    code = ("import sys; from app.infrastructure.model_budget import BudgetLedger; "
            "BudgetLedger(sys.argv[1]).reserve(sys.argv[2], 'deepseek-flash', 'safe', 768)")
    env = dict(os.environ, PYTHONPATH=backend)
    procs = [subprocess.Popen([sys.executable, "-B", "-c", code, str(path), f"t:{i}"],
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
             for i in range(2)]
    for proc in procs:
        stdout, stderr = proc.communicate(timeout=15)
        assert proc.returncode == 0, (stdout, stderr)
    reopened = BudgetLedger(path).read()
    assert set(reopened["calls"]) == {"t:0", "t:1"}
    expected = Decimal("4.99") + sum(
        Decimal(row["reserved_cny"]) for row in reopened["calls"].values()
    )
    assert Decimal(reopened["reserved_cny"]) == expected > 5
    with pytest.raises(BudgetError, match="MODEL_CALL_ALREADY_RESERVED"):
        ledger.reserve("t:0", "deepseek-flash", "safe", 768)
    with pytest.raises(BudgetError, match="MODEL_PRICE_UNVERIFIED"):
        ledger.reserve("unknown", "unpriced-model", "safe", 768)


def test_migration_write_failure_retains_original_and_rollback_bytes(tmp_path, monkeypatch):
    path = tmp_path / "ledger.json"
    raw = b'{"version":1,"authorization":"old","limit_cny":"5","reserved_cny":"0","calls":{}}'
    path.write_bytes(raw)
    ledger = BudgetLedger(path)

    def fail_save(_):
        raise OSError("synthetic write failure")

    monkeypatch.setattr(ledger, "save", fail_save)
    with pytest.raises(OSError, match="synthetic write failure"):
        ledger.migrate_to_metered()
    assert path.read_bytes() == raw
    backups = list(tmp_path.glob("ledger.json.v1-backup-*.json"))
    assert len(backups) == 1 and backups[0].read_bytes() == raw


def test_usage_unknown_and_over_upper_are_recorded_without_rewriting_total(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    ledger.initialize("offline synthetic")
    ledger.reserve("unknown", "deepseek-flash", "safe", 768)
    ledger.finish("unknown", {"status": "failed", "usage": None, "error_code": "PROVIDER_TIMEOUT"})
    ledger.reserve("anomaly", "deepseek-flash", "safe", 768)
    before = ledger.read()["reserved_cny"]
    ledger.finish("anomaly", {"status": "received", "usage": {
        "input_tokens": 999999, "output_tokens": 769}})
    after = ledger.read()
    assert after["reserved_cny"] == before
    assert after["calls"]["unknown"]["usage_status"] == "unknown"
    assert after["calls"]["anomaly"]["budget_anomaly"] is True
    assert after["calls"]["anomaly"]["usage_status"] == "reported"
    assert Decimal(after["calls"]["anomaly"]["peak_cost_upper_cny"]) > 0


def test_large_input_is_accepted_only_for_matched_area_profile(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    ledger.initialize("offline synthetic")
    payload = "资料" * 40000
    with pytest.raises(BudgetError, match="MODEL_INPUT_LIMIT"):
        ledger.reserve("default", "deepseek-flash", payload, 8192)
    ledger.reserve("matched", "deepseek-flash", payload, 8192,
                   input_profile="matched_areas")
    state = ledger.read()
    assert set(state["calls"]) == {"matched"}
    assert state["calls"]["matched"]["input_profile"] == "matched_areas"
    assert state["calls"]["matched"]["input_upper"] == len(payload.encode("utf8")) * 4 + 8192


@pytest.mark.parametrize("content", ["{broken", "[]", '{"version":2,"policy":"wrong","reserved_cny":"0","calls":{},"authorization":"x"}',
                                     '{"version":2,"policy":"metered_no_cumulative_cap","reserved_cny":"NaN","calls":{},"authorization":"x"}'])
def test_corrupt_or_unknown_policy_fails_closed(tmp_path, content):
    path = tmp_path / "ledger.json"
    path.write_text(content)
    with pytest.raises(BudgetError, match="BUDGET_LEDGER_INVALID"):
        BudgetLedger(path).read()
