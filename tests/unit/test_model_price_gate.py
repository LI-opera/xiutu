"""Free checks for the paid gateway's retained model, target and budget gates."""

import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from app.config import Settings
from app.infrastructure import model_gateway
from app.infrastructure.model_budget import BudgetLedger
from app.infrastructure.model_gateway import DeepSeekGateway, ModelError
from langchain_core.messages import HumanMessage


class OfflineChat:
    requests = []

    def __init__(self, **kwargs):
        self.max_tokens = kwargs["max_tokens"]

    def bind(self, **options):
        return self

    def invoke(self, messages):
        self.requests.append(dict(max_tokens=self.max_tokens, messages=messages))
        return SimpleNamespace(
            content="synthetic", tool_calls=[], invalid_tool_calls=[],
            usage_metadata=None,
            response_metadata={"model_name": "deepseek-flash", "finish_reason": "stop"},
        )


def paid_rig(tmp_path, monkeypatch, **settings_overrides):
    ledger = BudgetLedger(tmp_path / "isolated-budget.json")
    ledger.initialize("offline synthetic test")
    monkeypatch.setattr(model_gateway, "LIVE_LEDGER", ledger.path)
    monkeypatch.setattr(model_gateway, "ChatDeepSeek", OfflineChat)
    OfflineChat.requests = []
    settings = Settings(deepseek_api_key="offline-placeholder", **settings_overrides)
    return settings, ledger


def test_historical_cutoff_no_longer_rejects_paid_gateway(tmp_path, monkeypatch):
    assert datetime.now(timezone.utc) >= datetime(2026, 9, 20, tzinfo=timezone.utc)
    settings, ledger = paid_rig(tmp_path, monkeypatch)
    gateway = DeepSeekGateway(settings, paid=True, max_output_tokens=1536)
    try:
        assert gateway.request([HumanMessage(content="offline synthetic")]).content == "synthetic"
        assert len(OfflineChat.requests) == 1
        row = next(iter(ledger.read()["calls"].values()))
        assert row["output_upper"] == OfflineChat.requests[0]["max_tokens"] == 1536
        assert row["usage_status"] == "unknown"
    finally:
        gateway.close()


def test_unknown_model_rejected_but_cumulative_amount_is_metered(tmp_path, monkeypatch):
    settings, ledger = paid_rig(tmp_path, monkeypatch, deepseek_model="unpriced-model")
    gateway = DeepSeekGateway(settings, paid=True)
    try:
        with pytest.raises(ModelError, match="MODEL_PRICE_UNVERIFIED"):
            gateway.request([HumanMessage(content="offline synthetic")])
        assert not OfflineChat.requests and not ledger.read()["calls"]
    finally:
        gateway.close()

    settings, ledger = paid_rig(tmp_path / "excess", monkeypatch)
    state = ledger.read()
    state["reserved_cny"] = "4.999"
    ledger.save(state)
    gateway = DeepSeekGateway(settings, paid=True, max_output_tokens=1536)
    try:
        assert gateway.request([HumanMessage(content="offline synthetic")]).content == "synthetic"
        assert len(OfflineChat.requests) == len(ledger.read()["calls"]) == 1
        assert float(ledger.read()["reserved_cny"]) > 5
    finally:
        gateway.close()


def test_config_and_post_reservation_deadline_remain_fail_closed(tmp_path, monkeypatch):
    settings, ledger = paid_rig(tmp_path, monkeypatch)
    with pytest.raises(ModelError, match="MODEL_TARGET_DENIED"):
        DeepSeekGateway(settings.model_copy(update={"deepseek_base_url": "https://example.test"}),
                        paid=True)
    assert not hasattr(settings, "llm_budget_cny")

    gateway = DeepSeekGateway(settings, paid=True)
    reserve = gateway.ledger.reserve

    def expire_after_reserving(*args, **kwargs):
        reserve(*args, **kwargs)
        gateway.started = time.monotonic() - 121

    monkeypatch.setattr(gateway.ledger, "reserve", expire_after_reserving)
    try:
        with pytest.raises(ModelError, match="MODEL_TURN_TIMEOUT"):
            gateway.request([HumanMessage(content="offline synthetic")])
        row = next(iter(ledger.read()["calls"].values()))
        assert row["status"] == "not_sent" and row["dispatched"] is False
        assert not OfflineChat.requests
    finally:
        gateway.close()
