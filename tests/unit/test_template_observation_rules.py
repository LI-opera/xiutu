"""One frozen rule evaluation feeds projection and model-input context."""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.services.area_analysis_service import build_matched_input
from app.services.template_projection import build_plan, project_template
from app.services.workbench_topic_workflow import ObservationWorkflow


def topic():
    def question(qid, area, options, kind="single_choice", conditions=None):
        return {"id": qid, "area_id": area, "title": qid, "answer_kind": kind,
                "options": [{"id": option, "label": option, "outcome":
                             "unavailable" if option == "unable" else "abnormal" if option == "fault" else "normal"}
                            for option in options], "fields": [], "execution_conditions": conditions,
                "prerequisites": {"refs": ["SOURCE"] if conditions else []}, "source_refs": []}
    return {"version": "cooling-v1", "areas": [
        {"id": "cooling", "title": "冷却", "description": "记录冷却事实"},
        {"id": "electrical", "title": "电气", "description": "记录电气事实"}],
        "questions": [question("SOURCE", "cooling", ["ok", "fault"]),
                      question("CHECK", "electrical", ["done", "unable"],
                               kind="conditional_operation", conditions={
                                   "bypass_options": ["unable"], "requirements": [
                                       {"ref": "SOURCE", "allowed": ["ok"], "label": "确认来源状态"}]}),
                      question("SECOND", "electrical", ["ok", "fault"])],
        "observation_rules": {"version": "observation-v1", "focus_rules": [
            {"id": "focus-electrical", "all": [{"question_id": "SOURCE", "option_ids": ["fault"]}],
             "question_ids": ["CHECK", "SECOND"]}], "conflict_rules": [
            {"id": "cross-conflict", "all": [
                {"question_id": "SOURCE", "option_ids": ["fault"]},
                {"question_id": "SECOND", "option_ids": ["fault"]}],
             "reason": "两项异常并存，先核对共同条件。"}]}}


def test_focus_conflict_and_gate_are_consistent_in_saved_view_and_ai_preview():
    content = topic()
    records = [{"id": uuid4(), "supersedes_id": None,
                "payload": {"question_id": qid, "option_ids": [option]}}
               for qid, option in (("SOURCE", "fault"), ("SECOND", "fault"))]
    case = {"intake_snapshot": {"topic_plan": build_plan(content, {}),
                                "template_binding": {"template_id": "cooling", "version": "1"}}}
    projection = project_template(case, records, {}, content)
    assert projection["question_states"]["CHECK"]["focused"]
    assert projection["question_states"]["CHECK"]["condition_blockers"][0]["ref"] == "SOURCE"
    assert projection["synthesis"]["conflicts"][0]["id"] == "cross-conflict"

    full_view = {"topic": content, "view": projection, "case": {
        "id": str(uuid4()), "revision": 2, "vehicle": {}, "fault_description": "待查",
        "fault_codes": [], "intake_snapshot": case["intake_snapshot"]},
        "plan": case["intake_snapshot"]["topic_plan"],
        "observations": [{"id": str(row["id"]), "question_id": row["payload"]["question_id"],
                          "payload": row["payload"], "effective": True} for row in records]}
    with patch("app.services.area_analysis_service.enrich", side_effect=lambda value, _: {
        **value, "unrecorded_decision_question_ids": [], "reference_reading_guide": {}}):
        payload = build_matched_input(full_view, {"cooling": [], "electrical": []})
    assert {entry["id"] for entry in payload["questions"]} == {"SOURCE", "CHECK", "SECOND"}
    check = next(entry for entry in payload["questions"] if entry["id"] == "CHECK")
    assert check["suggested_focus"]
    assert check["execution_blockers"] == projection["question_states"]["CHECK"]["condition_blockers"]
    assert payload["rule_conflicts"] == projection["synthesis"]["conflicts"]
    assert payload["prompt_version"] == "matched-area-advice-v11"


def test_independent_operation_can_use_case_intake_safety_without_legacy_question():
    content = topic()
    operation = content["questions"][1]
    operation["prerequisites"] = {"refs": []}
    operation["execution_conditions"] = {
        "bypass_options": ["unable"], "requirements": [
            {"intake_key": "safety_gate", "allowed": ["none", "caution"], "label": "接诊安全条件允许操作"}]}
    workflow = ObservationWorkflow(content, template_bound=True)
    stop = build_plan(content, {"safety_gate": "stop_now"})
    allowed = build_plan(content, {"safety_gate": "none"})
    body = SimpleNamespace(option_ids=["done"])
    assert workflow.prerequisites(operation, stop, [], body)[0]["ref"] == "intake:safety_gate"
    assert workflow.prerequisites(operation, allowed, [], body) == []
    assert workflow.prerequisites(operation, stop, [], SimpleNamespace(option_ids=["unable"])) == []
    projection = project_template({"intake_snapshot": {"topic_plan": stop}}, [], None, content)
    assert projection["question_states"]["CHECK"]["condition_blockers"][0]["ref"] == "intake:safety_gate"
