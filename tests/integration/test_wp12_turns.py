"""WP-12: synthetic isolated PostgreSQL observation turns, never a repair claim."""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4
from threading import Barrier, Event

import pytest
from sqlalchemy import select, text, update

from app.agents.state import ProposalContext
from app.legacy_execution.graph import DiagnosisGraph
from app.config import Settings
from app.domain.policies import DomainError
from app.infrastructure.orm import (
    case_evidence, cases, diagnosis_area_conclusions, diagnosis_steps, graph_progress, jobs,
    observations, run_events, runs,
)
from app.services.diagnosis_service import DiagnosisService, StartDiagnosis
from app.services.evidence_scope import invalidate_source
from app.services.run_service import RunService
from test_evidence_measurement import indexed_rig as indexed_rig
from test_document_ingest import docrig as docrig
from test_wp10_proposals import FIX, prepare, synthetic_step
from test_wp10_remediation import EXTRA, measurement

pytestmark = pytest.mark.database


def waiting(r):
    _, case, _, proposal, cite = prepare(r, (FIX / "extra-synthetic.md").read_bytes()
        + "\n检查 P01 插头。\n".encode())
    r.store.lease_seconds = 60
    r.store.settings = Settings(app_mode="test", retrieval_profile="synthetic")
    cid = UUID(case["id"])
    rid = UUID(DiagnosisService(r.store.engine).start(
        r.actor, cid, StartDiagnosis(expected_revision=0), uuid4().hex)[1]["run_id"])
    lease = r.store.claim_legacy("wp12-first", run_id=rid)
    try:
        accepted = proposal.validate(ProposalContext(r.actor, cid, 0), synthetic_step(cite))
        assert accepted["accepted"], accepted["issues"]
        r.store.stage_diagnosis(lease, accepted)
        r.store.finish(lease, result=accepted)
    finally:
        lease.close()
    r.store.reconcile_wait(rid)
    return cid, DiagnosisService(r.store.engine).current(r.actor, cid)["current_step"], cite, proposal


def post(r, cid, step, **changes):
    body = dict(expected_revision=1, graph_epoch=0, step_id=step["id"],
                kind="choice", choice_index=0)
    body.update(changes)
    return r.client.post(f"/api/v2/cases/{cid}/observations",
                         headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
                         json=body)


def test_observation_atomic_idempotent_and_public_resume_closed(indexed_rig):
    r = indexed_rig
    cid, step, cite, proposal = waiting(r)
    body = dict(expected_revision=1, graph_epoch=0, step_id=step["id"],
                kind="choice", choice_index=0)
    key = uuid4().hex
    url = f"/api/v2/cases/{cid}/observations"
    headers = dict(r.headers, **{"Idempotency-Key": key})
    first = r.client.post(url, headers=headers, json=body)
    assert first.status_code == 202, first.text
    assert r.client.post(url, headers=headers, json=body).json() == first.json()
    assert r.client.post(url, headers=headers, json=dict(body, choice_index=1)).status_code == 409
    assert post(r, cid, step).status_code == 409
    assert post(r, cid, step, expected_revision=0).json()["error"]["details"]["current_revision"] == 2
    assert post(r, cid, step, step_id=str(uuid4())).status_code == 409
    resume = r.client.post(f"/api/v2/cases/{cid}/diagnosis/resume",
        headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
        json={"expected_revision": 2, "observation_id": first.json()["observation_id"]})
    assert resume.status_code == 409 and resume.json()["error"]["code"] == "OBSERVATION_SUBMIT_REQUIRED"
    with r.store.engine.connect() as c:
        assert c.execute(select(cases.c.revision).where(cases.c.id == cid)).scalar_one() == 2
        assert len(c.execute(select(observations.c.id).where(observations.c.case_id == cid)).all()) == 1
        saved = c.execute(select(observations.c.payload).where(
            observations.c.case_id == cid)).scalar_one()
        assert saved["checked"] is False  # the fixture choice says "not checked"
        assert c.execute(select(diagnosis_steps.c.status).where(
            diagnosis_steps.c.id == UUID(step["id"]))).scalar_one() == "completed"
        rid = UUID(first.json()["run_id"])
        assert c.execute(select(graph_progress.c.step_id).where(
            graph_progress.c.run_id == rid)).scalar_one() == UUID(step["id"])
        assert [x[0] for x in c.execute(select(run_events.c.type).where(
            run_events.c.run_id == rid).order_by(run_events.c.id))] == ["run.queued", "observation.saved"]
    lease = r.store.claim_legacy("wp12-second", run_id=rid)
    assert lease is not None
    try:
        candidate = synthetic_step(cite)
        candidate["title"] = "第二个有据检查"
        candidate["actions"] = [dict(**cite("检查 P01 插头。"), operation="inspect")]
        checked = proposal.validate(ProposalContext(r.actor, cid, 2), candidate)
        assert checked["accepted"], checked["issues"]
        r.store.stage_diagnosis(lease, checked)
        DiagnosisGraph(r.store, lease, Event()).execute()
    finally:
        lease.close()
    assert DiagnosisService(r.store.engine).current(r.actor, cid)["revision"] == 3


def test_unavailable_correction_new_epoch_and_area_card(indexed_rig):
    r = indexed_rig
    cid, step, _, _ = waiting(r)
    sent = post(r, cid, step, kind="unavailable", choice_index=None,
                reason="Synthetic fixture: equipment unavailable")
    assert sent.status_code == 202, sent.text
    new_run = UUID(sent.json()["run_id"])
    # The still-active next run must be terminal before a fact correction.
    correction = dict(expected_revision=2, graph_epoch=0, step_id=step["id"],
                      kind="choice", choice_index=0, correction_reason="Recorded wrong input")
    path = f"/api/v2/cases/{cid}/observations/{sent.json()['observation_id']}/correct"
    headers = dict(r.headers, **{"Idempotency-Key": uuid4().hex})
    active = r.client.post(path, headers=headers, json=correction)
    assert active.status_code == 409 and active.json()["error"]["code"] == "RUN_ACTIVE", active.text
    RunService(r.store.engine).cancel(r.actor, new_run, uuid4().hex)
    assert DiagnosisService(r.store.engine).current(r.actor, cid)["status"] == "needs_review"
    area = r.client.get(f"/api/v2/cases/{cid}/diagnosis/areas")
    assert area.status_code == 200 and len(area.json()["areas"]) == 1
    area_id = UUID(step["area_id"])
    card = r.client.post(f"/api/v2/cases/{cid}/diagnosis/areas/{area_id}/conclude",
        headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
        json={"expected_revision": 2, "graph_epoch": 0})
    assert card.status_code == 201 and card.json()["assessment"] == "needs_input"
    assert card.json()["content"]["source_evidence_ids"]
    corrected = r.client.post(path, headers=headers, json=correction)
    assert corrected.status_code == 202, corrected.text
    assert r.client.post(path, headers=headers, json=correction).json() == corrected.json()
    assert corrected.json()["graph_epoch"] == 1
    with r.store.engine.connect() as c:
        old = c.execute(select(observations).where(
            observations.c.id == UUID(sent.json()["observation_id"]))).mappings().one()
        replacement = c.execute(select(observations).where(
            observations.c.id == UUID(corrected.json()["observation_id"]))).mappings().one()
        assert old["kind"] == "unavailable" and old["payload"]["checked"] is False
        assert replacement["supersedes_id"] == old["id"]
        assert c.execute(select(cases.c.graph_epoch).where(cases.c.id == cid)).scalar_one() == 1
        assert c.execute(select(diagnosis_area_conclusions.c.needs_review).where(
            diagnosis_area_conclusions.c.area_id == area_id)).scalar_one() is True
        assert c.execute(select(diagnosis_steps.c.status).where(
            diagnosis_steps.c.id == UUID(step["id"]))).scalar_one() == "needs_review"


def test_owner_and_choice_validation(indexed_rig):
    r = indexed_rig
    cid, step, _, _ = waiting(r)
    assert post(r, cid, step, choice_index=99).status_code == 422
    with pytest.raises(DomainError) as wrong:
        from app.services.observation_service import ObservationService, SubmitObservation
        ObservationService(r.store.engine, Settings(app_mode="test", retrieval_profile="synthetic")).submit(
            uuid4(), cid, SubmitObservation(expected_revision=1, graph_epoch=0,
                step_id=UUID(step["id"]), kind="choice", choice_index=0), uuid4().hex)
    assert wrong.value.code == "NOT_FOUND"


def test_concurrent_distinct_keys_only_one_answer(indexed_rig):
    from app.services.observation_service import ObservationService, SubmitObservation

    r = indexed_rig
    cid, step, _, _ = waiting(r)
    body = SubmitObservation(expected_revision=1, graph_epoch=0,
                             step_id=UUID(step["id"]), kind="choice", choice_index=0)
    barrier = Barrier(2)

    def send(_):
        barrier.wait(timeout=10)
        try:
            return ObservationService(r.store.engine, r.store.settings).submit(
                r.actor, cid, body, uuid4().hex)[0]
        except DomainError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(send, range(2)))
    assert sorted(outcomes, key=str) == [202, "REVISION_CONFLICT"]
    with r.store.engine.connect() as c:
        assert len(c.execute(select(observations.c.id).where(
            observations.c.case_id == cid)).all()) == 1
        assert c.execute(select(cases.c.revision).where(cases.c.id == cid)).scalar_one() == 2


def test_area_card_rechecks_observation_source(indexed_rig):
    r = indexed_rig
    cid, step, _, _ = waiting(r)
    sent = post(r, cid, step)
    assert sent.status_code == 202
    RunService(r.store.engine).cancel(r.actor, UUID(sent.json()["run_id"]), uuid4().hex)
    with r.store.engine.begin() as c:
        c.execute(update(case_evidence).where(case_evidence.c.case_id == cid)
                  .values(needs_review=True, review_reasons=["synthetic_revocation_fixture"]))
    card = r.client.post(
        f"/api/v2/cases/{cid}/diagnosis/areas/{step['area_id']}/conclude",
        headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
        json={"expected_revision": 2, "graph_epoch": 0})
    assert card.status_code == 201, card.text
    assert card.json()["assessment"] == "needs_input"
    assert card.json()["content"]["basis"] == "source_invalid"
    with r.store.engine.begin() as c:
        version = c.execute(select(case_evidence.c.document_version_id).where(
            case_evidence.c.case_id == cid).limit(1)).scalar_one()
        invalidate_source(c, version)
    with r.store.engine.connect() as c:
        assert c.execute(select(diagnosis_area_conclusions.c.needs_review).where(
            diagnosis_area_conclusions.c.id == UUID(card.json()["id"]))).scalar_one() is True


def test_approved_decimal_measurement_and_conditions(indexed_rig):
    r = indexed_rig
    _, case, _, proposal, cite = prepare(r,
        (FIX / "extra-synthetic.md").read_bytes() + EXTRA.encode())
    r.store.lease_seconds = 60
    r.store.settings = Settings(app_mode="test", retrieval_profile="synthetic")
    cid = UUID(case["id"])
    candidate = synthetic_step(cite)
    sid = measurement(r, cite, candidate)
    validated = proposal.validate(ProposalContext(r.actor, cid, 0), candidate)
    assert validated["accepted"], validated["issues"]
    rid = UUID(DiagnosisService(r.store.engine).start(
        r.actor, cid, StartDiagnosis(expected_revision=0), uuid4().hex)[1]["run_id"])
    lease = r.store.claim_legacy("wp12-measure", run_id=rid)
    try:
        r.store.stage_diagnosis(lease, validated)
        r.store.finish(lease, result=validated)
    finally:
        lease.close()
    current = DiagnosisService(r.store.engine).current(r.actor, cid)["current_step"]
    base = dict(expected_revision=1, graph_epoch=0, step_id=current["id"],
                kind="measurement", measurements=[dict(spec_id=sid, value="1.0000000000000000001",
                    unit="V", conditions={"engine": "off"})])
    url = f"/api/v2/cases/{cid}/observations"
    def request(data):
        return r.client.post(url, headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
                             json=data)
    assert request(dict(base, measurements=[dict(base["measurements"][0],
                    conditions={"engine": "on"})])).status_code == 422
    assert request(dict(base, measurements=[dict(base["measurements"][0],
                    unit="ohm")])).status_code == 422
    assert request(dict(base, measurements=[])).status_code == 422
    good = request(base)
    assert good.status_code == 202, good.text
    history = r.client.get(f"/api/v2/cases/{cid}/observations")
    assert history.status_code == 200
    measured = history.json()["items"][-1]["payload"]["measurements"][0]
    assert measured["value"] == "1.0000000000000000001"
    assert measured["outcome"] == "within_range"


def test_new_worker_reuses_saved_observation_and_staged_check(indexed_rig):
    """Separate process takes over one expired attempt without model access."""
    r = indexed_rig
    cid, step, cite, proposal = waiting(r)
    sent = post(r, cid, step)
    assert sent.status_code == 202
    rid = UUID(sent.json()["run_id"])
    first = r.store.claim_legacy("wp12-crashed-worker", run_id=rid)
    assert first is not None
    try:
        candidate = synthetic_step(cite)
        candidate["title"] = "跨进程有据检查"
        candidate["actions"] = [dict(**cite("检查 P01 插头。"), operation="inspect")]
        accepted = proposal.validate(ProposalContext(r.actor, cid, 2), candidate)
        assert accepted["accepted"], accepted["issues"]
        r.store.stage_diagnosis(first, accepted)
    finally:
        first.close()
    # Test-only crash boundary: old process is gone; expire its lease without
    # changing the token or the persisted candidate.
    with r.store.engine.begin() as c:
        c.execute(update(jobs).where(jobs.c.run_id == rid)
                  .values(lease_until=text("clock_timestamp() - interval '1 second'")))
    env = dict(os.environ, DATABASE_URL=os.environ["TEST_DATABASE_URL"],
               APP_MODE="test", RETRIEVAL_PROFILE="synthetic", TOOL_MODE="local",
               PYTHONPATH="backend", XIUTU_WP11_PAID="0")
    runner = ("from uuid import UUID; from app.infrastructure.job_store import JobStore; "
              "from app.worker import Worker; import os,sys; "
              "store=JobStore(os.environ['TEST_DATABASE_URL']); "
              "assert Worker(store, legacy_execution=True).once(run_id=UUID(sys.argv[1])); store.close()")
    proc = subprocess.run([sys.executable, "-B", "-c", runner, str(rid)],
                          env=env, capture_output=True, text=True, timeout=45)
    assert proc.returncode == 0, proc.stderr[-1000:]
    with r.store.engine.connect() as c:
        assert c.execute(select(cases.c.revision).where(cases.c.id == cid)).scalar_one() == 3
        assert c.execute(select(jobs.c.attempt).where(jobs.c.run_id == rid)).scalar_one() == 2
        assert c.execute(select(runs.c.status).where(runs.c.id == rid)).scalar_one() == "waiting_input"
        assert len(c.execute(select(diagnosis_steps.c.id).where(
            diagnosis_steps.c.case_id == cid)).all()) == 2


def test_two_saved_choices_drive_distinct_source_backed_checks(indexed_rig):
    """Deterministic branch fixture proves persisted facts can alter the next check.

    This is not a DeepSeek decision or a vehicle diagnosis.
    """
    r = indexed_rig
    source = ((FIX / "extra-synthetic.md").read_text(encoding="utf-8") +
              "\nP01 外观完好。\n\nP01 外观损坏。\n\n检查 P01 插头。\n\n检查 P01 外壳。\n")
    seen = []
    for selection, expected_state, action_text in [
        (0, "intact", "检查 P01 插头。"),
        (1, "damaged", "检查 P01 外壳。"),
    ]:
        _, case, _, proposal, cite = prepare(r, source.encode("utf-8"))
        r.store.lease_seconds = 60
        r.store.settings = Settings(app_mode="test", retrieval_profile="synthetic")
        cid = UUID(case["id"])
        first_candidate = synthetic_step(cite)
        first_candidate["input"]["choices"] = [cite("P01 外观完好。"), cite("P01 外观损坏。")]
        first = proposal.validate(ProposalContext(r.actor, cid, 0), first_candidate)
        assert first["accepted"], first["issues"]
        rid = UUID(DiagnosisService(r.store.engine).start(
            r.actor, cid, StartDiagnosis(expected_revision=0), uuid4().hex)[1]["run_id"])
        lease = r.store.claim_legacy("wp12-branch-first", run_id=rid)
        try:
            r.store.stage_diagnosis(lease, first)
            r.store.finish(lease, result=first)
        finally:
            lease.close()
        step = DiagnosisService(r.store.engine).current(r.actor, cid)["current_step"]
        assert post(r, cid, step, choice_index=selection).status_code == 422
        answer = post(r, cid, step, choice_index=selection,
                      conditions={"engine": "off"})
        assert answer.status_code == 202, answer.text
        with r.store.engine.connect() as c:
            stored = c.execute(select(observations.c.payload).where(
                observations.c.id == UUID(answer.json()["observation_id"]))).scalar_one()
        assert stored["checked"] is True and stored["appearance_state"] == expected_state
        assert stored["conditions"] == {"engine": "off"}
        next_candidate = synthetic_step(cite)
        next_candidate["actions"] = [dict(**cite(action_text), operation="inspect")]
        validated = proposal.validate(ProposalContext(r.actor, cid, 2), next_candidate)
        assert validated["accepted"], validated["issues"]
        next_rid = UUID(answer.json()["run_id"])
        lease = r.store.claim_legacy("wp12-branch-next", run_id=next_rid)
        try:
            r.store.stage_diagnosis(lease, validated)
            r.store.finish(lease, result=validated)
        finally:
            lease.close()
        current = DiagnosisService(r.store.engine).current(r.actor, cid)
        assert current["current_step"]["candidate"]["actions"][0]["text"] == action_text
        seen.append(current["current_step"]["candidate"]["actions"][0]["text"])
    assert seen[0] != seen[1]
