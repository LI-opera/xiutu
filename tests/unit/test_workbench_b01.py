"""Focused B01 contract checks; no model, network, or business DB."""
from uuid import uuid4

import pytest

from app.domain.policies import DomainError
from app.services.workbench_b01_projection import project
from app.services.workbench_b01_service import TopicAnswer, TopicService
from app.topics.dkvb_b01 import catalog, plan


def fresh():
    return plan({"symptom_condition": "high_load", "safety_gate": "none"})


def record(qid, option, revision, *, fields=None, batch=None, supersedes=None):
    return {"id": uuid4(), "supersedes_id": supersedes, "created_revision": revision,
            "payload": {"question_id": qid, "option_ids": [option], "fields": fields or {},
                        "batch_id": batch, "round_id": None}}


def view(p, rows):
    return project({"intake_snapshot": {"topic_plan": p}}, rows,
                   {"available": False, "blocking_items": [{"code": "NO_EFFECTIVE_AREA"}]})


def test_all_78_have_formal_treatment_and_first_advice_excludes_retest():
    topic, _ = catalog()
    assert len(topic["questions"]) == len({q["id"] for q in topic["questions"]}) == 78
    assert {q["answer_kind"] for q in topic["questions"]} == {
        "single_choice", "multi_choice", "numeric_with_choice", "automatic_derived", "conditional_operation"}
    assert all(q["options"] and q["phase"] and q["submission_semantics"] for q in topic["questions"])
    p = fresh()
    assert not any(qid.startswith("RET-") or qid == "ACT-10" for qid in p["required_question_ids"])
    assert len(view(p, [])["question_states"]) == 78
    assert "RET-08" not in view(p, [])["derived"]


def test_raw_static_correction_recomputes_pressure_without_clearing_turbo():
    p = fresh(); batch = p["capture_batches"]["engine_off_static"]
    fields = lambda value: {"hpa": {"value": value, "unit": "hPa absolute"}}
    ambient = record("PRS-01", "recorded", 2, fields=fields(1005), batch=batch)
    g31 = record("PRS-02", "recorded", 3, fields=fields(1010), batch=batch)
    g71 = record("PRS-03", "recorded", 4, fields=fields(1008), batch=batch)
    turbo = record("TUR-01", "crack_clue", 5)
    before = view(p, [ambient, g31, g71, turbo])
    assert before["derived"]["PRS-04"]["option_id"] == "consistent"
    replacement = record("PRS-02", "recorded", 6, fields=fields(1450), batch=batch, supersedes=g31["id"])
    after = view(p, [ambient, g31, g71, turbo, replacement])
    assert after["derived"]["PRS-04"]["option_id"] == "g31_outlier"
    assert after["question_states"]["TUR-01"]["observation_id"] == str(turbo["id"])
    assert after["derived"]["D-PRESSURE-EVIDENCE"]["option_id"] is None
    assert any(item["question_id"] == "TUR-01" for item in after["synthesis"]["issues"])


def test_pressure_trend_stays_raw_but_ceases_to_be_credible_after_static_correction():
    p = fresh()
    static_batch = p["capture_batches"]["engine_off_static"]
    load_batch = p["capture_batches"]["comparable_load_frames"]
    hpa = lambda value: {"hpa": {"value": value, "unit": "hPa absolute"}}
    rows = [record("PRS-01", "recorded", 2, fields=hpa(1005), batch=static_batch),
            record("PRS-02", "recorded", 3, fields=hpa(1010), batch=static_batch),
            record("PRS-03", "recorded", 4, fields=hpa(1008), batch=static_batch),
            record("PRS-07", "comparable", 5), record("TUR-01", "crack_clue", 6)]
    for offset, qid in enumerate(("PRS-08", "PRS-09", "PRS-10"), 7):
        fields = {"target": {"value": 2100, "unit": "hPa absolute"},
                  "actual": {"value": 1740, "unit": "hPa absolute"}}
        rows.append(record(qid, "recorded", offset, fields=fields, batch=load_batch))
    before = view(p, rows)
    assert before["derived"]["PRS-11"]["option_id"] == "persistent_underboost"
    assert before["derived"]["D-PRESSURE-EVIDENCE"]["option_id"] == "credible"
    assert before["derived"]["TUR-09"]["option_id"] == "multiple_supporting_facts"
    replacement = record("PRS-02", "recorded", 10, fields=hpa(1450), batch=static_batch,
                         supersedes=rows[1]["id"])
    after = view(p, [*rows, replacement])
    assert after["derived"]["PRS-11"]["option_id"] == "persistent_underboost"
    assert after["derived"]["D-PRESSURE-EVIDENCE"]["option_id"] is None
    assert after["derived"]["TUR-09"]["option_id"] == "weak_support"
    assert after["question_states"]["TUR-01"]["observation_id"] == str(rows[4]["id"])


def test_multiple_cross_system_directions_and_unavailable_reason():
    p = fresh()
    rows = [record("X-01", "cyl1", 2), record("X-05", "moved_with_coil", 3),
            record("X-06", "low_pressure", 4), record("X-09", "low_level", 5)]
    result = view(p, rows)["derived"]["X-13"]
    assert result["option_id"] == "multiple"
    assert result["detail"]["supported_directions"] == ["ignition", "fuel"]
    topic, _ = catalog()
    answer = TopicAnswer(expected_revision=1, topic_version=topic["version"],
                         question_id="AIR-07", option_ids=["unavailable"])
    assert TopicService._validate_answer(topic, p, [], answer)[2]
    # A missing reason is persisted as a truthful system marker, not invented
    # as a tool or safety failure; a supplied reason cannot bypass prerequisites.
    action = TopicAnswer(expected_revision=1, topic_version=topic["version"],
                         question_id="AIR-14", option_ids=["within_limit"],
                         unavailable_reason="没有工具")
    assert TopicService._prerequisites(next(q for q in topic["questions"] if q["id"] == "AIR-14"), p, [], action)


def test_multi_choice_empty_is_unselected_not_normal():
    topic, _ = catalog(); p = fresh()
    blank = TopicAnswer(expected_revision=1, topic_version=topic["version"], question_id="IN-07", option_ids=[])
    assert TopicService._validate_answer(topic, p, [], blank)[1] == {}
    current = record("IN-07", "boost_pipe", 2)
    cleared = record("IN-07", "boost_pipe", 3, supersedes=current["id"])
    cleared["payload"]["option_ids"] = []
    result = view(p, [current, cleared])
    assert result["question_states"]["IN-07"]["status"] == "unanswered"
    assert not any(item["question_id"] == "IN-07" for item in result["synthesis"]["facts"])
    conflict = TopicAnswer(expected_revision=1, topic_version=topic["version"], question_id="IN-07",
                           option_ids=["none_known", "boost_pipe"])
    with pytest.raises(DomainError) as exc:
        TopicService._validate_answer(topic, p, [], conflict)
    assert exc.value.code == "OPTION_CONFLICT"


def test_required_scope_uses_saved_rule_triggers_not_browsing_or_optional_record():
    p = fresh()
    p["expanded_area_ids"].append("turbo")  # Browser/legacy marker alone adds nothing new.
    baseline = set(view(p, [])["plan_evaluation"]["required_question_ids"])
    assert "TUR-02" not in baseline
    ordinary = view(p, [record("TUR-01", "normal", 2)])
    assert set(ordinary["plan_evaluation"]["required_question_ids"]) == baseline
    assert ordinary["areas"][3]["recorded"] == 1
    leak = view(p, [record("AIR-13", "available", 2)])
    assert {"AIR-14", "AIR-15"} <= set(leak["plan_evaluation"]["required_question_ids"])
    assert "AIR-16" not in leak["plan_evaluation"]["required_question_ids"]
    signal = view(p, [record("PRS-02", "signal_missing", 2)])
    assert {"PRS-05", "PRS-06"} <= set(signal["plan_evaluation"]["required_question_ids"])
    p["required_question_ids"].append("TUR-02")  # Existing case plan is not cleared.
    assert "TUR-02" in view(p, [])["plan_evaluation"]["required_question_ids"]


def test_unavailable_and_stopped_operation_do_not_carry_measurement_fields():
    topic, _ = catalog(); p = fresh()
    answer = TopicAnswer(expected_revision=1, topic_version=topic["version"],
                         question_id="PRS-01", option_ids=["unavailable"],
                         fields={"hpa": {"value": 1005, "unit": "hPa absolute"}})
    with pytest.raises(DomainError) as exc:
        TopicService._validate_answer(topic, p, [], answer)
    assert exc.value.code == "FIELD_NOT_APPLICABLE"
    answer.question_id = "PRS-02"; answer.option_ids = ["signal_missing"]
    with pytest.raises(DomainError) as exc:
        TopicService._validate_answer(topic, p, [], answer)
    assert exc.value.code == "FIELD_NOT_APPLICABLE"
    answer.question_id = "AIR-14"; answer.option_ids = ["unsafe_stop"]; answer.fields = {}
    assert TopicService._validate_answer(topic, p, [], answer)[1] == {}


def test_numeric_unit_and_derived_submission_rejected():
    topic, _ = catalog(); p = fresh()
    answer = TopicAnswer(expected_revision=1, topic_version=topic["version"],
                         question_id="PRS-02", option_ids=["recorded"],
                         batch_id=p["capture_batches"]["engine_off_static"],
                         fields={"hpa": {"value": 1010, "unit": "bar"}})
    with pytest.raises(DomainError) as exc:
        TopicService._validate_answer(topic, p, [], answer)
    assert exc.value.code == "UNIT_MISMATCH"
    answer.fields = {"hpa": {"value": 1010, "unit": "hPa absolute"}}
    assert TopicService._validate_answer(topic, p, [], answer)[1]["hpa"]["value"] == 1010
    answer.question_id = "PRS-04"; answer.option_ids = ["consistent"]
    with pytest.raises(DomainError) as exc:
        TopicService._validate_answer(topic, p, [], answer)
    assert exc.value.code == "QUESTION_DERIVED"


def test_repair_action_is_not_a_current_diagnostic_abnormality():
    p = fresh()
    round_id = str(uuid4())
    p["rounds"].append({"id": round_id, "batch_id": str(uuid4())})
    action = record("RET-01", "reseat", 2)
    action["payload"]["round_id"] = round_id
    result = view(p, [action])
    assert all(item["question_id"] != "RET-01" for item in result["synthesis"]["issues"])
    assert result["derived"]["RET-07"]["option_id"] == "critical"
    assert result["ai_readiness"]["ready_for_first_advice"] is False


def test_pre_repair_question_remains_visible_if_recorded_after_retest_opened():
    p = fresh()
    round_id = str(uuid4())
    p["rounds"].append({"id": round_id, "batch_id": str(uuid4())})
    previous_bug_record = record("PRS-05", "normal", 4)
    previous_bug_record["payload"]["round_id"] = round_id
    result = view(p, [previous_bug_record])
    assert result["question_states"]["PRS-05"]["observation_id"] == str(previous_bug_record["id"])
    assert TopicService._effective([previous_bug_record], "PRS-05", None) == previous_bug_record
