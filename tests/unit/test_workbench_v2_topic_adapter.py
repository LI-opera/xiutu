"""Narrow contract checks for the first formal DKVB V2 vertical slice."""

import pytest
from pydantic import ValidationError

from app.domain.policies import DomainError
from app.agents.trusted_protocol import PROFILE
from app.services.observation_service import SubmitObservation
from app.services.workbench_v2_projection import project
from app.topics.dkvb_v2 import WIRED, applicable, binding, bound, catalog, validate_annotation


def case():
    return {"intake_snapshot": {"topic_binding": binding()},
            "diagnosis_mode": "conservative", "vehicle_json": PROFILE.copy(),
            "fault_codes": ["P0299"]}


def test_all_78_questions_are_versioned_and_only_explicit_pairs_are_writable():
    topic, digest = catalog()
    assert len(topic["questions"]) == 78
    assert len(topic["cards"]) == 34
    assert len(topic["areas"]) == 5
    assert binding()["content_hash"] == digest
    assert WIRED[("CHK-04", "air.seating_suspect")] == ("AIR-07", "partially_seated")
    assert ("CHK-04", "air.wall_damage") not in WIRED


def test_connector_answer_requires_bound_case_and_observation_basis():
    payload = {"check_id": "CHK-04", "option_id": "air.seating_suspect",
               "protocol_fields": {"object": "connector", "location": "中冷器右侧快插接头", "note": "卡簧未到止挡"}}
    annotation = validate_annotation(case(), payload, "AIR-07", "partially_seated", "2.0.0")
    assert annotation["topic_question_id"] == "AIR-07"
    assert annotation["topic_source"] == "SYNTHETIC_DEMO_TOPIC"
    with pytest.raises(DomainError):
        validate_annotation(case(), {**payload, "protocol_fields": {"object": "connector", "location": "右侧"}},
                            "AIR-07", "partially_seated", "2.0.0")
    with pytest.raises(DomainError):
        validate_annotation(case(), payload, "AIR-07", "seated", "2.0.0")
    changed = case()
    changed["intake_snapshot"]["topic_binding"] = {**binding(), "content_hash": "wrong"}
    assert not bound(changed)
    assert not applicable({**PROFILE, "engine_code": "OTHER"}, ["P0299"], "conservative")
    assert not applicable(PROFILE, ["P0236"], "conservative")


def test_retest_mapping_rejects_unrecovered_frames():
    fields = {"leak_result": "not_found", "symptom": "absent",
              **{f"target_{i}_hpa": "2000" for i in range(1, 4)},
              **{f"actual_{i}_hpa": "1950" for i in range(1, 4)}}
    payload = {"check_id": "CHK-07", "option_id": "retest.record", "protocol_fields": fields}
    assert validate_annotation(case(), payload, "RET-04", "recovered", "2.0.0")["topic_option_id"] == "recovered"
    with pytest.raises(DomainError):
        validate_annotation(case(), {**payload, "protocol_fields": {**fields, "symptom": "present"}},
                            "RET-04", "recovered", "2.0.0")


def test_topic_submission_metadata_is_atomic_shape():
    base = {"expected_revision": 1, "graph_epoch": 0,
            "step_id": "829bb4c8-0a59-4fd7-879d-b19868893cec", "kind": "choice",
            "option_id": "air.seating_suspect"}
    with pytest.raises(ValidationError):
        SubmitObservation.model_validate({**base, "topic_question_id": "AIR-07"})
    value = SubmitObservation.model_validate({**base, "topic_question_id": "AIR-07",
                                              "topic_option_id": "partially_seated", "topic_version": "2.0.0"})
    assert value.topic_option_id == "partially_seated"


def test_projection_uses_effective_observations_and_keeps_report_boundary():
    topic, _ = catalog()
    rows = [
        {"id": "old-air", "effective": False, "created_revision": 8,
         "payload": {"topic_question_id": "AIR-07", "topic_option_id": "partially_seated"}},
        {"id": "air", "effective": True, "created_revision": 10, "supersedes_id": "old-air",
         "payload": {"topic_question_id": "AIR-07", "topic_option_id": "partially_seated"}},
        {"id": "leak", "effective": True, "created_revision": 12,
         "payload": {"topic_question_id": "AIR-15", "topic_option_id": "connector"}},
        {"id": "repair", "effective": True, "created_revision": 14,
         "payload": {"topic_question_id": "RET-01", "topic_option_id": "reseat"}},
        {"id": "retest", "effective": True, "created_revision": 16,
         "payload": {"topic_question_id": "RET-04", "topic_option_id": "recovered"}},
    ]
    diagnosis = {"current_step": {"validation": {"protocol": {
        "next_check_id": "CHK-11", "observation_id": "retest",
        "presentation": {"completion_explanation": "待最终复核"},
    }}}}
    result = project(topic, {"status": "waiting_input"}, diagnosis, {"items": rows})
    air = next(area for area in result["areas"] if area["area_id"] == "boost-air")
    assert air["recorded_questions"] == 2
    assert air["needs_review"]
    assert len(result["synthesis"]["confirmed_facts"]) == 4
    assert {issue["question_id"] for issue in result["synthesis"]["issues"]} == {"AIR-07", "AIR-15"}
    assert "合成演示小结" in result["synthesis"]["current_explanation"]
    assert result["synthesis"]["supporting_observation_id"] == "retest"


def test_initial_area_order_uses_saved_intake_not_later_checks():
    topic, _ = catalog()
    intake = {"id": "intake", "effective": True, "kind": "choice",
              "payload": {"check_id": "CHK-01", "protocol_fields": {
                  "symptom_conditions": "intermittent"}}}
    case_data = {"status": "waiting_input", "fault_codes": ["P0299"]}
    initial = project(topic, case_data, {}, {"items": [intake]})
    assert min(initial["areas"], key=lambda area: area["priority"])["area_id"] == "pressure"
    later = {"id": "later", "effective": True, "kind": "choice",
             "payload": {"topic_question_id": "AIR-07", "topic_option_id": "partially_seated"}}
    after_check = project(topic, case_data, {}, {"items": [intake, later]})
    assert [(area["area_id"], area["priority"]) for area in after_check["areas"]] == [
        (area["area_id"], area["priority"]) for area in initial["areas"]]
