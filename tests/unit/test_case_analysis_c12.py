"""C12 publication dependencies. Synthetic samples; no model or database calls."""

from copy import deepcopy

import pytest

from app.domain.case_analysis import CaseAdviceDraft
from app.domain.policies import DomainError
from app.legacy_execution.case_analysis import assemble_proposal, substitute_advice, validate_advice
from test_case_analysis_c09 import proposal, snapshot
from test_case_analysis_c07 import frozen, proposal as old_proposal


BAD_RETEST = "按同一可比工况重新采集三帧目标/实际压力，并与旧记录对照。"


def test_independent_analysis_survives_unsupported_retest_without_publishing_it():
    frozen = snapshot()
    draft = proposal()
    draft["retest_plan"] = BAD_RETEST
    published = assemble_proposal(frozen, draft)
    assert published["publication"]["state"] == "partial"
    assert published["publication"]["rejected_sections"] == [{
        "field_path": "retest_plan", "rule_id": "text.unsupported_operation",
        "reason": "具体技术操作只能由冻结 action_id 装配"}]
    assert published["retest_plan"] is None
    assert len(published["supported_directions"]) == 1
    assert len(published["steps"]) == 2
    assert BAD_RETEST not in str(published)
    assert validate_advice(frozen, published) == published


@pytest.mark.parametrize("field,text", [
    ("summary", "复检后压力仍偏低，当前方向已获支持。"),
    ("uncertainty", "仍需依据复检结果判断压力方向。"),
])
def test_conclusion_dependent_on_rejected_retest_is_not_published(field, text):
    draft = proposal()
    draft["retest_plan"] = BAD_RETEST
    draft[field] = text
    with pytest.raises(DomainError) as error:
        assemble_proposal(snapshot(), draft)
    assert error.value.details["rule_id"] == "publication.retest_content_dependency"


def test_valid_looking_step_dependent_on_rejected_retest_is_not_isolated():
    draft = proposal()
    draft["retest_plan"] = BAD_RETEST
    draft["steps"][1]["reason"] = "需依据复检结果决定要补记的压力证据。"
    with pytest.raises(DomainError) as error:
        assemble_proposal(snapshot(), draft)
    assert error.value.details["rule_id"] == "publication.retest_content_dependency"


def test_retest_with_unique_safety_boundary_cannot_be_discarded():
    draft = proposal()
    draft["retest_plan"] = "只有安全前提满足才能重新采集压力，否则必须停止。"
    with pytest.raises(DomainError) as error:
        assemble_proposal(snapshot(), draft)
    assert error.value.details["rule_id"] == "publication.retest_safety_dependency"


def test_frozen_air_excerpt_cannot_support_entire_cross_area_handoff():
    frozen = snapshot()
    draft = proposal()
    draft["steps"].append({"type": "handoff", "action": "将气路与压力记录交由技术人员核对。",
                           "reason": "当前仍有未核实的线索。",
                           "basis_observation_ids": ["air-fact", "pressure-fact"],
                           "source_ids": ["C01-SRC-CHARGE-AIR-P1"]})
    result = assemble_proposal(frozen, draft)
    assert result["publication"]["state"] == "partial"
    assert result["publication"]["rejected_sections"] == [{
        "field_path": "steps[2].source_ids", "rule_id": "source.applicability_unconfirmed",
        "reason": "该摘录只支持部分区域，不能作为跨区域交接内容的整体资料依据"}]
    assert len(result["steps"]) == 2
    air_only = deepcopy(draft)
    air_only["steps"][2]["basis_observation_ids"] = ["air-fact"]
    assert assemble_proposal(frozen, air_only)["publication"]["state"] == "complete"


def test_complete_advice_not_degraded_and_old_schema_remains_readable():
    published = assemble_proposal(snapshot(), proposal())
    assert published["publication"]["state"] == "complete"
    assert published["retest_plan"] == proposal()["retest_plan"]
    old = CaseAdviceDraft.model_validate(assemble_proposal(frozen(), old_proposal()))
    assert old.retest_plan == old_proposal()["retest_plan"]


def test_published_null_retest_cannot_claim_complete_or_hide_rejection():
    frozen = snapshot()
    published = assemble_proposal(frozen, proposal())
    published["retest_plan"] = None
    with pytest.raises(DomainError) as error:
        validate_advice(frozen, published)
    assert error.value.details["rule_id"] == "publication.retest_state"


def test_isolated_stub_uses_actual_assembly_and_default_stub_unchanged(monkeypatch):
    frozen = snapshot()
    frozen["fault_description"] = "【C12-RETEST-PARTIAL-STUB-ONLY · 模拟测试】"
    monkeypatch.setenv("APP_MODE", "test")
    result = substitute_advice(frozen)
    assert result["publication"]["state"] == "partial"
    assert result["publication"]["rejected_sections"][0]["field_path"] == "retest_plan"
    assert result["retest_plan"] is None
    assert result["steps"][0]["action_id"] == "CHECK_CHARGE_AIR_HOSE_SEATING_LEAK"
    monkeypatch.setenv("APP_MODE", "dev")
    assert substitute_advice(frozen)["publication"]["state"] == "complete"
