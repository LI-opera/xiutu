"""WP-11 current-turn publication on a real isolated PostgreSQL database."""

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import httpx
import pytest
from app.legacy_execution.graph import DiagnosisGraph
from app.agents.state import ProposalContext
from app.config import Settings
from app.domain.policies import DomainError
from app.infrastructure.job_store import JobStore, LeaseLost
from app.infrastructure.orm import (
    cases,
    diagnosis_publications,
    diagnosis_steps,
    graph_progress,
    observations,
    run_events,
    runs,
)
from app.services.diagnosis_service import DiagnosisService, ResumeDiagnosis, StartDiagnosis
from app.services.run_service import RunService
from sqlalchemy import select, text, update
from test_document_ingest import docrig as docrig
from test_evidence_measurement import indexed_rig as indexed_rig
from test_wp10_proposals import FIX, prepare, synthetic_step

pytestmark = pytest.mark.database
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _normal_worker_lease(indexed_rig):
    # The shared ingest fixture uses a 2-second lease for its own expiry tests.
    # These graph tests perform synchronous proposal validation after claiming;
    # real workers heartbeat throughout that work and use a 60-second lease.
    indexed_rig.store.lease_seconds = 60


def test_start_publish_wait_and_replay(indexed_rig):
    r = indexed_rig
    content = (FIX / "extra-synthetic.md").read_bytes() + "\n检查 P01 插头。\n".encode()
    _, case, ctx, svc, cite = prepare(r, content)
    settings = Settings(app_mode="test", retrieval_profile="synthetic")
    r.store.settings = settings
    service = DiagnosisService(r.store.engine)
    cid = UUID(case["id"])
    key = uuid4().hex
    status, started = service.start(r.actor, cid, StartDiagnosis(expected_revision=0), key)
    assert status == 202 and started["status"] == "queued"
    assert service.start(r.actor, cid, StartDiagnosis(expected_revision=0), key) == (status, started)
    path = f"/api/v2/cases/{cid}/diagnosis/runs"
    headers = dict(r.headers, **{"Idempotency-Key": key})
    replay = r.client.post(path, headers=headers, json={"expected_revision": 0})
    assert replay.status_code == 202 and replay.json() == started
    assert r.client.post(path, headers={"Origin": r.headers["Origin"],
                                         "Idempotency-Key": uuid4().hex},
                         json={"expected_revision": 0}).status_code == 403
    with httpx.Client(base_url=r.headers["Origin"], trust_env=False) as unauthenticated:
        assert unauthenticated.post(path, headers=headers,
                                    json={"expected_revision": 0}).status_code == 401
    with pytest.raises(DomainError) as wrong:
        service.start(uuid4(), cid, StartDiagnosis(expected_revision=0), uuid4().hex)
    assert wrong.value.code == "NOT_FOUND"
    run_id = UUID(started["run_id"])
    lease = r.store.claim_legacy("wp11-publisher", run_id=run_id)
    assert lease is not None
    try:
        candidate = synthetic_step(cite)
        result = svc.validate(ProposalContext(r.actor, cid, 0), candidate)
        assert result["accepted"], result["issues"]
        r.store.stage_diagnosis(lease, result)
        assert r.store.staged_diagnosis(lease)["candidate"] == result["candidate"]
        r.store.finish(lease, result=result)
        r.store.finish(lease, result=result)
        changed = dict(result, candidate=dict(result["candidate"], title="不同的同轮输出"))
        with pytest.raises(DomainError) as conflict:
            r.store.finish(lease, result=changed)
        assert conflict.value.code == "PUBLICATION_CONFLICT"
    finally:
        lease.close()
    current = service.current(r.actor, cid)
    assert current["revision"] == 1 and current["status"] == "waiting_input"
    assert current["current_step"]["candidate"] == result["candidate"]
    with r.store.engine.connect() as c:
        assert c.execute(select(cases.c.revision).where(cases.c.id == cid)).scalar_one() == 1
        assert c.execute(select(runs.c.status).where(runs.c.id == run_id)).scalar_one() == "waiting_input"
        assert len(c.execute(select(diagnosis_steps.c.id).where(diagnosis_steps.c.case_id == cid)).all()) == 1
        assert len(c.execute(select(diagnosis_publications.c.id).where(diagnosis_publications.c.case_id == cid)).all()) == 1
        assert len(c.execute(select(run_events.c.id).where(run_events.c.run_id == run_id,
                            run_events.c.type == "run.waiting_input")).all()) == 1
        assert c.execute(select(graph_progress.c.phase).where(
            graph_progress.c.run_id == run_id)).scalar_one() == "evaluating"
    # Simulate process loss after the business COMMIT but before checkpoint.
    assert service.current(r.actor, cid)["current_step"] is not None
    r.store.reconcile_pending()
    with r.store.engine.connect() as c:
        assert c.execute(select(graph_progress.c.phase).where(
            graph_progress.c.run_id == run_id)).scalar_one() == "waiting_input"
    first_step = current["current_step"]
    observation_id = uuid4()
    with r.store.engine.begin() as c:
        c.execute(observations.insert().values(
            id=observation_id, case_id=cid, area_id=UUID(first_step["area_id"]),
            step_id=UUID(first_step["id"]), kind="choice",
            payload={"selected": "observed"}, created_revision=1, actor_id=r.actor,
        ))
    resume_key = uuid4().hex
    resume = ResumeDiagnosis(expected_revision=1, observation_id=observation_id)
    resumed = service.resume(r.actor, cid, resume, resume_key)
    assert resumed[0] == 202 and resumed[1]["run_id"] != str(run_id)
    assert service.resume(r.actor, cid, resume, resume_key) == resumed
    with pytest.raises(DomainError) as invalid:
        service.resume(r.actor, cid, ResumeDiagnosis(expected_revision=1,
                                                     observation_id=uuid4()), uuid4().hex)
    assert invalid.value.code == "NOT_WAITING"
    second_run = UUID(resumed[1]["run_id"])
    second_lease = r.store.claim_legacy("wp11-resumer", run_id=second_run)
    assert second_lease is not None
    try:
        next_candidate = synthetic_step(cite)
        next_candidate["title"] = "插头观察"
        next_candidate["actions"] = [dict(**cite("检查 P01 插头。"), operation="inspect")]
        next_ctx = ProposalContext(r.actor, cid, 1)
        next_result = svc.validate(next_ctx, next_candidate)
        assert next_result["accepted"], next_result["issues"]
        r.store.stage_diagnosis(second_lease, next_result)
        DiagnosisGraph(r.store, second_lease, Event()).execute()
    finally:
        second_lease.close()
    with r.store.engine.connect() as c:
        states = c.execute(select(diagnosis_steps.c.status).where(
            diagnosis_steps.c.case_id == cid).order_by(diagnosis_steps.c.ordinal)).scalars().all()
        assert states == ["completed", "waiting_input"]
    assert service.current(r.actor, cid)["revision"] == 2


def test_case_lock_wait_crosses_database_lease_and_rolls_back(indexed_rig, database_url):
    r = indexed_rig
    _, case, ctx, svc, cite = prepare(r, (FIX / "extra-synthetic.md").read_bytes())
    settings = Settings(app_mode="test", retrieval_profile="synthetic")
    short = JobStore(database_url, lease_seconds=2, settings=settings)
    cid = UUID(case["id"])
    run_id = UUID(DiagnosisService(short.engine).start(
        r.actor, cid, StartDiagnosis(expected_revision=0), uuid4().hex)[1]["run_id"])
    lease = short.claim_legacy("old-wp11-worker", run_id=run_id)
    assert lease is not None
    result = svc.validate(ctx, synthetic_step(cite))
    assert result["accepted"]
    short.stage_diagnosis(lease, result)
    observed_blocker = False
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        with r.store.engine.connect() as blocker:
            with blocker.begin():
                blocker.execute(select(cases.c.id).where(cases.c.id == cid).with_for_update()).one()
                blocker_pid = blocker.execute(text("select pg_backend_pid()")).scalar_one()
                future = pool.submit(short.finish, lease, result=result)
                until = time.monotonic() + 5
                with r.store.engine.connect() as observer:
                    while time.monotonic() < until:
                        blockers = observer.execute(
                            text("select pg_blocking_pids(:pid)"), {"pid": lease.pid}
                        ).scalar_one()
                        if blocker_pid in blockers:
                            observed_blocker = True
                            break
                        time.sleep(0.02)
                    assert observed_blocker, "Real PG case-row wait was not observed"
                    while time.monotonic() < until:
                        expired = observer.execute(
                            text("select clock_timestamp() >= :deadline"),
                            {"deadline": lease.job["lease_until"]}
                        ).scalar_one()
                        if expired:
                            break
                        time.sleep(0.02)
                    assert expired, "Database clock did not cross lease deadline"
            with pytest.raises(LeaseLost):
                future.result(timeout=6)
    finally:
        pool.shutdown(wait=True)
        lease.close()
    with short.engine.connect() as c:
        assert c.execute(select(cases.c.revision).where(cases.c.id == cid)).scalar_one() == 0
        assert c.execute(select(diagnosis_steps.c.id).where(diagnosis_steps.c.case_id == cid)).first() is None
        assert c.execute(select(diagnosis_publications.c.id).where(
            diagnosis_publications.c.case_id == cid)).first() is None
    replacement = short.claim_legacy("new-wp11-worker", run_id=run_id)
    assert replacement is not None and replacement.job["lease_token"] > lease.job["lease_token"]
    try:
        assert short.staged_diagnosis(replacement)["candidate"] == result["candidate"]
        short.finish(replacement, result=result)
    finally:
        replacement.close()
        short.close()
    assert DiagnosisService(r.store.engine).current(r.actor, cid)["revision"] == 1


def test_staged_candidate_recovers_in_a_new_worker_process(indexed_rig, database_url):
    r = indexed_rig
    _, case, ctx, svc, cite = prepare(r, (FIX / "extra-synthetic.md").read_bytes())
    short = JobStore(database_url, lease_seconds=1,
                     settings=Settings(app_mode="test", retrieval_profile="synthetic"))
    cid = UUID(case["id"])
    run_id = UUID(DiagnosisService(short.engine).start(
        r.actor, cid, StartDiagnosis(expected_revision=0), uuid4().hex)[1]["run_id"])
    old = short.claim_legacy("interrupted-before-publication", run_id=run_id)
    assert old is not None
    candidate = svc.validate(ctx, synthetic_step(cite))
    assert candidate["accepted"]
    short.stage_diagnosis(old, candidate)
    deadline = old.job["lease_until"]
    old.close()  # Releases only this test attempt's advisory lock.
    until = time.monotonic() + 5
    with short.engine.connect() as c:
        while time.monotonic() < until:
            if c.execute(text("select clock_timestamp() >= :deadline"),
                         {"deadline": deadline}).scalar_one():
                break
            time.sleep(0.02)
        else:
            raise AssertionError("Test lease did not expire")
    env = dict(os.environ, DATABASE_URL=str(database_url), TEST_DATABASE_URL=str(database_url),
               PYTHONPATH=str(ROOT / "backend"), PYTHONDONTWRITEBYTECODE="1",
               APP_MODE="test", RETRIEVAL_PROFILE="synthetic", TOOL_MODE="local")
    for name in ["DEEPSEEK_API_KEY", "XIUTU_WP11_PAID", "XIUTU_LOAD_PROJECT_ENV"]:
        env.pop(name, None)
    process_code = (
        "import os; from uuid import UUID; "
        "from app.infrastructure.job_store import JobStore; "
        "from app.worker import Worker; "
        "s=JobStore(os.environ['DATABASE_URL']); "
        f"assert Worker(s, legacy_execution=True).once(run_id=UUID('{run_id}')); s.close()"
    )
    proc = subprocess.run([sys.executable, "-B", "-c", process_code],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, "Worker process failed without leaking its raw output"
    assert DiagnosisService(short.engine).current(r.actor, cid)["revision"] == 1
    with short.engine.connect() as c:
        assert c.execute(select(graph_progress.c.phase).where(
            graph_progress.c.run_id == run_id)).scalar_one() == "waiting_input"
    short.close()


def test_graph_interrupt_and_saved_observation_resume(indexed_rig):
    r = indexed_rig
    _, case, ctx, svc, cite = prepare(r, (FIX / "extra-synthetic.md").read_bytes()
                                      + "\n检查 P01 插头。\n".encode())
    r.store.settings = Settings(app_mode="test", retrieval_profile="synthetic")
    service = DiagnosisService(r.store.engine)
    cid = UUID(case["id"])
    first_id = UUID(service.start(r.actor, cid, StartDiagnosis(expected_revision=0),
                                  uuid4().hex)[1]["run_id"])
    first = r.store.claim_legacy("wp11-graph-first", run_id=first_id)
    assert first is not None
    try:
        result = svc.validate(ctx, synthetic_step(cite))
        assert result["accepted"]
        r.store.stage_diagnosis(first, result)
        DiagnosisGraph(r.store, first, Event()).execute()
    finally:
        first.close()
    r.store.reconcile_wait(first_id)
    current = service.current(r.actor, cid)
    assert current["status"] == "waiting_input" and current["revision"] == 1
    step = current["current_step"]
    observation_id = uuid4()
    with r.store.engine.begin() as c:
        c.execute(observations.insert().values(
            id=observation_id, case_id=cid, area_id=UUID(step["area_id"]),
            step_id=UUID(step["id"]), kind="choice", payload={"selected": "observed"},
            created_revision=1, actor_id=r.actor))
    resumed_id = UUID(service.resume(r.actor, cid,
        ResumeDiagnosis(expected_revision=1, observation_id=observation_id),
        uuid4().hex)[1]["run_id"])
    second = r.store.claim_legacy("wp11-graph-second", run_id=resumed_id)
    assert second is not None
    try:
        next_candidate = synthetic_step(cite)
        next_candidate["title"] = "插头观察"
        next_candidate["actions"] = [dict(**cite("检查 P01 插头。"), operation="inspect")]
        next_result = svc.validate(ProposalContext(r.actor, cid, 1), next_candidate)
        assert next_result["accepted"]
        r.store.stage_diagnosis(second, next_result)
        DiagnosisGraph(r.store, second, Event()).execute()
    finally:
        second.close()
    r.store.reconcile_wait(resumed_id)
    assert service.current(r.actor, cid)["revision"] == 2
    print("SYNTHETIC WP11: first step waiting_input -> saved observation -> "
          "second persisted step waiting_input; revision 0 -> 1 -> 2")


def test_cancelled_attempt_cannot_publish_or_checkpoint(indexed_rig):
    r = indexed_rig
    _, case, ctx, svc, cite = prepare(r, (FIX / "extra-synthetic.md").read_bytes())
    r.store.settings = Settings(app_mode="test", retrieval_profile="synthetic")
    cid = UUID(case["id"])
    run_id = UUID(DiagnosisService(r.store.engine).start(
        r.actor, cid, StartDiagnosis(expected_revision=0), uuid4().hex)[1]["run_id"])
    lease = r.store.claim_legacy("wp11-cancel", run_id=run_id)
    assert lease is not None
    try:
        result = svc.validate(ctx, synthetic_step(cite))
        assert result["accepted"]
        r.store.stage_diagnosis(lease, result)
        RunService(r.store.engine).cancel(r.actor, run_id, uuid4().hex)
        r.store.finish(lease, result=result)
        graph = DiagnosisGraph(r.store, lease, Event())
        with pytest.raises(LeaseLost):
            graph.saver.get_tuple({"configurable": {"thread_id": graph.saver.workflow_id}})
    finally:
        lease.close()
    with r.store.engine.connect() as c:
        assert c.execute(select(cases.c.revision).where(cases.c.id == cid)).scalar_one() == 0
        assert c.execute(select(runs.c.status).where(runs.c.id == run_id)).scalar_one() == "cancelled"
        assert c.execute(select(diagnosis_steps.c.id).where(
            diagnosis_steps.c.case_id == cid)).first() is None


def test_late_publication_sql_rolls_back_complete_turn(indexed_rig, database_url):
    r = indexed_rig
    _, case, ctx, svc, cite = prepare(r, (FIX / "extra-synthetic.md").read_bytes())
    short = JobStore(database_url, lease_seconds=2,
                     settings=Settings(app_mode="test", retrieval_profile="synthetic"))
    cid = UUID(case["id"])
    run_id = UUID(DiagnosisService(short.engine).start(
        r.actor, cid, StartDiagnosis(expected_revision=0), uuid4().hex)[1]["run_id"])
    lease = short.claim_legacy("wp11-slow-sql", run_id=run_id)
    assert lease is not None
    result = svc.validate(ctx, synthetic_step(cite))
    assert result["accepted"]
    short.stage_diagnosis(lease, result)
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        with r.store.engine.connect() as blocker:
            with blocker.begin():
                blocker.execute(text("LOCK TABLE diagnosis_steps IN ACCESS EXCLUSIVE MODE"))
                blocker_pid = blocker.execute(text("SELECT pg_backend_pid()")).scalar_one()
                future = pool.submit(short.finish, lease, result=result)
                observed_wait = False
                expired = False
                until = time.monotonic() + 5
                with r.store.engine.connect() as observer:
                    while time.monotonic() < until:
                        if blocker_pid in observer.execute(
                            text("SELECT pg_blocking_pids(:pid)"), {"pid": lease.pid}
                        ).scalar_one():
                            observed_wait = True
                            break
                        time.sleep(0.02)
                    assert observed_wait, "Real late publication SQL wait was not observed"
                    while time.monotonic() < until:
                        expired = observer.execute(
                            text("SELECT clock_timestamp() >= :deadline"),
                            {"deadline": lease.job["lease_until"]}
                        ).scalar_one()
                        if expired:
                            break
                        time.sleep(0.02)
                    assert expired, "Database time did not cross the lease deadline"
            with pytest.raises(LeaseLost):
                future.result(timeout=6)
    finally:
        pool.shutdown(wait=True)
        lease.close()
        short.close()
    with r.store.engine.connect() as c:
        assert c.execute(select(cases.c.revision).where(cases.c.id == cid)).scalar_one() == 0
        assert c.execute(select(diagnosis_steps.c.id).where(
            diagnosis_steps.c.case_id == cid)).first() is None
        assert c.execute(select(diagnosis_publications.c.id).where(
            diagnosis_publications.c.case_id == cid)).first() is None


def test_turn_deadline_crossed_during_publish_sql_rolls_back(indexed_rig):
    r = indexed_rig
    _, case, ctx, svc, cite = prepare(r, (FIX / "extra-synthetic.md").read_bytes())
    r.store.settings = Settings(app_mode="test", retrieval_profile="synthetic")
    cid = UUID(case["id"])
    run_id = UUID(DiagnosisService(r.store.engine).start(
        r.actor, cid, StartDiagnosis(expected_revision=0), uuid4().hex)[1]["run_id"])
    lease = r.store.claim_legacy("wp11-turn-deadline", run_id=run_id)
    assert lease is not None
    result = svc.validate(ctx, synthetic_step(cite))
    assert result["accepted"]
    r.store.stage_diagnosis(lease, result)
    with r.store.engine.begin() as c:
        c.execute(update(graph_progress).where(graph_progress.c.run_id == run_id).values(
            created_at=text("clock_timestamp() - interval '119 seconds'")))
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        with r.store.engine.connect() as blocker:
            with blocker.begin():
                blocker.execute(text("LOCK TABLE diagnosis_steps IN ACCESS EXCLUSIVE MODE"))
                blocker_pid = blocker.execute(text("SELECT pg_backend_pid()")).scalar_one()
                future = pool.submit(r.store.finish, lease, result=result)
                observed_wait = False
                crossed = False
                until = time.monotonic() + 5
                with r.store.engine.connect() as observer:
                    while time.monotonic() < until:
                        if blocker_pid in observer.execute(
                            text("SELECT pg_blocking_pids(:pid)"), {"pid": lease.pid}
                        ).scalar_one():
                            observed_wait = True
                            break
                        time.sleep(0.02)
                    assert observed_wait, "Real publication SQL wait was not observed"
                    while time.monotonic() < until:
                        crossed = observer.execute(text(
                            "SELECT clock_timestamp() >= created_at + interval '120 seconds' "
                            "FROM graph_progress WHERE run_id=:run_id"),
                            {"run_id": run_id}).scalar_one()
                        if crossed:
                            break
                        time.sleep(0.02)
                    assert crossed, "Database clock did not cross the turn deadline"
            future.result(timeout=6)
    finally:
        pool.shutdown(wait=True)
        lease.close()
    with r.store.engine.connect() as c:
        assert c.execute(select(cases.c.revision).where(cases.c.id == cid)).scalar_one() == 0
        assert c.execute(select(diagnosis_steps.c.id).where(
            diagnosis_steps.c.case_id == cid)).first() is None
        assert c.execute(select(diagnosis_publications.c.id).where(
            diagnosis_publications.c.case_id == cid)).first() is None
        run = c.execute(select(runs.c.status, runs.c.error_json).where(
            runs.c.id == run_id)).one()
        assert run.status == "failed" and run.error_json["code"] == "MODEL_TURN_TIMEOUT"


def test_cancel_queued_resume_keeps_original_waiting_check(indexed_rig):
    r = indexed_rig
    _, case, ctx, svc, cite = prepare(r, (FIX / "extra-synthetic.md").read_bytes())
    r.store.settings = Settings(app_mode="test", retrieval_profile="synthetic")
    service = DiagnosisService(r.store.engine)
    cid = UUID(case["id"])
    first_id = UUID(service.start(r.actor, cid, StartDiagnosis(expected_revision=0),
                                  uuid4().hex)[1]["run_id"])
    lease = r.store.claim_legacy("wp11-first-check", run_id=first_id)
    try:
        result = svc.validate(ctx, synthetic_step(cite))
        assert result["accepted"]
        r.store.stage_diagnosis(lease, result)
        r.store.finish(lease, result=result)
    finally:
        lease.close()
    r.store.reconcile_wait(first_id)
    current = service.current(r.actor, cid)
    step = current["current_step"]
    observation_id = uuid4()
    with r.store.engine.begin() as c:
        c.execute(observations.insert().values(
            id=observation_id, case_id=cid, area_id=UUID(step["area_id"]),
            step_id=UUID(step["id"]), kind="choice", payload={"selected": "observed"},
            created_revision=1, actor_id=r.actor))
    resumed_id = UUID(service.resume(r.actor, cid,
        ResumeDiagnosis(expected_revision=1, observation_id=observation_id),
        uuid4().hex)[1]["run_id"])
    RunService(r.store.engine).cancel(r.actor, resumed_id, uuid4().hex)
    retained = service.current(r.actor, cid)
    assert retained["revision"] == 1 and retained["status"] == "waiting_input"
    assert retained["current_step"]["id"] == step["id"]


def test_one_repair_budget_is_persisted_before_second_model_call(indexed_rig):
    r = indexed_rig
    _, case, _, _, _ = prepare(r, (FIX / "extra-synthetic.md").read_bytes())
    cid = UUID(case["id"])
    run_id = UUID(DiagnosisService(r.store.engine).start(
        r.actor, cid, StartDiagnosis(expected_revision=0), uuid4().hex)[1]["run_id"])
    lease = r.store.claim_legacy("wp11-repair", run_id=run_id)
    assert lease is not None
    try:
        r.store.reserve_diagnosis_repair(lease)
        with pytest.raises(DomainError) as exhausted:
            r.store.reserve_diagnosis_repair(lease)
        assert exhausted.value.code == "REPAIR_EXHAUSTED"
        with r.store.engine.connect() as c:
            budget = c.execute(select(runs.c.budget_json).where(
                runs.c.id == run_id)).scalar_one()
        assert budget["proposal_repair_used"] is True
    finally:
        lease.close()
