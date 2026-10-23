"""Offline SDK wire and real cross-process reservation regression tests."""
import copy
import json
import subprocess
import sys
import time
from decimal import Decimal

import pytest
from app.infrastructure.model_gateway import ModelError
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from test_model_gateway_contracts import rig

SECRET = "13800138000 audit-person@example.test"


def test_supported_carriers_and_immutability(tmp_path):
    args = {"query": SECRET, "nested": [{"text": SECRET, "n": 12.5, "b": True,
            "empty": None, "label": "正常中文"}], "limit": 2}
    messages = [HumanMessage(content=SECRET),
                HumanMessage(content=[{"type": "text", "text": SECRET},
                                      {"type": "text", "text": "正常中文"}]),
                AIMessage(content="", tool_calls=[dict(id="native-13800138000", name="search_manuals", args=args)]),
                ToolMessage(content=json.dumps({"text": SECRET}), tool_call_id="native-13800138000")]
    before = copy.deepcopy(messages)
    g, ledger, seen = rig(tmp_path, [dict(role="assistant", content="ok")])
    try:
        g.invoke_with_tools(messages, [])
        assert messages == before
        wire = seen[0]["messages"]
        assert wire[0]["content"] == "[PHONE] [EMAIL]"
        assert wire[1]["content"] == "[PHONE] [EMAIL]\n正常中文"
        call = wire[2]["tool_calls"][0]
        assert call["id"] == wire[3]["tool_call_id"] == "native-13800138000"
        assert call["function"]["name"] == "search_manuals"
        restored = json.loads(call["function"]["arguments"])
        assert restored == {"query": "[PHONE] [EMAIL]", "nested": [{"text": "[PHONE] [EMAIL]", "n": 12.5, "b": True, "empty": None, "label": "正常中文"}], "limit": 2}
        assert json.loads(wire[3]["content"])["text"] == "[PHONE] [EMAIL]"
        assert len(ledger.read()["calls"]) == 1
    finally:
        g.close()


@pytest.mark.parametrize("content", [
    [{"type": "text", "text": SECRET}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}}],
    [{"type": "input_audio", "input_audio": {"data": "AA==", "format": "wav"}}],
    [{"type": "text", "text": SECRET, "unrecognized": SECRET}],
])
def test_unsupported_carrier_before_reservation(tmp_path, content):
    messages = [HumanMessage(content=content)]
    before = copy.deepcopy(messages)
    g, ledger, seen = rig(tmp_path, [])
    try:
        with pytest.raises(ModelError, match="MODEL_MESSAGE_UNSUPPORTED"):
            g.invoke_with_tools(messages, [])
        assert not seen and not ledger.read()["calls"] and g.calls == 0
        assert messages == before
    finally:
        g.close()


def test_real_lock_deadline_terminal(tmp_path):
    g, ledger, seen = rig(tmp_path, [dict(role="assistant", content="must not send")])
    worker = tmp_path / "hold.py"
    held = tmp_path / "held"
    worker.write_text("import sys,time\nfrom pathlib import Path\nfrom app.infrastructure.model_budget import exclusive\nwith exclusive(Path(sys.argv[1])):\n Path(sys.argv[2]).touch()\n time.sleep(1.6)\n")
    process = subprocess.Popen([sys.executable, "-B", str(worker), str(ledger.path), str(held)])
    try:
        deadline = time.monotonic() + 10
        while not held.exists():
            assert time.monotonic() < deadline
            time.sleep(.01)
        g.started = time.monotonic() - 119.7
        start = time.monotonic()
        with pytest.raises(ModelError, match="MODEL_TURN_TIMEOUT"):
            g.invoke_with_tools([], [])
        assert time.monotonic() - start >= 1.5
        assert process.wait(timeout=10) == 0 and not seen
        state = ledger.read()
        assert len(state["calls"]) == g.calls == 1
        row = next(iter(state["calls"].values()))
        assert row["status"] == "not_sent" and row["dispatched"] is False
        assert row["usage"] is None and row["usage_status"] == "unknown"
        assert Decimal(state["reserved_cny"]) == Decimal(row["reserved_cny"]) > 0
        print(json.dumps({"pid": process.pid, "wait_seconds": time.monotonic()-start, "transport": len(seen), "terminal": row["status"]}))
    finally:
        g.close()
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


@pytest.mark.parametrize("mode", ["deadline", "amount", "normal"])
def test_retry_still_bounded(tmp_path, monkeypatch, mode):
    g, ledger, seen = rig(tmp_path, [429, dict(role="assistant", content="ok")])
    # Clock changes only after the first actual mocked response has been handled.
    if mode == "deadline":
        finish = ledger.finish
        def delayed(*args):
            finish(*args)
            g.started -= 121
        monkeypatch.setattr(ledger, "finish", delayed)
    elif mode == "amount":
        d = ledger.read()
        d["reserved_cny"] = "4.98"
        ledger.save(d)
    try:
        if mode in {"normal", "amount"}:
            assert g.invoke_with_tools([], []).content == "ok"
            assert len(seen) == len(ledger.read()["calls"]) == 2
        else:
            with pytest.raises(ModelError, match="MODEL_TURN_BUDGET_EXHAUSTED"):
                g.invoke_with_tools([], [])
            assert len(seen) == len(ledger.read()["calls"]) == 1
    finally:
        g.close()


def test_sent_late_response_not_usable(tmp_path, monkeypatch):
    g, ledger, seen = rig(tmp_path, [dict(role="assistant", content="late")])
    finish = ledger.finish
    def late(*args):
        finish(*args)
        g.started -= 121
    monkeypatch.setattr(ledger, "finish", late)
    try:
        with pytest.raises(ModelError, match="MODEL_TURN_TIMEOUT"):
            g.invoke_with_tools([], [])
        assert len(seen) == 1
        assert next(iter(ledger.read()["calls"].values()))["status"] == "received"
    finally:
        g.close()
