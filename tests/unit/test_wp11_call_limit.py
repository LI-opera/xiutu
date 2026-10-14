"""No-network budgeted WP-11 model-attempt checks."""

import json

import httpx
import pytest
from app.config import Settings
from app.infrastructure.model_budget import BudgetLedger
from app.infrastructure.model_gateway import DeepSeekGateway, ModelError
from langchain_core.messages import HumanMessage


def rig(tmp_path, replies, *, turn="wp11-test", resume=False, limit=4):
    path = tmp_path / "isolated-ledger.json"
    ledger = BudgetLedger(path)
    if not path.exists():
        ledger.initialize("offline synthetic fixture")
    sent = []
    queue = iter(replies)

    def response(request):
        sent.append(json.loads(request.content))
        item = next(queue)
        if isinstance(item, int):
            return httpx.Response(item, json={"error": {"message": "synthetic"}})
        return httpx.Response(200, json={
            "id": "synthetic", "object": "chat.completion", "created": 0,
            "model": "deepseek-flash",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": item},
                         "finish_reason": "stop"}],
        })

    gateway = DeepSeekGateway(
        Settings(deepseek_api_key="offline-placeholder"),
        transport=httpx.MockTransport(response), ledger=ledger,
        turn_id=turn, resume_existing=resume, max_model_calls=limit,
    )
    return gateway, ledger, sent


def invoke(gateway):
    return gateway.request([HumanMessage(content="synthetic")])


def test_four_calls_then_fifth_rejected_before_reservation_or_send(tmp_path):
    gateway, ledger, sent = rig(tmp_path, ["ok"] * 4)
    try:
        for _ in range(4):
            assert invoke(gateway).content == "ok"
        before = ledger.read()
        with pytest.raises(ModelError, match="MODEL_TURN_BUDGET_EXHAUSTED"):
            invoke(gateway)
        assert len(sent) == len(ledger.read()["calls"]) == 4
        assert ledger.read() == before
    finally:
        gateway.close()


def test_provider_retry_consumes_one_of_four_attempts(tmp_path):
    gateway, ledger, sent = rig(tmp_path, [429, "ok", "ok", "ok"])
    try:
        assert invoke(gateway).content == "ok"  # 429 then one bounded retry
        assert invoke(gateway).content == "ok"
        assert invoke(gateway).content == "ok"
        with pytest.raises(ModelError, match="MODEL_TURN_BUDGET_EXHAUSTED"):
            invoke(gateway)
        assert len(sent) == len(ledger.read()["calls"]) == 4
    finally:
        gateway.close()


def test_worker_restart_inherits_same_turn_count(tmp_path):
    first, ledger, first_sent = rig(tmp_path, ["ok", "ok"])
    try:
        invoke(first)
        invoke(first)
    finally:
        first.close()
    second, same_ledger, second_sent = rig(tmp_path, ["ok", "ok"], resume=True)
    try:
        assert second.calls == 2
        invoke(second)
        invoke(second)
        before = same_ledger.read()
        with pytest.raises(ModelError, match="MODEL_TURN_BUDGET_EXHAUSTED"):
            invoke(second)
        assert len(first_sent) == len(second_sent) == 2
        assert len(ledger.read()["calls"]) == 4
        assert same_ledger.read() == before
    finally:
        second.close()


def test_no_cumulative_cap_and_configuration_fail_closed(tmp_path):
    with pytest.raises(ModelError, match="MODEL_CALL_LIMIT_INVALID"):
        rig(tmp_path, [], limit=5.0)
    with pytest.raises(ModelError, match="MODEL_CALL_LIMIT_INVALID"):
        rig(tmp_path, [], limit=True)
    with pytest.raises(ModelError, match="MODEL_CALL_LIMIT_INVALID"):
        rig(tmp_path, [], limit=6)
    gateway, ledger, sent = rig(tmp_path, ["ok"])
    state = ledger.read()
    state["reserved_cny"] = "4.99"
    ledger.save(state)
    try:
        assert invoke(gateway).content == "ok"
        assert len(sent) == len(ledger.read()["calls"]) == 1
        assert float(ledger.read()["reserved_cny"]) > 4.99
    finally:
        gateway.close()


def test_wp09_default_still_allows_fifth_call(tmp_path):
    path = tmp_path / "wp09-ledger.json"
    ledger = BudgetLedger(path)
    ledger.initialize("offline synthetic fixture")
    seen = []

    def response(request):
        seen.append(request)
        return httpx.Response(200, json={
            "id": "synthetic", "object": "chat.completion", "created": 0,
            "model": "deepseek-flash",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"},
                         "finish_reason": "stop"}],
        })

    gateway = DeepSeekGateway(
        Settings(deepseek_api_key="offline-placeholder"),
        transport=httpx.MockTransport(response), ledger=ledger,
    )
    try:
        assert gateway.call_limit == 5
        for _ in range(5):
            invoke(gateway)
        with pytest.raises(ModelError, match="MODEL_TURN_BUDGET_EXHAUSTED"):
            invoke(gateway)
        assert len(seen) == len(ledger.read()["calls"]) == 5
    finally:
        gateway.close()
