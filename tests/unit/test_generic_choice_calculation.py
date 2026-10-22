from uuid import uuid4

import pytest
from app.domain.policies import DomainError
from app.services.template_projection import build_plan, project_template


def topic():
    def q(qid, kind, options):
        return {"id": qid, "area_id": "system", "answer_kind": kind,
                "options": [{"id": name, "outcome": "normal"} for name in options]}
    return {"version": "unrelated-v1", "areas": [{"id": "system"}],
            "questions": [q("A", "single_choice", ["yes", "no"]),
                          q("B", "single_choice", ["yes", "no"]),
                          q("RESULT", "automatic_derived", ["confirmed", "not_confirmed"])],
            "calculation_rules": {"version": "choice-v1", "rules": [{
                "question_id": "RESULT", "inputs": ["A", "B"], "cases": [
                    {"when": [{"question_id": "A", "option_ids": ["yes"]},
                              {"question_id": "B", "option_ids": ["yes"]}],
                     "option_id": "confirmed", "reason": "两项均已确认。"},
                    {"when": [{"question_id": "A", "option_ids": ["no"]}],
                     "option_id": "not_confirmed", "reason": "A 未确认。"},
                ]}]}}


def row(qid, option, *, supersedes=None):
    return {"id": uuid4(), "supersedes_id": supersedes,
            "payload": {"question_id": qid, "option_ids": [option]}}


def test_derived_choice_uses_effective_saved_records_and_correction():
    config = topic()
    case = {"intake_snapshot": {"topic_plan": build_plan(config, {})}}
    first = row("A", "yes")
    second = row("B", "yes")
    empty = project_template(case, [], config)
    assert empty["derived"]["RESULT"]["option_id"] is None
    assert empty["derived"]["RESULT"]["detail"]["evidence_state"] == "awaiting_input"
    computed = project_template(case, [first, second], config)
    assert computed["question_states"]["RESULT"]["option_ids"] == ["confirmed"]
    assert computed["question_states"]["RESULT"]["status"] == "derived"
    assert set(computed["derived"]["RESULT"]["basis_observation_ids"]) == {str(first["id"]), str(second["id"])}
    correction = row("A", "no", supersedes=first["id"])
    updated = project_template(case, [first, second, correction], config)
    assert updated["derived"]["RESULT"]["option_id"] == "not_confirmed"
    assert str(first["id"]) not in updated["derived"]["RESULT"]["basis_observation_ids"]
    assert not updated["ai_readiness"]["repair_conclusion_supported"]


def test_unmatched_and_incomplete_inputs_stay_unknown():
    config = topic()
    case = {"intake_snapshot": {"topic_plan": build_plan(config, {})}}
    one = project_template(case, [row("A", "no")], config)
    assert one["derived"]["RESULT"]["option_id"] is None
    unmatched = project_template(case, [row("A", "yes"), row("B", "no")], config)
    assert unmatched["derived"]["RESULT"]["option_id"] is None
    assert unmatched["derived"]["RESULT"]["detail"]["evidence_state"] == "no_matching_rule"


def test_invalid_or_legacy_style_rules_cannot_run_as_generic_calculation():
    config = topic()
    config["calculation_rules"]["rules"][0]["cases"][0]["when"][0]["question_id"] = "PRS-01"
    with pytest.raises(DomainError, match="模板派生规则配置无效"):
        build_plan(config, {})
    config = topic()
    config["calculation_rules"]["version"] = "2.2.1-b02"
    with pytest.raises(DomainError, match="模板派生规则配置无效"):
        build_plan(config, {})
