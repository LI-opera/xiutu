"""Rule results shown on the page must reach the model unchanged, including "not computed yet"."""
import json
from unittest.mock import patch
from uuid import uuid4

from app.services.area_analysis_service import (
    MATCHED_RULES_PROMPT_VERSION,
    MATCHED_SYSTEM_PROMPT,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_input,
    build_matched_input,
)
from app.services.template_projection import build_plan, project_template

from scripts.build_analysis_context import RELATIONS


def topic():
    relation = json.loads(RELATIONS.read_text(encoding="utf-8"))["relations"][0]
    assert relation["template_id"] == "tayron-dkvb-p0299"
    return json.loads((RELATIONS.parent / relation["content_file"]).read_text(encoding="utf-8"))


def view_with(values):
    """values: question ID -> static hPa reading, saved in the plan's engine-off batch."""
    content = topic()
    plan = build_plan(content, {})
    batch = plan["capture_batches"]["engine_off_static"]
    records = [{"id": uuid4(), "supersedes_id": None, "payload": {
        "question_id": qid, "option_ids": ["recorded"], "batch_id": batch,
        "fields": {"hpa": {"value": value, "unit": "hPa absolute"}}}} for qid, value in values.items()]
    case = {"intake_snapshot": {"topic_plan": plan,
                                "template_binding": {"template_id": "tayron-dkvb-p0299", "version": "2"}}}
    projection = project_template(case, records, {}, content)
    return {"topic": content, "view": projection, "plan": plan, "case": {
        "id": str(uuid4()), "revision": 3, "vehicle": {}, "fault_description": "增压不足",
        "fault_codes": ["P0299"], "intake_snapshot": case["intake_snapshot"]},
        "observations": [{"id": str(row["id"]), "question_id": row["payload"]["question_id"],
                          "payload": row["payload"], "effective": True} for row in records]}, records


def no_reading_guide():
    # Reading-guide behaviour has its own tests; keep these focused on derived results.
    return patch("app.services.area_analysis_service.enrich", side_effect=lambda value, _: {
        **value, "unrecorded_decision_question_ids": [], "reference_reading_guide": {}})


def test_computed_outlier_reaches_area_input_with_its_basis():
    view, records = view_with({"PRS-01": 1008, "PRS-02": 1010, "PRS-03": 1180})
    shown = view["view"]["derived"]["PRS-04"]
    assert shown["option_id"] == "g71_outlier"
    with no_reading_guide():
        payload = build_input(view, "pressure", [])
    sent = {item["question_id"]: item for item in payload["derived_results"]}
    assert sent["PRS-04"]["option_id"] == shown["option_id"]
    assert sent["PRS-04"]["option_label"] == "G71离群"
    assert sent["PRS-04"]["evidence_state"] == "computed"
    assert sent["PRS-04"]["reason"] == shown["reason"]
    assert set(sent["PRS-04"]["basis_observation_ids"]) == {str(row["id"]) for row in records}
    # Derived questions are not facts the technician still has to collect.
    assert "PRS-04" not in payload["unknown_question_ids"]
    assert payload["prompt_version"] == PROMPT_VERSION


def test_uncomputed_result_is_sent_as_unknown_not_dropped():
    view, _ = view_with({"PRS-01": 1008, "PRS-02": 1010})
    with no_reading_guide():
        payload = build_input(view, "pressure", [])
    prs04 = next(item for item in payload["derived_results"] if item["question_id"] == "PRS-04")
    assert prs04["option_id"] is None and prs04["option_label"] is None
    assert prs04["evidence_state"] == "awaiting_input"


def test_matched_input_only_carries_results_of_included_areas():
    view, _ = view_with({"PRS-01": 1008, "PRS-02": 1010, "PRS-03": 1180})
    with no_reading_guide():
        payload = build_matched_input(view, {"pressure": []})
    area_of = {q["id"]: q["area_id"] for q in view["topic"]["questions"]}
    assert [a["id"] for a in payload["areas"]] == ["pressure"]
    assert payload["derived_results"]
    assert {area_of[item["question_id"]] for item in payload["derived_results"]} == {"pressure"}
    assert payload["prompt_version"] == MATCHED_RULES_PROMPT_VERSION


def test_prompts_explain_how_to_use_rule_results():
    for prompt in (SYSTEM_PROMPT, MATCHED_SYSTEM_PROMPT):
        assert "derived_results" in prompt
        assert "不用原始数值自行重算" in prompt
