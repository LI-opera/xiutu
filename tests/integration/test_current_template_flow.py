"""Current template flow over HTTP, with no model submission or existing-case edits."""

from uuid import uuid4

import pytest
from app.infrastructure.orm import area_reference_bindings
from sqlalchemy import select

from test_document_ingest import docrig  # Reuse the isolated API/auth process fixture.

pytestmark = pytest.mark.database


def post(rig, path, body):
    response = rig.client.post(path, json=body, headers={
        **rig.headers, "Idempotency-Key": uuid4().hex,
    })
    assert response.status_code in (200, 201), (path, response.status_code, response.text)
    return response.json()


def get(rig, path):
    response = rig.client.get(path)
    assert response.status_code == 200, (path, response.status_code, response.text)
    return response.json()


def simple_question(topic, area_id):
    """Choose by question capabilities rather than vehicle-specific IDs."""
    for question in topic["questions"]:
        if (question.get("area_id") == area_id
                and question["answer_kind"] == "single_choice"
                and not question.get("execution_conditions")
                and not (question.get("capture") or {}).get("batch_id_required")
                and not question.get("fields")
                and not (question.get("prerequisites") or {}).get("refs")
                and len(question["options"]) >= 2):
            return question
    raise AssertionError(f"No independent choice in area {area_id}")


@pytest.mark.parametrize("fault_code,expected_areas", [("P0299", 5), ("P0236", 3)])
def test_two_templates_save_correct_analysis_input_repair_retest_and_reload(
    docrig, fault_code, expected_areas,
):
    case = post(docrig, "/api/v2/cases", {
        "workbench_flow": "template-match-v1",
        "vehicle": {"brand": "大众", "model": "探岳", "year": 2019, "engine_code": "DKVB"},
        "fault_description": f"隔离回归 {fault_code} {uuid4().hex}",
        "fault_codes": [fault_code],
    })
    case_id = case["id"]
    base = f"/api/v2/cases/{case_id}"
    view = get(docrig, base + "/workbench-v2")
    topic = view["topic"]
    assert len(topic["areas"]) == expected_areas
    assert view["case"]["intake_snapshot"]["template_binding"]["template_id"]
    assert get(docrig, base + "/matched-areas/analysis")["recorded"] == 0

    first, second = topic["areas"][:2]
    question = simple_question(topic, first["id"])
    other = simple_question(topic, second["id"])
    binding = view["case"]["intake_snapshot"]["template_binding"]

    def reference_ids(area_ids):
        with docrig.store.engine.connect() as conn:
            rows = conn.execute(select(area_reference_bindings.c.document_id).where(
                area_reference_bindings.c.template_id == binding["template_id"],
                area_reference_bindings.c.template_version == binding["version"],
                area_reference_bindings.c.area_id.in_(area_ids),
            )).all()
        return {row[0] for row in rows}

    def answer(q, option_id, *, original=None):
        nonlocal view
        path = base + "/topic-observations"
        if original:
            path += f"/{original}/correct"
        result = post(docrig, path, {
            "expected_revision": view["case"]["revision"],
            "topic_version": topic["version"],
            "question_id": q["id"], "option_ids": [option_id],
        })
        view = result["view"]
        return result["observation_id"]

    old_id = answer(question, question["options"][0]["id"])
    analysis = get(docrig, base + "/matched-areas/analysis")
    assert analysis["recorded"] == 1
    assert [a["id"] for a in analysis["areas"]] == [first["id"]]
    assert {d["id"] for d in analysis["documents"]} == reference_ids([first["id"]])

    new_id = answer(question, question["options"][1]["id"], original=old_id)
    answer(other, other["options"][0]["id"])
    analysis = get(docrig, base + "/matched-areas/analysis")
    assert analysis["recorded"] == 2
    assert {a["id"] for a in analysis["areas"]} == {first["id"], second["id"]}
    assert {o["id"] for o in analysis["observations"]}.isdisjoint({old_id})
    assert new_id in {o["id"] for o in analysis["observations"]}
    assert {d["id"] for d in analysis["documents"]} == reference_ids([
        first["id"], second["id"],
    ])

    before = get(docrig, base + "/workbench-v2")
    repairs = post(docrig, base + "/template-repairs", {
        "expected_revision": before["case"]["revision"],
        "area_id": first["id"], "repair_action": "隔离回归：记录已完成的处理动作",
    })
    assert len(repairs["rounds"]) == 1
    round_id = repairs["rounds"][0]["id"]
    retested = post(docrig, base + f"/template-repairs/{round_id}/retest", {
        "expected_revision": repairs["revision"],
        "retest_condition": "same", "retest_outcome": "uncertain",
        "retest_evidence": "隔离回归：复检结果仍需后续确认",
        "next_area_id": second["id"],
        "observations": [{"question_id": question["id"],
                          "option_ids": [question["options"][0]["id"]]}],
    })
    assert retested["rounds"][0]["next_area_id"] == second["id"]
    assert retested["rounds"][0]["retest_outcome"] == "uncertain"

    reloaded = get(docrig, base + "/workbench-v2")
    history = get(docrig, base + "/topic-observations/history")
    assert reloaded["case"]["revision"] == retested["revision"]
    # The re-check supersedes the pre-repair answer instead of hiding in free text.
    recheck = next(o for o in reloaded["observations"]
                   if o["effective"] and o["question_id"] == question["id"])
    assert recheck["id"] not in {old_id, new_id}
    assert recheck["supersedes_id"] == new_id
    assert recheck["payload"]["repair_round_id"] == round_id
    assert recheck["payload"]["option_ids"] == [question["options"][0]["id"]]
    assert {o["id"] for o in history["items"]} >= {old_id, new_id, recheck["id"]}
    sent = next(o for o in get(docrig, base + "/matched-areas/analysis")["observations"]
                if o["question_id"] == question["id"])
    assert sent["after_repair_round_id"] == round_id
    assert sent["before_repair"]["id"] == new_id
    assert get(docrig, base + "/template-repairs")["rounds"][0]["id"] == round_id
    assert get(docrig, base + "/matched-areas/analysis")["recorded"] == 2
