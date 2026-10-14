"""C07 bounded proposal and text validation using synthetic frozen data only."""

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.domain.case_analysis import CaseAdviceProposalV3
from app.domain.policies import DomainError
from app.infrastructure.model_gateway import structured_schema_instruction
from app.services.case_analysis_actions import supported_actions
from app.services.case_analysis_context import selected_context
from app.legacy_execution.case_analysis import (assemble_proposal, input_characters, model_payload,
                                                proposal_schema, substitute_advice,
                                                proposal_instruction, validate_advice)
from app.topics import dkvb_b02


def frozen():
    topic, _ = dkvb_b02.catalog()
    context = deepcopy(selected_context(topic, ["AIR-07", "PRS-01"]))
    return {
        "output_contract_version": "case-advice-proposal-c07-v1",
        "allowed_scope": "supplement_or_handoff",
        "observations": [
            {"id": "air-fact", "question_id": "AIR-07", "option_ids": ["partially_seated"], "fields": {}},
            {"id": "pressure-fact", "question_id": "PRS-01", "option_ids": ["recorded"],
             "fields": {"hpa": {"value": 1000, "unit": "hPa absolute"},
                        "rpm": {"value": 2800, "unit": "rpm"}}},
        ],
        "unresolved_questions": [{"question_id": "PRS-02", "target_question_id": "PRS-02"}],
        "derived": {"PRS-11": {"detail": {"evidence_state": "computed", "gaps_hpa": [400]}}},
        "source_context": context, "action_catalog": supported_actions(context),
    }


def proposal():
    return {
        "summary": "合成病例记录接头未完全座合；目前不能确诊，也不能据此排除其他方向。",
        "supported_directions": [], "unconfirmed_directions": ["压力来源仍需核对。"],
        "steps": [
            {"type": "controlled", "action_id": "CHECK_CHARGE_AIR_HOSE_SEATING_LEAK",
             "basis_observation_ids": ["air-fact"]},
            {"type": "free", "kind": "handoff", "action": "补充 PRS-02 的已有静态压力记录。",
             "reason": "本轮缺少 G31 静态压力原始记录。", "missing_question_ids": ["PRS-02"]},
        ],
        "retest_plan": "若后续实际处理，另开独立复检轮次；当前没有处理后事实。",
        "uncertainty": "非实车确诊，所有观察均为合成演示。",
        "safety_notice": "禁止拆卸或加压；不满足安全条件时交接。",
    }


def test_compact_handoff_and_frozen_controlled_action():
    snapshot = frozen()
    schema = proposal_schema(snapshot)
    assert schema["$defs"]["FreeStepProposalV3"]["properties"]["source_ids"]["items"]["enum"] == [
        item["id"] for item in snapshot["source_context"]["excerpts"]]
    assert "source_metadata" not in model_payload(snapshot)["source_context"]
    result = assemble_proposal(snapshot, proposal())
    rule = snapshot["action_catalog"]["actions"]["CHECK_CHARGE_AIR_HOSE_SEATING_LEAK"]
    assert result["steps"][0]["source_ids"] == rule["required_excerpt_ids"]
    assert result["steps"][0]["action"] == rule["action"]
    assert result["steps"][1]["reason"]
    assert result["steps"][1]["missing_question_ids"] == ["PRS-02"]
    assert result["steps"][1]["retest"] is None


def test_input_budget_counts_the_exact_schema_message_sent_to_gateway():
    snapshot = frozen()
    expected = (len(json.dumps(model_payload(snapshot), ensure_ascii=False, separators=(",", ":"))) +
                len(proposal_instruction(snapshot)) +
                len(structured_schema_instruction(proposal_schema(snapshot))))
    assert input_characters(snapshot) == expected


@pytest.mark.parametrize("change", [
    {"action": ""}, {"reason": ""}, {"source_ids": ["SRC-CHARGE-AIR"]},
    {"basis_observation_ids": ["invented"]}, {"missing_question_ids": ["NOT_MISSING"]},
])
def test_empty_or_invented_free_content_rejected(change):
    draft = proposal()
    draft["steps"][1].update(change)
    with pytest.raises((DomainError, ValidationError)):
        assemble_proposal(frozen(), draft)


@pytest.mark.parametrize("value", [
    "建议拆卸涡轮并更换部件。", "请对增压空气管路加压检漏。",
])
def test_free_step_does_not_hide_technical_operation(value):
    draft = proposal()
    draft["steps"][1]["action"] = value
    with pytest.raises(DomainError) as error:
        assemble_proposal(frozen(), draft)
    assert error.value.details["field_path"] == "steps[1].action"


def test_controlled_extra_field_rejected_in_schema():
    draft = proposal()
    draft["steps"][0]["source_ids"] = ["C01-SRC-CHARGE-AIR-P1"]
    with pytest.raises(ValidationError) as error:
        CaseAdviceProposalV3.model_validate(draft)
    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_negation_and_recorded_numbers_but_not_mixed_assertions():
    snapshot = frozen()
    result = assemble_proposal(snapshot, proposal())
    result["summary"] = "非实车确诊；已保存静态压力 1000 hPa、转速 2800 rpm，派生差值 400 hPa。"
    assert validate_advice(snapshot, result)["summary"] == result["summary"]
    for text, expected in [
        ("目前不能确诊，但已确定需要更换涡轮。", "text.unsupported_certainty"),
        ("禁止加压，但建议拆卸涡轮。", "text.unsupported_operation"),
        ("已保存静态压力 9999 hPa。", "text.unsupported_parameter"),
        ("安全限值不得超过 1000 hPa。", "text.unsupported_parameter"),
        ("检漏操作压力不得超过 0.5 bar。", "text.unsupported_parameter"),
    ]:
        changed = deepcopy(result)
        changed["summary"] = text
        with pytest.raises(DomainError) as error:
            validate_advice(snapshot, changed)
        assert error.value.details["rule_id"] == expected


def test_c07_missing_reason_does_not_silently_drop_step():
    draft = proposal()
    del draft["steps"][1]["reason"]
    with pytest.raises(ValidationError):
        assemble_proposal(frozen(), draft)


def test_substitute_uses_short_handoff_without_fake_retest_text():
    snapshot = frozen()
    snapshot["synthesis"] = {"unavailable": [], "missing_question_ids": ["PRS-02"], "conflicts": []}
    result = validate_advice(snapshot, substitute_advice(snapshot))
    handoff = result["steps"][-1]
    assert handoff["missing_question_ids"] == ["PRS-02"]
    assert handoff["reason"] and handoff["retest"] is None
