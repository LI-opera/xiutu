"""Focused C01 source/scope checks; integration exercises the real task path."""

from copy import deepcopy

import pytest

from app.domain.policies import DomainError
from app.services.case_analysis_context import context_pack, selected_context
from app.services.case_analysis_actions import supported_actions
from app.legacy_execution.case_analysis import substitute_advice, validate_advice
from app.topics import dkvb_b02


def snapshot(scope="fact_review"):
    topic, _ = dkvb_b02.catalog()
    context = selected_context(topic, ["AIR-07"])
    return {"observations": [{"id": "observation-1", "question_id": "AIR-07",
                              "option_ids": ["partially_seated"]}],
            "source_context": context, "action_catalog": supported_actions(context),
            "allowed_scope": scope,
            "synthesis": {"unavailable": [], "missing_question_ids": [], "conflicts": []}}


def test_actual_manual_excerpt_and_substitute_use_same_validation():
    pack, digest = context_pack()
    assert len(digest) == 64
    assert pack["topic_version"] == dkvb_b02.TOPIC_VERSION
    assert "座合是否牢固" in pack["excerpts"][0]["text"]
    frozen = snapshot()
    content = validate_advice(frozen, substitute_advice(frozen))
    assert len(content["steps"]) == 1
    assert content["steps"][0]["action_id"] == "CHECK_CHARGE_AIR_HOSE_SEATING_LEAK"
    assert content["steps"][0]["source_ids"] == ["C01-SRC-CHARGE-AIR-P1"]
    assert "不能确诊" in content["uncertainty"]


def test_unavailable_scope_only_gives_handoff():
    frozen = snapshot("supplement_or_handoff")
    frozen["observations"] = []
    frozen["synthesis"]["unavailable"] = [{"question_id": "PRS-02"}]
    content = validate_advice(frozen, substitute_advice(frozen))
    assert all(step["action_id"] is None for step in content["steps"])
    assert not content["supported_directions"]


def test_unavailable_scope_rejects_supported_direction_even_with_valid_fact():
    frozen = snapshot("supplement_or_handoff")
    draft = substitute_advice(snapshot())
    with pytest.raises(DomainError) as error:
        validate_advice(frozen, draft)
    assert error.value.code == "ANALYSIS_SCOPE_EXCEEDED"


def test_rejects_fabricated_citation_or_beyond_scope_action():
    frozen = snapshot("supplement_or_handoff")
    draft = substitute_advice(frozen)
    draft["steps"][0]["source_ids"] = ["not-provided"]
    with pytest.raises(DomainError) as error:
        validate_advice(frozen, draft)
    assert error.value.code == "ANALYSIS_INVALID_SOURCE_REFERENCE"
    draft = substitute_advice(frozen)
    draft["steps"][0]["kind"] = "conditional_action"
    with pytest.raises(DomainError) as error:
        validate_advice(frozen, draft)
    assert error.value.code == "ANALYSIS_SCOPE_EXCEEDED"


def test_rejects_snapshot_unrelated_observation():
    frozen = snapshot()
    draft = deepcopy(substitute_advice(frozen))
    draft["supported_directions"][0]["basis_observation_ids"] = ["old-or-other-case"]
    with pytest.raises(DomainError) as error:
        validate_advice(frozen, draft)
    assert error.value.code == "ANALYSIS_INVALID_FACT_REFERENCE"


def test_unrelated_manual_cannot_support_operation():
    frozen = snapshot()
    draft = substitute_advice(frozen)
    draft["steps"][0]["source_ids"] = ["C01-SRC-CHARGE-AIR-P5"]
    with pytest.raises(DomainError) as error:
        validate_advice(frozen, draft)
    assert error.value.code == "ANALYSIS_ACTION_SOURCE_MISMATCH"
    draft = substitute_advice(frozen)
    draft["steps"][0]["action"] = "检查点火线圈并更换"
    with pytest.raises(DomainError) as error:
        validate_advice(frozen, draft)
    assert error.value.code == "ANALYSIS_ACTION_TEXT_MISMATCH"


def test_action_requires_qualifying_saved_fact():
    frozen = snapshot()
    frozen["observations"][0]["option_ids"] = ["seated"]
    draft = substitute_advice(snapshot())
    with pytest.raises(DomainError) as error:
        validate_advice(frozen, draft)
    assert error.value.code == "ANALYSIS_ACTION_FACT_MISSING"


@pytest.mark.parametrize("field,value", [
    ("summary", "本车已经确诊增压故障。"),
    ("retest_plan", "复检后可直接更换涡轮。"),
    ("safety_notice", "故障已排除。"),
    ("unconfirmed_directions", "必须更换点火线圈。"),
    ("direction_limit", "已有数据，确定故障根因，可换件。"),
    ("step_prerequisites", "先直接更换点火线圈。"),
    ("step_retest", "已排除故障，无需复检。"),
    ("step_stop_condition", "必须更换涡轮。"),
])
def test_claim_in_any_advice_field_is_rejected(field, value):
    frozen = snapshot()
    draft = substitute_advice(frozen)
    if field.startswith("step_"):
        frozen = snapshot("supplement_or_handoff")
        frozen["observations"] = []
        draft = substitute_advice(frozen)
    if field == "unconfirmed_directions":
        draft[field] = [value]
    elif field == "direction_limit":
        draft["supported_directions"][0]["limit"] = value
    elif field.startswith("step_"):
        draft["steps"][0][field.removeprefix("step_")] = value
    else:
        draft[field] = value
    with pytest.raises(DomainError) as error:
        validate_advice(frozen, draft)
    assert error.value.code == "ANALYSIS_UNSUPPORTED_CERTAINTY"


def test_negated_caution_is_not_misread_as_positive_claim():
    frozen = snapshot()
    draft = substitute_advice(frozen)
    draft["summary"] = "目前不能确诊；不能据此排除其他方向。"
    draft["retest_plan"] = "无处理事实，不能直接更换部件。"
    assert validate_advice(frozen, draft)["summary"] == draft["summary"]


def test_unlisted_technical_procedure_and_parameter_are_rejected():
    frozen = snapshot()
    draft = substitute_advice(frozen)
    draft["steps"].append({"kind": "check", "action": "检查点火线圈并进行基本设置",
                           "prerequisites": "现场安全", "basis_observation_ids": [],
                           "source_ids": ["C01-SRC-CHARGE-AIR-P1"], "retest": "记录结果",
                           "stop_condition": "条件不足时交接"})
    with pytest.raises(DomainError) as error:
        validate_advice(frozen, draft)
    assert error.value.code == "ANALYSIS_UNSUPPORTED_OPERATION"
    draft = substitute_advice(frozen)
    draft["safety_notice"] = "加压可至 1.0 bar。"
    with pytest.raises(DomainError) as error:
        validate_advice(frozen, draft)
    assert error.value.code == "ANALYSIS_UNSUPPORTED_OPERATION"
