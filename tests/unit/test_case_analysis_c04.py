"""Artificial C04 proposals only; never a replay of the lost C03 response."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.domain.case_analysis import CaseAdviceProposal
from app.domain.policies import DomainError
from app.infrastructure.model_gateway import DeepSeekGateway, ModelError
from app.services.case_analysis_actions import supported_actions
from app.services.case_analysis_context import selected_context
from app.legacy_execution.case_analysis import (assemble_proposal, proposal_schema,
                                                publish_case_analysis, substitute_advice,
                                                validate_advice)
from app.services import case_analysis_diagnostics as diagnostics
from app.topics import dkvb_b02


def frozen(scope="supplement_or_handoff"):
    topic, _ = dkvb_b02.catalog()
    context = selected_context(topic, ["AIR-07"])
    return {"allowed_scope": scope,
            "observations": [{"id": "c04-synthetic-observation", "question_id": "AIR-07",
                              "option_ids": ["partially_seated"]}],
            "source_context": context, "action_catalog": supported_actions(context),
            "synthesis": {"unavailable": [], "missing_question_ids": [], "conflicts": []}}


def proposal(snapshot):
    return deepcopy(substitute_advice(snapshot))


def assert_rule(error, rule, path):
    assert error.value.details["rule_id"] == rule
    assert error.value.details["field_path"] == path
    assert error.value.details["allowed_scope"] == "supplement_or_handoff"


def test_scope_contract_and_distinct_field_failures():
    snapshot = frozen()
    schema = proposal_schema(snapshot)
    assert schema["properties"]["supported_directions"]["maxItems"] == 0
    assert schema["$defs"]["ProposedStep"]["properties"]["kind"]["enum"] == ["check", "handoff"]
    draft = proposal(snapshot)
    draft["supported_directions"] = [{"title": "可维修", "basis_observation_ids": ["c04-synthetic-observation"],
                                       "source_ids": [], "limit": "仍需现场确认"}]
    with pytest.raises(DomainError) as error:
        assemble_proposal(snapshot, draft)
    assert_rule(error, "scope.no_supported_direction", "supported_directions[0]")
    draft = proposal(snapshot)
    draft["steps"][0]["kind"] = "conditional_action"
    with pytest.raises(DomainError) as error:
        assemble_proposal(snapshot, draft)
    assert_rule(error, "scope.conditional_action", "steps[0].kind")


def test_frozen_action_assembly_and_rejections():
    snapshot = frozen()
    draft = proposal(snapshot)
    rule = snapshot["action_catalog"]["actions"]["CHECK_CHARGE_AIR_HOSE_SEATING_LEAK"]
    controlled = draft["steps"][0]
    for field in ("action", "prerequisites", "retest", "stop_condition"):
        controlled.pop(field)
    controlled["source_ids"] = []
    content = assemble_proposal(snapshot, draft)
    assert content["steps"][0]["action"] == rule["action"]
    assert content["steps"][0]["retest"] == rule["retest"]
    assert content["steps"][0]["source_ids"] == rule["required_excerpt_ids"]
    unknown = deepcopy(draft)
    unknown["steps"][0]["action_id"] = "NOT_IN_FROZEN_CATALOG"
    with pytest.raises(DomainError) as error:
        assemble_proposal(snapshot, unknown)
    assert error.value.details["rule_id"] == "action.known"
    bad_source = deepcopy(draft)
    bad_source["steps"][0]["source_ids"] = ["C01-SRC-CHARGE-AIR-P5"]
    with pytest.raises(DomainError) as error:
        assemble_proposal(snapshot, bad_source)
    assert error.value.details["rule_id"] == "action.source"
    missing_fact = deepcopy(draft)
    missing_fact["steps"][0]["basis_observation_ids"] = []
    with pytest.raises(DomainError) as error:
        assemble_proposal(snapshot, missing_fact)
    assert error.value.details["rule_id"] == "action.fact"


def test_parse_and_structure_failures_capture_once_without_repair():
    for raw, expected in (("not json", "MODEL_JSON_INVALID_NO_RETRY"),
                          ('{"summary":"short"}', "MODEL_SCHEMA_INVALID_NO_RETRY")):
        gateway = DeepSeekGateway.__new__(DeepSeekGateway)
        captured, calls = [], []
        def fake_request(messages, **options):
            calls.append(options)
            options["on_response"](raw, {"call_key": "synthetic:1", "finish_reason": "stop"})
            return SimpleNamespace(content=raw, tool_calls=[])
        gateway.request = fake_request
        with pytest.raises(ModelError) as error:
            gateway.generate_structured_once(CaseAdviceProposal, [],
                                             on_response=lambda body, meta: captured.append(body))
        assert error.value.code == expected
        assert captured == [raw]
        assert len(calls) == 1 and calls[0]["retry_transient"] is False


def test_storage_failure_stops_before_parse_and_publish():
    gateway = DeepSeekGateway.__new__(DeepSeekGateway)
    def fake_request(messages, **options):
        options["on_response"]("synthetic raw", {"call_key": "synthetic:1"})
        pytest.fail("capture must stop before parsing")
    gateway.request = fake_request
    with pytest.raises(ModelError, match="ANALYSIS_DIAGNOSTIC_STORE_FAILED"):
        gateway.generate_structured_once(CaseAdviceProposal, [],
                                         on_response=lambda *_: (_ for _ in ()).throw(
                                             ModelError("ANALYSIS_DIAGNOSTIC_STORE_FAILED")))

    class FakeResult:
        def mappings(self):
            return self
        def one(self):
            return {"mode": "real", "status": "draft", "dispatch_state": "reserved",
                    "diagnostic_json": {}, "snapshot_json": frozen()}
    class FakeConnection:
        def execute(self, statement):
            return FakeResult()
    with pytest.raises(DomainError, match="响应诊断记录未完成") as error:
        publish_case_analysis(FakeConnection(), "synthetic-run", {})
    assert error.value.code == "ANALYSIS_DIAGNOSTIC_REQUIRED"


def test_rejected_response_is_bounded_and_redacted(monkeypatch):
    saved = []
    class FakeResult:
        def mappings(self):
            return self
        def one(self):
            return {"id": "synthetic-analysis", "status": "draft", "dispatch_state": "reserved",
                    "input_revision": 42}
    class FakeConnection:
        def execute(self, statement):
            if statement.__visit_name__ == "update":
                saved.append(statement.compile().params["diagnostic_json"])
            return FakeResult()
    class FakeUow:
        connection = FakeConnection()
        def __init__(self, engine):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(diagnostics, "UnitOfWork", FakeUow)
    raw = "Authorization: Bearer synthetic-secret-token " + "x" * (diagnostics.MAX_RESPONSE_BYTES + 100)
    diagnostics.record_response(object(), "synthetic-analysis", raw,
                                {"call_key": "synthetic:1", "finish_reason": "stop"})
    first = saved[0]
    assert first["truncated"] is True and first["credentials_redacted"] is True
    assert len(first["raw_response"].encode("utf-8")) == diagnostics.MAX_RESPONSE_BYTES
    assert "synthetic-secret-token" not in first["raw_response"]
    assert first["response_characters"] == len(raw)
    assert first["stage"] == "response_received"


def test_negated_statement_and_old_published_shape():
    snapshot = frozen("fact_review")
    old = proposal(snapshot)
    old["summary"] = "目前不能确诊；不能据此排除其他方向。"
    assert validate_advice(snapshot, old)["summary"] == old["summary"]
    old["safety_notice"] = "已经确诊，应直接更换涡轮。"
    with pytest.raises(DomainError) as error:
        validate_advice(snapshot, old)
    assert error.value.details["field_path"] == "safety_notice"
