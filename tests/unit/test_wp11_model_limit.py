"""No-network checks for the server-owned WP-11 model output allowance."""

import json

import httpx
import pytest
from app.config import Settings
from app.infrastructure.model_budget import BudgetLedger
from app.infrastructure.model_gateway import DeepSeekGateway, ModelError
from langchain_core.messages import HumanMessage
from pydantic import ValidationError


def test_configured_output_limit_matches_transport_and_reservation(tmp_path):
    sent = []

    def response(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "synthetic", "object": "chat.completion", "created": 0,
            "model": "deepseek-flash",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "{}"},
                         "finish_reason": "stop"}],
        })

    settings = Settings(deepseek_api_key="offline-placeholder")
    ledger = BudgetLedger(tmp_path / "ledger.json")
    ledger.initialize("offline fixture")
    gateway = DeepSeekGateway(
        settings, transport=httpx.MockTransport(response), ledger=ledger,
        max_output_tokens=1536,
    )
    try:
        gateway.request([HumanMessage(content="synthetic")])
        assert sent[0]["max_tokens"] == 1536
        record = next(iter(ledger.read()["calls"].values()))
        assert record["output_upper"] == sent[0]["max_tokens"]
        assert record["usage_status"] == "unknown"  # provider omitted usage
        with pytest.raises(ModelError, match="MODEL_OPTIONS_DENIED"):
            gateway.request([], max_tokens=16384)
        assert len(sent) == 1
    finally:
        gateway.close()


def test_truncation_still_fails_without_using_partial_result(tmp_path):
    sent = []

    def response(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "synthetic", "object": "chat.completion", "created": 0,
            "model": "deepseek-flash",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": '{"partial":'},
                         "finish_reason": "length"}],
        })

    ledger = BudgetLedger(tmp_path / "ledger.json")
    ledger.initialize("offline fixture")
    gateway = DeepSeekGateway(
        Settings(deepseek_api_key="offline-placeholder"),
        transport=httpx.MockTransport(response), ledger=ledger, max_output_tokens=1536,
    )
    try:
        with pytest.raises(ModelError, match="MODEL_TRUNCATED"):
            gateway.request([HumanMessage(content="synthetic")],
                            response_format={"type": "json_object"})
        assert len(sent) == 1
        record = next(iter(ledger.read()["calls"].values()))
        assert record["output_upper"] == 1536
        assert record["usage_status"] == "unknown"
        assert record["request_mode"] == "json"
        assert record["error_code"] == "MODEL_TRUNCATED"
    finally:
        gateway.close()


def test_output_limit_is_bounded_server_configuration(tmp_path):
    with pytest.raises(ValidationError):
        Settings(area_analysis_max_output_tokens=16385)
    with pytest.raises(ValidationError):
        Settings(area_analysis_max_output_tokens=200)
    ledger = BudgetLedger(tmp_path / "ledger.json")
    ledger.initialize("offline fixture")
    gateway = DeepSeekGateway(
        Settings(deepseek_api_key="offline-placeholder"),
        transport=httpx.MockTransport(lambda _: httpx.Response(500)),
        ledger=ledger, max_output_tokens=4096,
    )
    assert gateway.max_tokens == 4096
    gateway.close()
    with pytest.raises(ModelError, match="MODEL_OUTPUT_LIMIT_INVALID"):
        DeepSeekGateway(
            Settings(deepseek_api_key="offline-placeholder"),
            transport=httpx.MockTransport(lambda _: httpx.Response(500)),
            ledger=ledger, max_output_tokens=16385,
        )
