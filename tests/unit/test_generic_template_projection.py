from unittest.mock import patch
from uuid import uuid4

import pytest
from app.domain.policies import DomainError
from app.services.template_legacy_calculations import supports
from app.services.template_projection import build_plan, project_template


def template():
    def question(id, area, kind="single_choice"):
        return {"id": id, "area_id": area, "answer_kind": kind,
                "options": [{"id": "ok", "outcome": "normal"},
                            {"id": "fault", "outcome": "abnormal"},
                            {"id": "unknown", "outcome": "unavailable"}]}
    return {"version": "independent-1", "areas": [{"id": "cooling"}, {"id": "electrical"}],
            "questions": [question("coolant", "cooling"), question("voltage", "electrical"),
                          question("inferred", "electrical", "automatic_derived")]}


def test_arbitrary_template_has_no_legacy_calculation_or_plan_dependency():
    topic = template()
    topic["questions"][0]["capture"] = {"batch_kind": "cold_measurement", "batch_id_required": True}
    intake = {"safety_gate": "unprovided", "symptom_condition": "unprovided"}
    with patch("app.services.template_legacy_calculations.evaluate", side_effect=AssertionError("legacy called")), \
         patch("app.topics.dkvb_b02.plan", side_effect=AssertionError("legacy plan called")):
        plan = build_plan(topic, intake)
        assert set(plan["capture_batches"]) == {"cold_measurement"}
        assert plan["required_question_ids"] == ["coolant", "voltage"]
        case = {"intake_snapshot": {"topic_plan": plan}}
        empty = project_template(case, [], {}, topic)
        assert empty["synthesis"]["missing_question_ids"] == ["coolant", "voltage"]
        assert empty["derived"] == {}
        assert not empty["ai_readiness"]["ready_for_first_advice"]
        assert all(state["option_ids"] == [] for state in empty["question_states"].values())
        row = dict(id=uuid4(), supersedes_id=None, payload=dict(question_id="coolant", option_ids=["fault"]))
        fixed = dict(id=uuid4(), supersedes_id=row["id"], payload=dict(question_id="coolant", option_ids=["ok"]))
        missing = dict(id=uuid4(), supersedes_id=None, payload=dict(question_id="voltage", option_ids=["unknown"]))
        view = project_template(case, [row, fixed, missing], {"allowed": False}, topic)
        assert not view["synthesis"]["issues"]
        assert [item["question_id"] for item in view["synthesis"]["facts"]] == ["coolant"]
        assert [item["question_id"] for item in view["synthesis"]["unavailable"]] == ["voltage"]
        assert [area["recorded"] for area in view["areas"]] == [1, 1]
        assert view["question_states"]["inferred"]["option_ids"] == []
        assert view["final_report_gate"] == {"allowed": False}
        assert not view["ai_readiness"]["repair_conclusion_supported"]


def test_unknown_calculator_never_silently_runs_b02_rules():
    topic = {**template(), "calculation_catalog": {"version": "unknown"}}
    with pytest.raises(DomainError, match="模板计算规则版本尚不支持"):
        build_plan(topic, {})
    with pytest.raises(DomainError, match="模板计算规则版本尚不支持"):
        project_template({"intake_snapshot": {"topic_plan": {}}}, [], None, topic)


def test_legacy_calculator_requires_a_frozen_v1_template_identity():
    for code in ("p0299", "p0236"):
        assert supports({"topic_id": f"tayron-dkvb-{code}",
                         "version": f"tayron-dkvb-{code}-v1",
                         "calculation_catalog": {"version": "2.2.1-b02"}})
    with pytest.raises(DomainError, match="模板计算规则版本尚不支持"):
        supports({"topic_id": "unrelated", "version": "2.2.1-b02",
                  "calculation_catalog": {"version": "2.2.1-b02"}})
