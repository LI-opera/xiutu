"""C14 responsibilities: interpret frozen facts, only execute frozen actions."""

from copy import deepcopy

import pytest

from app.domain.policies import DomainError
from app.legacy_execution.case_analysis import assemble_proposal, model_payload, proposal_schema, substitute_advice
from test_case_analysis_c09 import proposal as old_proposal, snapshot as old_snapshot


def frozen():
    value = old_snapshot()
    value["output_contract_version"] = "case-advice-proposal-c14-v1"
    return value


def proposal():
    value = old_proposal()
    value["supported_directions"][0]["editorial_rule_ids"] = ["persistent_gap"]
    value["retest_plan"] = None
    return value


def test_new_schema_does_not_require_retest_and_controlled_text_is_server_owned():
    value = frozen()
    schema = proposal_schema(value)
    assert "retest_plan" not in schema["required"]
    assert "editorial_rule_ids" in schema["$defs"]["AdviceDirectionV5"]["properties"]
    assert "source_ids" not in schema["$defs"]["ControlledStepProposal"]["properties"]
    result = assemble_proposal(value, proposal())
    assert result["publication"]["state"] == "complete"
    assert result["retest_plan"] is None
    assert result["steps"][0]["source_ids"] == ["C01-SRC-CHARGE-AIR-P1"]
    assert result["supported_directions"][0]["editorial_rule_ids"] == ["persistent_gap"]


def test_factual_direction_does_not_require_filler_steps():
    draft = proposal()
    draft["steps"] = []
    assert assemble_proposal(frozen(), draft)["steps"] == []
    draft["supported_directions"] = []
    with pytest.raises(DomainError):
        assemble_proposal(frozen(), draft)


def test_model_view_only_exposes_citable_excerpt_ids():
    value = frozen()
    value["source_context"]["missing_body_source_refs"] = ["REGISTER_ONLY"]
    context = model_payload(value)["source_context"]
    assert "missing_body_source_refs" not in context
    assert context["missing_body_count"] == 1
    assert context["excerpts"]


@pytest.mark.parametrize("text", [
    "按专题演示阈值 250/150 hPa 呈现偏低模式，不能据此确诊。",
    "250/150 hPa 为编辑性演示判别带宽；并非厂家标准。",
    "250/150 hPa 是演示判别带宽；不能作为厂家标准。",
    "模拟压力 1000 hPa 已保存；本次不能据此确诊。",
    "已保存静态 1000 hPa，按编辑性演示阈值 250/150 hPa 仅供说明，非厂家标准。",
])
def test_explanation_uses_frozen_values_without_turning_them_into_actions(text):
    draft = proposal()
    draft["summary"] = text
    assert assemble_proposal(frozen(), draft)["publication"]["state"] == "complete"


@pytest.mark.parametrize("text", [
    "250/150 hPa 是厂家标准。",
    "演示阈值 999 hPa 足以判断故障。",
    "目前不能确诊，但需要更换涡轮。",
    "不能确诊、需要更换涡轮。",
    "禁止加压，随后建议拆装。",
    "建议将已保存的 1000 hPa 设置为加压上限。",
    "建议按演示阈值 250 hPa 加压。",
])
def test_explanation_cannot_invent_standards_or_hide_repair_instruction(text):
    draft = proposal()
    draft["summary"] = text
    with pytest.raises(DomainError):
        assemble_proposal(frozen(), draft)


def test_record_title_reference_not_new_operation_and_new_measurement_is_isolated():
    value = frozen()
    value["unresolved_questions"].append({"question_id": "AIR-14", "name": "加压过程是否遵守最大0.5 bar"})
    draft = proposal()
    draft["steps"][1].update(question_ids=["AIR-14"], missing_question_ids=["AIR-14"])
    draft["steps"][1]["request"] = "补充记录 AIR-14 加压过程是否遵守最大 0.5 bar 的结果或未执行原因。"
    assert assemble_proposal(value, draft)["publication"]["state"] == "complete"
    draft["retest_plan"] = "按同一工况重新采集三帧压力。"
    result = assemble_proposal(value, draft)
    assert result["publication"]["state"] == "partial"
    assert result["retest_plan"] is None
    assert result["publication"]["rejected_sections"][0]["field_path"] == "retest_plan"
    draft["summary"] = "待重新采集压力结果确认后，当前方向才成立。"
    with pytest.raises(DomainError):
        assemble_proposal(value, draft)


def test_recording_multiple_question_titles_does_not_treat_response_as_imperative():
    value = frozen()
    value["unresolved_questions"].extend([
        {"question_id": "AIR-14", "name": "加压过程是否遵守最大0.5 bar"},
        {"question_id": "AIR-15", "name": "泄漏响应位于哪里"},
    ])
    draft = proposal()
    draft["steps"][1].update(question_ids=["AIR-14", "AIR-15"],
                              missing_question_ids=["AIR-14", "AIR-15"],
                              request="补充记录 AIR-14（加压过程是否遵守最大 0.5 bar）、AIR-15（泄漏响应位置）的结果。")
    assert assemble_proposal(value, draft)["publication"]["state"] == "complete"
    draft["steps"][1]["request"] = "补充记录后，请进行加压至 2 bar。"
    assert assemble_proposal(value, draft)["publication"]["state"] == "partial"


def test_invalid_step_is_not_executable_and_safety_is_not_discarded():
    draft = proposal()
    draft["steps"].append({"type": "controlled", "action_id": "UNKNOWN", "basis_observation_ids": ["air-fact"]})
    result = assemble_proposal(frozen(), draft)
    assert result["publication"]["state"] == "partial"
    assert len(result["steps"]) == 2
    draft["safety_notice"] = "建议加压至 2 bar。"
    with pytest.raises(DomainError):
        assemble_proposal(frozen(), draft)


def test_safety_hazard_description_does_not_authorize_execution():
    draft = proposal()
    draft["safety_notice"] = "加压可能造成器件损坏；不得据此实施加压。"
    assert assemble_proposal(frozen(), draft)["publication"]["state"] == "complete"
    draft["safety_notice"] = "建议加压至 2 bar。"
    with pytest.raises(DomainError):
        assemble_proposal(frozen(), draft)


def test_missing_or_wrong_facts_sources_and_rules_fail_closed():
    draft = proposal()
    draft["steps"][0]["basis_observation_ids"] = ["not-in-snapshot"]
    result = assemble_proposal(frozen(), draft)
    assert result["publication"]["state"] == "partial"
    draft = proposal()
    draft["supported_directions"][0]["editorial_rule_ids"] = ["not-frozen"]
    assert assemble_proposal(frozen(), draft)["publication"]["state"] == "partial"
    draft = proposal()
    draft["steps"][1]["question_ids"] = ["FAKE"]
    assert assemble_proposal(frozen(), draft)["publication"]["state"] == "partial"
    draft = proposal()
    draft["supported_directions"][0]["source_ids"] = ["C01-SRC-CHARGE-AIR-P5"]
    assert assemble_proposal(frozen(), draft)["publication"]["state"] == "partial"


def test_new_stub_uses_same_assembly_without_model(monkeypatch):
    monkeypatch.setenv("APP_MODE", "test")
    value = frozen()
    value["fault_description"] = "【C14-PARTIAL-STUB-ONLY · 模拟测试】"
    result = substitute_advice(value)
    assert result["publication"]["state"] == "partial"
    assert len(result["steps"]) == 2
    assert result["retest_plan"] is None
