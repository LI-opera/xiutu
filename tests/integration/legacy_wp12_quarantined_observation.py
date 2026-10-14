"""RECOVERY-001: a quarantined published turn is not usable as new input."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update

from app.infrastructure.orm import (
    cases, diagnosis_publications, diagnosis_steps, graph_progress,
    idempotency_keys, jobs, observations, run_events, runs,
)
from test_document_ingest import docrig as docrig
from test_evidence_measurement import indexed_rig as indexed_rig
from test_wp12_turns import waiting


pytestmark = pytest.mark.database


def quarantine(r, run_id):
    with r.store.engine.begin() as c:
        c.execute(update(graph_progress).where(graph_progress.c.run_id == run_id)
                  .values(phase="evaluating", workflow_id=uuid4()))
    r.store.reconcile_pending()
    with r.store.engine.connect() as c:
        assert c.execute(select(graph_progress.c.phase).where(
            graph_progress.c.run_id == run_id)).scalar_one() == "failed"
        assert c.execute(select(runs.c.error_json).where(runs.c.id == run_id)).scalar_one() == {
            "code": "CHECKPOINT_INCONSISTENT", "retryable": False,
            "recovery": "manual_review"}


def snapshot(r, case_id, step_id, run_id):
    with r.store.engine.connect() as c:
        return (
            c.execute(select(cases.c.revision, cases.c.status).where(
                cases.c.id == case_id)).one(),
            c.execute(select(diagnosis_steps.c.status).where(
                diagnosis_steps.c.id == step_id)).scalar_one(),
            c.execute(select(func.count()).select_from(observations).where(
                observations.c.case_id == case_id)).scalar_one(),
            tuple(c.execute(select(runs.c.id).where(runs.c.case_id == case_id)
                .order_by(runs.c.id)).scalars()),
            tuple(c.execute(select(jobs.c.id).join(runs, runs.c.id == jobs.c.run_id)
                .where(runs.c.case_id == case_id).order_by(jobs.c.id)).scalars()),
            tuple(c.execute(select(run_events.c.id).where(run_events.c.case_id == case_id)
                .order_by(run_events.c.id)).scalars()),
            c.execute(select(func.count()).select_from(idempotency_keys).where(
                idempotency_keys.c.actor_id == r.actor,
                idempotency_keys.c.route_scope ==
                f"POST /api/v2/cases/{case_id}/observations")).scalar_one(),
            c.execute(select(graph_progress.c.phase, graph_progress.c.checkpoint_ref).where(
                graph_progress.c.run_id == run_id)).one(),
            c.execute(select(diagnosis_publications.c.payload_hash).where(
                diagnosis_publications.c.run_id == run_id,
                diagnosis_publications.c.node == "publish")).scalar_one(),
        )


def request(r, case_id, step_id, key):
    return r.client.post(f"/api/v2/cases/{case_id}/observations",
        headers=dict(r.headers, **{"Idempotency-Key": key}),
        json={"expected_revision": 1, "graph_epoch": 0,
              "step_id": str(step_id), "kind": "choice", "choice_index": 0})


def test_quarantined_parent_rejects_new_and_repeated_http_submission(indexed_rig):
    r = indexed_rig
    case_id, step, _, _ = waiting(r)
    step_id, run_id = UUID(step["id"]), UUID(step["run_id"])
    quarantine(r, run_id)
    before = snapshot(r, case_id, step_id, run_id)
    key = uuid4().hex
    for use_key in (key, key, uuid4().hex):
        response = request(r, case_id, step_id, use_key)
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "CHECKPOINT_QUARANTINED"
        assert snapshot(r, case_id, step_id, run_id) == before
    current = r.client.get(f"/api/v2/cases/{case_id}/diagnosis", headers=r.headers)
    assert current.status_code == 200
    assert current.json()["current_step"]["id"] == str(step_id)
    saved_run = r.client.get(f"/api/v2/runs/{run_id}", headers=r.headers)
    assert saved_run.status_code == 200
    assert saved_run.json()["error"]["code"] == "CHECKPOINT_INCONSISTENT"
    assert saved_run.json()["error"]["recovery"] == "manual_review"


def test_old_successful_key_cannot_replay_as_current_after_quarantine(indexed_rig):
    r = indexed_rig
    case_id, step, _, _ = waiting(r)
    step_id, run_id = UUID(step["id"]), UUID(step["run_id"])
    key = uuid4().hex
    first = request(r, case_id, step_id, key)
    assert first.status_code == 202, first.text
    quarantine(r, run_id)
    before = snapshot(r, case_id, step_id, run_id)
    replay = request(r, case_id, step_id, key)
    assert replay.status_code == 409, replay.text
    assert replay.json()["error"]["code"] == "CHECKPOINT_QUARANTINED"
    assert snapshot(r, case_id, step_id, run_id) == before


def test_quarantine_does_not_turn_read_only_area_or_public_resume_into_writes(indexed_rig):
    r = indexed_rig
    case_id, step, _, _ = waiting(r)
    step_id, run_id = UUID(step["id"]), UUID(step["run_id"])
    quarantine(r, run_id)
    before = snapshot(r, case_id, step_id, run_id)
    activate = r.client.post(
        f"/api/v2/cases/{case_id}/diagnosis/areas/{step['area_id']}/activate",
        headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
        json={"expected_revision": 1, "graph_epoch": 0})
    assert activate.status_code == 200 and activate.json()["mode"] == "read_only"
    resume = r.client.post(f"/api/v2/cases/{case_id}/diagnosis/resume",
        headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
        json={"expected_revision": 1, "observation_id": str(uuid4())})
    assert resume.status_code == 409
    assert resume.json()["error"]["code"] == "OBSERVATION_SUBMIT_REQUIRED"
    assert snapshot(r, case_id, step_id, run_id) == before
