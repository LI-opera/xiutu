"""RECOVERY-001: one bad checkpoint cannot block another case's worker."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text, update

from app.agents.state import ProposalContext
from app.domain.policies import DomainError
from app.infrastructure.orm import (
    cases, diagnosis_publications, diagnosis_steps, graph_progress,
    jobs, run_events, runs,
)
from test_document_ingest import docrig as docrig
from test_evidence_measurement import indexed_rig as indexed_rig
from test_wp10_proposals import synthetic_step
from test_wp12_turns import waiting, post


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.database


def test_bad_case_is_quarantined_and_other_case_worker_completes(indexed_rig):
    r = indexed_rig
    case_a, step_a, _, _ = waiting(r)
    case_b, step_b, cite_b, proposal_b = waiting(r)
    submitted = post(r, case_b, step_b)
    assert submitted.status_code == 202, submitted.text
    run_a, run_b = UUID(step_a["run_id"]), UUID(submitted.json()["run_id"])

    # A deterministic staged proposal gives B a real worker/recovery path
    # without any model request. The first worker dies before publication.
    first = r.store.claim_legacy("synthetic-case-b-staging", run_id=run_b)
    assert first is not None
    try:
        candidate = synthetic_step(cite_b)
        candidate["title"] = "跨病例隔离复核"
        candidate["actions"] = [dict(**cite_b("检查 P01 插头。"), operation="inspect")]
        checked = proposal_b.validate(ProposalContext(r.actor, case_b, 2), candidate)
        assert checked["accepted"], checked["issues"]
        r.store.stage_diagnosis(first, checked)
    finally:
        first.close()
    with r.store.engine.begin() as c:
        c.execute(update(jobs).where(jobs.c.run_id == run_b)
                  .values(lease_until=text("clock_timestamp() - interval '1 second'")))
        c.execute(update(graph_progress).where(graph_progress.c.run_id == run_a)
                  .values(phase="evaluating", workflow_id=uuid4()))
    with r.store.engine.connect() as c:
        a_pub = c.execute(select(diagnosis_publications).where(
            diagnosis_publications.c.run_id == run_a,
            diagnosis_publications.c.node == "publish")).mappings().one()
        a_before = c.execute(select(graph_progress).where(
            graph_progress.c.run_id == run_a)).mappings().one()
        a_step = c.execute(select(diagnosis_steps).where(
            diagnosis_steps.c.id == UUID(step_a["id"]))).mappings().one()
        a_job = c.execute(select(jobs).where(jobs.c.run_id == run_a)).mappings().one()
        b_before = c.execute(select(cases.c.revision).where(
            cases.c.id == case_b)).scalar_one()
        assert a_before["workflow_id"] != a_pub["workflow_id"]
        assert a_before["phase"] == "evaluating" and b_before == 2

    env = dict(os.environ, DATABASE_URL=os.environ["TEST_DATABASE_URL"],
               TEST_DATABASE_URL=os.environ["TEST_DATABASE_URL"],
               APP_MODE="test", RETRIEVAL_PROFILE="synthetic", TOOL_MODE="local",
               PYTHONPATH=str(ROOT / "backend"), XIUTU_WP11_PAID="0")
    for name in ("DEEPSEEK_API_KEY", "XIUTU_LOAD_PROJECT_ENV"):
        env.pop(name, None)
    runner = ("from uuid import UUID; from app.infrastructure.job_store import JobStore; "
              "from app.worker import Worker; import os,sys; "
              "s=JobStore(os.environ['TEST_DATABASE_URL']); "
              "assert Worker(s, legacy_execution=True).once(run_id=UUID(sys.argv[1])); s.close()")
    proc = subprocess.run([sys.executable, "-B", "-c", runner, str(run_b)],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=45)
    assert proc.returncode == 0, "Isolated worker failed; see private test log"

    with r.store.engine.connect() as c:
        a_after = c.execute(select(graph_progress).where(
            graph_progress.c.run_id == run_a)).mappings().one()
        a_run = c.execute(select(runs).where(runs.c.id == run_a)).mappings().one()
        a_pub_after = c.execute(select(diagnosis_publications).where(
            diagnosis_publications.c.id == a_pub["id"])).mappings().one()
        a_events = c.execute(select(run_events.c.type).where(
            run_events.c.run_id == run_a,
            run_events.c.type == "checkpoint.quarantined")).all()
        b_run = c.execute(select(runs).where(runs.c.id == run_b)).mappings().one()
        b_job = c.execute(select(jobs).where(jobs.c.run_id == run_b)).mappings().one()
        b_publications = c.execute(select(diagnosis_publications.c.id).where(
            diagnosis_publications.c.run_id == run_b,
            diagnosis_publications.c.node == "publish")).all()
        assert a_after["phase"] == "failed"
        assert a_after["workflow_id"] == a_before["workflow_id"]
        assert a_after["checkpoint_ref"] == a_before["checkpoint_ref"]
        assert a_pub_after["payload_hash"] == a_pub["payload_hash"]
        assert a_pub_after["output_revision"] == a_pub["output_revision"]
        assert a_run["status"] == "waiting_input"
        assert a_run["error_json"] == {"code": "CHECKPOINT_INCONSISTENT",
            "retryable": False, "recovery": "manual_review"}
        assert len(a_events) == 1
        assert c.execute(select(diagnosis_steps.c.status).where(
            diagnosis_steps.c.id == a_step["id"])).scalar_one() == a_step["status"]
        assert c.execute(select(jobs.c.status).where(
            jobs.c.id == a_job["id"])).scalar_one() == a_job["status"]
        assert b_run["status"] == "waiting_input"
        assert b_job["status"] == "completed" and b_job["attempt"] == 2
        assert len(b_publications) == 1
        assert c.execute(select(cases.c.revision).where(cases.c.id == case_b)).scalar_one() == 3

    # Direct inspection of A remains an explicit error; repeated global
    # recovery no longer revisits or rewrites the quarantined record.
    with pytest.raises(DomainError) as failure:
        r.store.reconcile_wait(run_a)
    assert failure.value.code == "CHECKPOINT_INCONSISTENT"
    # A fresh worker startup must also pass the retained anomaly without
    # replaying its publication or appending another quarantine event.
    startup_only = runner.replace("assert Worker(s, legacy_execution=True).once",
                                  "Worker(s, legacy_execution=True).once")
    again = subprocess.run([sys.executable, "-B", "-c", startup_only, str(run_b)],
                           cwd=ROOT, env=env, capture_output=True, text=True, timeout=45)
    assert again.returncode == 0, "Repeated worker startup was blocked"
    r.store.reconcile_pending()
    r.store.reconcile_pending()
    with r.store.engine.connect() as c:
        assert c.execute(select(graph_progress.c.phase).where(
            graph_progress.c.run_id == run_a)).scalar_one() == "failed"
        assert len(c.execute(select(run_events.c.id).where(
            run_events.c.run_id == run_a,
            run_events.c.type == "checkpoint.quarantined")).all()) == 1
        assert len(c.execute(select(diagnosis_publications.c.id).where(
            diagnosis_publications.c.run_id == run_b,
            diagnosis_publications.c.node == "publish")).all()) == 1
