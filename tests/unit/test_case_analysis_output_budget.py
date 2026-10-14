"""Offline checks for bounded case-advice output and retained truncated replies."""

import json
from types import SimpleNamespace

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from openai import LengthFinishReasonError
from pydantic import ValidationError

from app.config import Settings
from app.domain.case_analysis import CaseAdviceOpenV1
from app.infrastructure.model_budget import BudgetLedger
from app.infrastructure.model_gateway import DeepSeekGateway, ModelError
from app.services import case_analysis_diagnostics as diagnostics
from app.services.case_analysis_projection import freeze_generation_settings


class Adapter:
    def __init__(self, outcome):
        self.outcome = outcome
        self.invocations = 0

    def bind(self, **_options):
        return self

    def invoke(self, _wire):
        self.invocations += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def gateway(tmp_path, outcome, limit=4096):
    ledger = BudgetLedger(tmp_path / "budget.json")
    ledger.initialize("offline fixture")
    item = DeepSeekGateway(
        Settings(deepseek_api_key="offline-placeholder"),
        transport=httpx.MockTransport(lambda _: pytest.fail("No network request expected")),
        ledger=ledger, max_output_tokens=limit, max_model_calls=1,
    )
    item.adapter = Adapter(outcome)
    return item, ledger


def completion(*, content=None, usage=None):
    return SimpleNamespace(
        model="deepseek-flash",
        choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="length")],
        usage=usage,
    )


def ledger_call(ledger):
    calls = ledger.read()["calls"]
    assert len(calls) == 1
    return next(iter(calls.values()))


def test_sdk_length_error_retains_partial_text_model_and_actual_usage(tmp_path):
    partial = '{"summary":"部分输出'
    usage = SimpleNamespace(prompt_tokens=900, completion_tokens=4096, total_tokens=4996)
    item, ledger = gateway(tmp_path, LengthFinishReasonError(
        completion=completion(content=partial, usage=usage)))
    captured = []
    try:
        with pytest.raises(ModelError, match="MODEL_TRUNCATED"):
            item.generate_structured_once(CaseAdviceOpenV1, [HumanMessage(content="offline")],
                                          on_response=lambda raw, meta: captured.append((raw, meta)))
        assert item.adapter.invocations == 1
        assert len(captured) == 1 and captured[0][0] == partial
        assert captured[0][1]["returned_model"] == "deepseek-flash"
        assert captured[0][1]["finish_reason"] == "length"
        assert captured[0][1]["provider_output_truncated"] is True
        assert captured[0][1]["usage"] == {"input_tokens": 900, "output_tokens": 4096,
                                            "total_tokens": 4996}
        row = ledger_call(ledger)
        assert row["status"] == "failed" and row["error_code"] == "MODEL_TRUNCATED"
        assert row["usage"] == captured[0][1]["usage"]
        assert row["usage_status"] == "reported" and row["output_upper"] == 4096
    finally:
        item.close()


def test_installed_sdk_length_exception_from_mock_http_retains_completion(tmp_path):
    sent = []

    def response(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "offline-truncated", "object": "chat.completion", "created": 0,
            "model": "deepseek-flash",
            "choices": [{"index": 0, "message": {"role": "assistant",
                                                 "content": '{"summary":"partial'},
                         "finish_reason": "length"}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4096,
                      "total_tokens": 4108},
        })

    ledger = BudgetLedger(tmp_path / "budget.json")
    ledger.initialize("offline SDK fixture")
    item = DeepSeekGateway(
        Settings(deepseek_api_key="offline-placeholder"),
        transport=httpx.MockTransport(response), ledger=ledger,
        max_output_tokens=4096, max_model_calls=1,
    )
    captured = []
    try:
        with pytest.raises(ModelError, match="MODEL_TRUNCATED"):
            item.generate_structured_once(
                CaseAdviceOpenV1, [HumanMessage(content="offline")],
                on_response=lambda raw, meta: captured.append((raw, meta)),
            )
        assert len(sent) == 1 and sent[0]["max_tokens"] == 4096
        assert len(captured) == 1 and captured[0][0] == '{"summary":"partial'
        assert captured[0][1]["usage"] == {"input_tokens": 12,
                                             "output_tokens": 4096,
                                             "total_tokens": 4108}
        assert ledger_call(ledger)["usage_status"] == "reported"
    finally:
        item.close()


def test_sdk_length_error_without_body_or_usage_marks_absence(tmp_path, monkeypatch):
    item, ledger = gateway(tmp_path, LengthFinishReasonError(completion=completion()))
    saved = []

    class FakeResult:
        def mappings(self):
            return self

        def one(self):
            return {"id": "offline-analysis", "status": "draft", "dispatch_state": "reserved",
                    "input_revision": 60}

    class FakeConnection:
        def execute(self, statement):
            if statement.__visit_name__ == "update":
                value = statement.compile().params.get("diagnostic_json")
                if value:
                    saved.append(value)
            return FakeResult()

    class FakeUow:
        connection = FakeConnection()

        def __init__(self, _engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

    monkeypatch.setattr(diagnostics, "UnitOfWork", FakeUow)
    try:
        with pytest.raises(ModelError, match="MODEL_TRUNCATED"):
            item.generate_structured_once(CaseAdviceOpenV1, [HumanMessage(content="offline")],
                on_response=lambda raw, meta: diagnostics.record_response(None, "offline-analysis", raw, meta))
        assert item.adapter.invocations == 1 and len(saved) == 1
        row = saved[0]
        assert row["response_available"] is False and row["raw_response"] is None
        assert row["sha256"] is None and row["response_utf8_bytes"] is None
        assert row["diagnostic_storage_truncated"] is None
        assert row["provider_output_truncated"] is True
        assert row["usage"] is None and row["usage_available"] is False
        assert ledger_call(ledger)["usage_status"] == "unknown"
    finally:
        item.close()


def test_provider_length_and_local_diagnostic_size_are_separate(monkeypatch):
    saved = []

    class FakeResult:
        def mappings(self):
            return self

        def one(self):
            return {"status": "draft", "dispatch_state": "reserved", "input_revision": 60}

    class FakeConnection:
        def execute(self, statement):
            if statement.__visit_name__ == "update":
                value = statement.compile().params.get("diagnostic_json")
                if value:
                    saved.append(value)
            return FakeResult()

    class FakeUow:
        connection = FakeConnection()

        def __init__(self, _engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

    monkeypatch.setattr(diagnostics, "UnitOfWork", FakeUow)
    raw = "测" * 12000
    diagnostics.record_response(None, "offline-analysis", raw, {
        "provider_output_truncated": True, "finish_reason": "length",
    })
    row = saved[0]
    assert row["provider_output_truncated"] is True
    assert row["diagnostic_storage_truncated"] is True
    assert row["response_utf8_bytes"] == len(raw.encode("utf-8"))
    assert len(row["raw_response"].encode("utf-8")) <= diagnostics.MAX_RESPONSE_BYTES


def test_returned_length_and_storage_failure_never_retry(tmp_path):
    response = AIMessage(content='{"summary":"partial"', usage_metadata={
        "input_tokens": 8, "output_tokens": 16, "total_tokens": 24},
        response_metadata={"model_name": "deepseek-flash", "finish_reason": "length"})
    item, ledger = gateway(tmp_path, response)
    captured = []
    try:
        with pytest.raises(ModelError, match="MODEL_TRUNCATED"):
            item.generate_structured_once(CaseAdviceOpenV1, [HumanMessage(content="offline")],
                                          on_response=lambda raw, meta: captured.append((raw, meta)))
        assert item.adapter.invocations == 1 and len(captured) == 1
        assert captured[0][1]["provider_output_truncated"] is True
        assert ledger_call(ledger)["usage_status"] == "reported"
    finally:
        item.close()

    other, other_ledger = gateway(tmp_path / "other", LengthFinishReasonError(
        completion=completion(content="partial")))
    try:
        with pytest.raises(ModelError, match="ANALYSIS_DIAGNOSTIC_STORE_FAILED"):
            other.generate_structured_once(CaseAdviceOpenV1, [HumanMessage(content="offline")],
                on_response=lambda *_: (_ for _ in ()).throw(
                    ModelError("ANALYSIS_DIAGNOSTIC_STORE_FAILED")))
        assert other.adapter.invocations == 1
        assert ledger_call(other_ledger)["error_code"] == "MODEL_TRUNCATED"
    finally:
        other.close()


def test_complete_response_and_frozen_output_above_old_limit(tmp_path):
    settings = Settings(deepseek_api_key="offline-placeholder",
                        case_analysis_max_output_tokens=8192)
    frozen = freeze_generation_settings({}, {"mode": "real", "provider": "deepseek",
                                             "model": "deepseek-flash"}, settings)
    response = AIMessage(content='{"summary":"完整分析"}', usage_metadata={
        "input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        response_metadata={"model_name": "deepseek-flash", "finish_reason": "stop"})
    item, ledger = gateway(tmp_path, response, frozen["max_output_tokens"])
    captured = []
    try:
        result = item.generate_structured_once(CaseAdviceOpenV1, [HumanMessage(content="offline")],
                                               on_response=lambda raw, meta: captured.append((raw, meta)))
        assert result.summary == "完整分析" and item.adapter.invocations == 1
        assert len(captured) == 1 and captured[0][1]["provider_output_truncated"] is False
        assert frozen["max_output_tokens"] == item.max_tokens == ledger_call(ledger)["output_upper"] == 8192
        assert ledger_call(ledger)["status"] == "received"
    finally:
        item.close()


@pytest.mark.parametrize("invalid", [0, -1, True, "not-an-integer", 16385])
def test_invalid_case_analysis_output_limit_is_rejected(invalid):
    with pytest.raises(ValidationError):
        Settings(case_analysis_max_output_tokens=invalid)


def test_case_analysis_output_limit_accepts_decimal_environment_string(monkeypatch):
    monkeypatch.setenv("CASE_ANALYSIS_MAX_OUTPUT_TOKENS", "8192")
    assert Settings().case_analysis_max_output_tokens == 8192
    monkeypatch.setenv("CASE_ANALYSIS_MAX_OUTPUT_TOKENS", "8192.0")
    with pytest.raises(ValidationError):
        Settings()
