"""Actual treatments and retests reach the model, with every record marked before or after them."""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.services.area_analysis_service import (
    MATCHED_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_input,
    build_matched_input,
    input_identity,
    load_repair_rounds,
)
from app.services.template_projection import build_plan, project_template

from scripts.build_analysis_context import RELATIONS


def topic():
    relation = json.loads(RELATIONS.read_text(encoding="utf-8"))["relations"][0]
    return json.loads((RELATIONS.parent / relation["content_file"]).read_text(encoding="utf-8"))


def repair(area_id, pre_repair_revision, outcome=None):
    return {"id": str(uuid4()), "area_id": area_id, "repair_action": "更换中冷器出口软管卡箍",
            "repair_note": "原卡箍断裂", "pre_repair_revision": pre_repair_revision,
            "retest_status": "retested" if outcome else "pending",
            "retest_condition": "same" if outcome else None, "retest_outcome": outcome,
            "retest_evidence": "同路况试车仍增压不足" if outcome else None, "next_area_id": None,
            "created_at": "2026-10-21T08:00:00+00:00",
            "retested_at": "2026-10-21T09:00:00+00:00" if outcome else None}


def view_with(saved, rounds=()):
    """saved: (question ID, created revision) pairs, all answered with the first option."""
    content = topic()
    plan = build_plan(content, {})
    qmap = {q["id"]: q for q in content["questions"]}
    records = [{"id": uuid4(), "supersedes_id": None, "created_revision": revision,
                "payload": {"question_id": qid, "option_ids": [qmap[qid]["options"][0]["id"]]}}
               for qid, revision in saved]
    case = {"intake_snapshot": {"topic_plan": plan,
                                "template_binding": {"template_id": "tayron-dkvb-p0299", "version": "2"}}}
    return {"topic": content, "view": project_template(case, records, {}, content), "plan": plan,
            "case": {"id": str(uuid4()), "revision": 12, "vehicle": {}, "fault_description": "增压不足",
                     "fault_codes": ["P0299"], "intake_snapshot": case["intake_snapshot"]},
            "observations": [{"id": str(row["id"]), "question_id": row["payload"]["question_id"],
                              "payload": row["payload"], "created_revision": row["created_revision"],
                              "effective": True} for row in records],
            "repair_rounds": list(rounds)}


def no_reading_guide():
    return patch("app.services.area_analysis_service.enrich", side_effect=lambda value, _: {
        **value, "unrecorded_decision_question_ids": [], "reference_reading_guide": {}})


def test_records_are_marked_before_or_after_each_repair_round():
    first, second = repair("boost-air", 4, "persists"), repair("boost-air", 8)
    view = view_with([("AIR-01", 3), ("AIR-02", 6), ("AIR-03", 9)], [first, second])
    with no_reading_guide():
        payload = build_input(view, "boost-air", [])
    marks = {o["question_id"]: o["after_repair_round_id"] for o in payload["observations"]}
    assert marks == {"AIR-01": None, "AIR-02": first["id"], "AIR-03": second["id"]}
    assert payload["repair_rounds"] == [first, second]
    assert payload["repair_rounds"][1]["retest_status"] == "pending"


def test_other_areas_rounds_stay_out_and_no_rounds_changes_nothing_else():
    view = view_with([("AIR-01", 3)], [repair("pressure", 4)])
    with no_reading_guide():
        payload = build_input(view, "boost-air", [])
    assert payload["repair_rounds"] == []
    assert payload["observations"][0]["after_repair_round_id"] is None


def test_area_with_only_a_repair_round_joins_the_combined_analysis():
    treated = repair("pressure", 4, "resolved")
    view = view_with([("AIR-01", 3)], [treated])
    with no_reading_guide():
        payload = build_matched_input(view, {"boost-air": [], "pressure": []})
    areas = {area["id"]: area for area in payload["areas"]}
    assert set(areas) == {"boost-air", "pressure"}
    assert areas["pressure"]["observation_ids"] == []
    assert areas["pressure"]["repair_round_ids"] == [treated["id"]]
    assert payload["repair_rounds"] == [treated]


def test_recording_a_retest_makes_earlier_advice_outdated():
    pending = repair("boost-air", 4)
    retested = {**pending, "retest_status": "retested", "retest_condition": "same",
                "retest_outcome": "persists", "retest_evidence": "仍增压不足",
                "retested_at": "2026-10-21T09:00:00+00:00"}
    with no_reading_guide():
        before = build_input(view_with([("AIR-01", 3)], [pending]), "boost-air", [])
        after = build_input(view_with([("AIR-01", 3)], [retested]), "boost-air", [])
    before["case_id"] = after["case_id"]
    for item in (before, after):
        item["observations"][0]["id"] = "same-record"
    assert input_identity(before) != input_identity(after)


def test_loaded_rounds_are_plain_json_in_time_order():
    created = datetime(2026, 10, 21, 8, tzinfo=timezone.utc)
    rows = [{"id": uuid4(), "area_id": "boost-air", "repair_action": "更换卡箍", "repair_note": "",
             "pre_repair_revision": 4, "retest_condition": "different", "retest_outcome": "resolved",
             "retest_evidence": "怠速未再报码", "next_area_id": None, "created_at": created,
             "retested_at": created + timedelta(hours=1)}]
    conn = SimpleNamespace(execute=lambda _: SimpleNamespace(
        mappings=lambda: SimpleNamespace(all=lambda: rows)))
    loaded = load_repair_rounds(conn, uuid4())
    assert loaded[0]["id"] == str(rows[0]["id"])
    assert loaded[0]["retest_status"] == "retested"
    assert loaded[0]["retested_at"] == "2026-10-21T09:00:00+00:00"
    json.dumps(loaded)


def test_prompts_explain_before_after_and_unconfirmed_retests():
    for prompt in (SYSTEM_PROMPT, MATCHED_SYSTEM_PROMPT):
        assert "repair_rounds" in prompt and "after_repair_round_id" in prompt
        assert "不能视为已确认解决" in prompt


def test_rechecked_record_keeps_its_pre_repair_value_for_comparison():
    treated = repair("boost-air", 4, "persists")
    view = view_with([("AIR-02", 3)], [treated])
    original = view["observations"][0]
    question = next(q for q in view["topic"]["questions"] if q["id"] == "AIR-02")
    view["observations"] = [{**original, "effective": False}, {
        "id": str(uuid4()), "question_id": "AIR-02", "effective": True, "created_revision": 6,
        "supersedes_id": original["id"],
        "payload": {"question_id": "AIR-02", "option_ids": [question["options"][1]["id"]],
                    "repair_round_id": treated["id"]}}]
    with no_reading_guide():
        payload = build_input(view, "boost-air", [])
    sent = payload["observations"][0]
    assert sent["after_repair_round_id"] == treated["id"]
    assert sent["option_ids"] == [question["options"][1]["id"]]
    assert sent["before_repair"]["id"] == original["id"]
    assert sent["before_repair"]["option_labels"] == [question["options"][0]["label"]]


def test_a_correction_made_before_the_repair_is_not_a_before_after_pair():
    view = view_with([("AIR-02", 3)], [repair("boost-air", 8)])
    original = view["observations"][0]
    question = next(q for q in view["topic"]["questions"] if q["id"] == "AIR-02")
    view["observations"] = [{**original, "effective": False}, {
        "id": str(uuid4()), "question_id": "AIR-02", "effective": True, "created_revision": 5,
        "supersedes_id": original["id"],
        "payload": {"question_id": "AIR-02", "option_ids": [question["options"][1]["id"]]}}]
    with no_reading_guide():
        sent = build_input(view, "boost-air", [])["observations"][0]
    assert sent["after_repair_round_id"] is None and sent["before_repair"] is None
