"""B02 execution checks against the real service validators and projection."""
from uuid import uuid4

from app.services.workbench_b01_projection import project
from app.services.workbench_b01_service import TopicAnswer, TopicService
from app.topics import dkvb_b01, dkvb_b02


TOPIC, _ = dkvb_b02.catalog()
QUESTIONS = {q["id"]: q for q in TOPIC["questions"]}


def plan():
    return dkvb_b02.plan({"symptom_condition": "high_load", "safety_gate": "none"})


def record(qid, option, revision, *, fields=None, batch=None, round_id=None, supersedes=None):
    return {"id": uuid4(), "created_revision": revision, "supersedes_id": supersedes,
            "payload": {"question_id": qid, "option_ids": [option], "fields": fields or {},
                        "batch_id": batch, "round_id": round_id}}


def view(p, rows):
    return project({"intake_snapshot": {"topic_plan": p}}, rows,
                   {"available": False, "blocking_items": [{"code": "NO_EFFECTIVE_AREA"}]}, TOPIC)


def answer(qid, option, *, reason=""):
    return TopicAnswer(expected_revision=1, topic_version=TOPIC["version"], question_id=qid,
                       option_ids=[option], unavailable_reason=reason)


def test_old_identity_remains_frozen_and_b02_interpreter_checks_outcomes():
    old, old_hash = dkvb_b01.catalog()
    assert old["version"] == "2.2.0-b01" and len(old["questions"]) == 78
    assert dkvb_b02.binding()["content_hash"] != old_hash
    p = plan()
    not_ready = record("ACT-08", "voltage_low", 2)
    completed = answer("ACT-09", "completed", reason="无法操作")
    missing = TopicService._prerequisites(QUESTIONS["ACT-09"], p, [not_ready], completed)
    assert missing[0]["ref"] == "ACT-08" and "voltage_low" in missing[0]["reason"]
    assert TopicService._prerequisites(QUESTIONS["ACT-09"], p, [not_ready], answer("ACT-09", "unavailable", reason="电压不足")) == []
    assert TopicService._prerequisites(QUESTIONS["ACT-09"], p, [record("ACT-08", "ready", 3)], completed) == []
    # Existing B01-bound cases continue to use their original interpretation.
    old_act = next(q for q in old["questions"] if q["id"] == "ACT-09")
    assert TopicService._prerequisites(old_act, p, [not_ready], completed) == []
    assert set(TOPIC["execution_rules"]["conditional_operations"]) == {
        q["id"] for q in TOPIC["questions"] if q["answer_kind"] == "conditional_operation"}


def test_conditional_execution_needs_qualifying_result_not_any_record():
    p = plan()
    examples = (
        ("AIR-14", "within_limit", "AIR-13", "unavailable"),
        ("AIR-15", "connector", "AIR-14", "not_performed"),
        ("AIR-16", "audible_or_bubble", "AIR-15", "none"),
        ("ACT-10", "recovered", "ACT-09", "failed"),
        ("X-05", "moved_with_coil", "X-01", "none"),
    )
    for qid, option, ref, prior in examples:
        rows = [record(ref, prior, 2)]
        missing = TopicService._prerequisites(QUESTIONS[qid], p, rows, answer(qid, option, reason="随便填写的原因"))
        assert any(item["ref"] == ref for item in missing), qid
    assert TopicService._prerequisites(QUESTIONS["ACT-09"], p, [], answer("ACT-09", "not_supported")) == []


def test_derived_insufficiency_is_addressed_but_not_normal_or_repair_ready():
    p = plan()
    p["required_question_ids"] = ["PRS-01", "PRS-02", "PRS-03", "PRS-04", "PRS-07", "PRS-08", "PRS-09", "PRS-10", "PRS-11"]
    empty = view(p, [])
    assert empty["derived"]["PRS-04"]["option_id"] is None
    assert "PRS-04" in empty["synthesis"]["missing_question_ids"]
    rows = [record(qid, "unavailable", index) for index, qid in enumerate(("PRS-01", "PRS-02", "PRS-03", "PRS-07", "PRS-08", "PRS-09", "PRS-10"), 2)]
    result = view(p, rows)
    assert result["derived"]["PRS-04"]["option_id"] == "unavailable"
    assert result["derived"]["PRS-11"]["option_id"] == "unreliable"
    assert result["synthesis"]["missing_question_ids"] == []
    assert result["ai_readiness"]["ready_for_first_advice"] is True
    assert result["ai_readiness"]["advice_scope"] == "supplement_or_handoff"
    assert result["ai_readiness"]["repair_conclusion_supported"] is False
    assert result["final_report_gate"]["available"] is False


def test_saved_signal_changes_priority_without_moving_cards_or_erasing_turbo():
    p = plan()
    initial = view(p, [])
    assert [a["area_id"] for a in initial["areas"]] == [a["id"] for a in TOPIC["areas"]]
    assert [a["priority"] for a in initial["areas"]] == [1, 2, 3, 4, 5]
    batch = p["capture_batches"]["engine_off_static"]
    hpa = lambda value: {"hpa": {"value": value, "unit": "hPa absolute"}}
    rows = [record("PRS-01", "recorded", 2, fields=hpa(1005), batch=batch),
            record("PRS-02", "recorded", 3, fields=hpa(1450), batch=batch),
            record("PRS-03", "recorded", 4, fields=hpa(1008), batch=batch),
            record("TUR-01", "crack_clue", 5), record("TUR-07", "scrape", 6)]
    changed = view(p, rows)
    assert changed["areas"][1]["priority"] == 1
    assert changed["recommendation_rule"] == "R11-R13"
    assert changed["question_states"]["TUR-01"]["status"] == "saved"
    replacement = record("PRS-02", "recorded", 7, fields=hpa(1010), batch=batch, supersedes=rows[1]["id"])
    restored = view(p, [*rows, replacement])
    assert [a["area_id"] for a in restored["areas"]] == [a["area_id"] for a in changed["areas"]]
    assert restored["question_states"]["TUR-01"]["status"] == "saved"
    assert restored["areas"][3]["priority"] == 1  # independent external clue now leads
    sound_corrected = record("TUR-07", "none", 8, supersedes=rows[4]["id"])
    fallback = view(p, [*rows, replacement, sound_corrected])
    assert fallback["areas"][0]["priority"] == 1
    assert fallback["question_states"]["TUR-01"]["status"] == "saved"


def test_repair_correction_preserves_history_but_invalidates_retest_conclusion():
    p = plan()
    round_id = str(uuid4())
    p["rounds"] = [{"id": round_id, "batch_id": str(uuid4())}]
    action = record("RET-01", "reseat", 2, round_id=round_id)
    retest = record("RET-04", "recovered", 3, round_id=round_id)
    corrected = record("RET-01", "seal_or_hose", 4, round_id=round_id, supersedes=action["id"])
    result = view(p, [action, retest, corrected])
    assert result["active_round_id"] == round_id
    assert result["derived"]["RET-07"]["option_id"] == "critical"
    assert result["derived"]["RET-08"]["option_id"] == "handoff_unavailable"
    assert any(item["id"] == "C-RET-01-REVISION" for item in result["synthesis"]["conflicts"])
    none = record("RET-01", "none", 5, round_id=round_id, supersedes=corrected["id"])
    no_repair = view(p, [action, retest, corrected, none])
    assert no_repair["active_round_id"] is None
    assert "RET-07" not in no_repair["derived"]
    assert no_repair["question_states"]["RET-01"]["option_ids"] == ["none"]
    assert no_repair["question_states"]["PRS-01"]["status"] == "unanswered"


def test_actual_service_round_planner_never_opens_for_none_or_correction():
    p = plan()
    assert TopicService._repair_round(p, None, ["none"], None) is None
    assert p["rounds"] == []
    none = record("RET-01", "none", 2)
    round_id = TopicService._repair_round(p, none, ["reseat"], none["id"])
    assert round_id and len(p["rounds"]) == 1
    actual = record("RET-01", "reseat", 3, round_id=round_id)
    assert TopicService._repair_round(p, actual, ["seal_or_hose"], actual["id"]) == round_id
    assert TopicService._repair_round(p, actual, ["none"], actual["id"]) == round_id
    assert len(p["rounds"]) == 1
