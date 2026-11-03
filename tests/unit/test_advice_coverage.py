"""Abnormal saved records an advice leaves without an action are listed for the user."""
from app.services.advice_coverage import unplanned_records

QUESTIONS = [
    {"id": "AIR-11", "options": [{"id": "normal", "outcome": "normal"}, {"id": "impact", "outcome": "abnormal"}]},
    {"id": "AIR-12", "options": [{"id": "normal", "outcome": "normal"}, {"id": "left", "outcome": "abnormal"}]},
    {"id": "AIR-13", "options": [{"id": "tool", "outcome": "normal"}, {"id": "none", "outcome": "unavailable"}]},
]
RECORDS = [
    {"id": "o11", "question_id": "AIR-11", "question": "中冷器外观", "option_ids": ["impact"], "option_labels": ["碰撞痕迹"]},
    {"id": "o12", "question_id": "AIR-12", "question": "左右接口", "option_ids": ["left"], "option_labels": ["左侧接口可疑"]},
    {"id": "o13", "question_id": "AIR-13", "question": "检漏能力", "option_ids": ["none"], "option_labels": ["无法检查"]},
]


def advice(**change):
    return {"summary": "s", "steps": [{"action": "处理左侧接口", "question_ids": ["AIR-12"],
                                       "basis_observation_ids": []}],
            "conditional_branches": [], "missing": [],
            # Mentioned only as another explanation: not a plan for the record.
            "directions": [{"title": "中冷器本体未判断", "basis_observation_ids": ["o11"]}], **change}


def test_abnormal_record_only_in_directions_is_unplanned():
    found = unplanned_records(advice(), RECORDS, QUESTIONS)
    assert [f["question_id"] for f in found] == ["AIR-11"]
    assert found[0]["option_labels"] == ["碰撞痕迹"]


def test_branch_steps_missing_entries_and_observation_ids_count_as_planned():
    branch = {"trigger": "t", "steps": [{"action": "a", "question_ids": [], "basis_observation_ids": ["o11"]}]}
    assert unplanned_records(advice(conditional_branches=[branch]), RECORDS, QUESTIONS) == []
    missing = [{"question_id": "AIR-11", "missing": "m"}]
    assert unplanned_records(advice(missing=missing), RECORDS, QUESTIONS) == []


def test_normal_unavailable_and_failed_results_need_nothing():
    assert unplanned_records(None, RECORDS, QUESTIONS) == []
    normal = [{**RECORDS[0], "option_ids": ["normal"]}]
    assert unplanned_records(advice(steps=[]), normal + [RECORDS[2]], QUESTIONS) == []
