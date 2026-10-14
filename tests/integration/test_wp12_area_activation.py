"""ISSUE-001: public area activation cannot bypass conservative closure."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from app.agents.state import ProposalContext
from app.infrastructure.orm import (
    case_evidence, cases, diagnosis_area_conclusions, diagnosis_areas,
    diagnosis_steps, observations, run_events, runs,
)
from app.services.diagnosis_service import DiagnosisService
from app.services.run_service import RunService
from test_document_ingest import docrig as docrig
from test_evidence_measurement import indexed_rig as indexed_rig
from test_wp12_area_closure import setup_turn, answer, next_candidate, publish_next
from test_evidence_measurement import spec, approve, compare
from test_wp10_proposals import FIX


pytestmark = pytest.mark.database


def pending(r, cid, step):
    identifier = uuid4()
    with r.store.engine.begin() as c:
        previous = c.execute(select(diagnosis_areas).where(
            diagnosis_areas.c.id == UUID(step["area_id"]))).mappings().one()
        c.execute(diagnosis_areas.insert().values(
            id=identifier, case_id=cid, workflow_id=previous["workflow_id"],
            graph_epoch=0, component_key="Q02", title="Synthetic pending area",
            provenance_json={"source": "synthetic_activation_test"}, status="pending"))
    return identifier


def activate(r, cid, aid, revision, key=None):
    return r.client.post(f"/api/v2/cases/{cid}/diagnosis/areas/{aid}/activate",
        headers=dict(r.headers, **{"Idempotency-Key": key or uuid4().hex}),
        json={"expected_revision": revision, "graph_epoch": 0})


def close_first(r, cid, step, proposal, cite, rid):
    with r.store.engine.connect() as c:
        obs_id = c.execute(select(observations.c.id).where(
            observations.c.case_id == cid)).scalar_one()
    candidate = dict(type="conclude_area", component_key="P01",
        finding=cite("P01 是隔离台架的合成检查部件。"),
        assessment="unknown", observation_ids=[str(obs_id)])
    checked = proposal.validate(ProposalContext(r.actor, cid, 2), candidate)
    assert checked["accepted"], checked["issues"]
    lease = r.store.claim_legacy("activation-close", run_id=rid)
    try:
        r.store.stage_diagnosis(lease, checked)
        r.store.finish(lease, result=checked)
    finally:
        lease.close()
    return obs_id


@pytest.mark.parametrize("block", ["unavailable", "source_invalid", "active_run"])
def test_unfinished_area_rejects_public_activation_without_side_effects(indexed_rig, block):
    r = indexed_rig
    cid, step, _, _ = setup_turn(r)
    rid = answer(r, cid, step, unavailable=block == "unavailable")
    aid = pending(r, cid, step)
    if block != "active_run":
        RunService(r.store.engine).cancel(r.actor, rid, uuid4().hex)
    if block == "source_invalid":
        with r.store.engine.begin() as c:
            c.execute(update(case_evidence).where(case_evidence.c.case_id == cid)
                .values(needs_review=True, review_reasons=["synthetic_revocation"]))
    with r.store.engine.connect() as c:
        before = c.execute(select(cases.c.revision).where(cases.c.id == cid)).scalar_one()
        cards = c.execute(select(diagnosis_area_conclusions.c.id).where(
            diagnosis_area_conclusions.c.case_id == cid)).all()
        events = c.execute(select(run_events.c.id).join(runs, runs.c.id == run_events.c.run_id)
            .where(runs.c.case_id == cid)).all()
    response = activate(r, cid, aid, before)
    assert response.status_code == 409, response.text
    with r.store.engine.connect() as c:
        assert c.execute(select(cases.c.revision).where(cases.c.id == cid)).scalar_one() == before
        assert c.execute(select(diagnosis_area_conclusions.c.id).where(
            diagnosis_area_conclusions.c.case_id == cid)).all() == cards
        assert c.execute(select(run_events.c.id).join(runs, runs.c.id == run_events.c.run_id)
            .where(runs.c.case_id == cid)).all() == events
        assert c.execute(select(runs.c.id).where(runs.c.case_id == cid,
            runs.c.input_payload["area_activation"].as_string() == str(aid))).first() is None
        assert c.execute(select(diagnosis_steps.c.status).where(
            diagnosis_steps.c.id == UUID(step["id"]))).scalar_one() == "completed"


def test_completed_area_activates_once_and_preserves_original_facts(indexed_rig):
    r = indexed_rig
    cid, step, proposal, cite = setup_turn(r)
    rid = answer(r, cid, step)
    obs_id = close_first(r, cid, step, proposal, cite, rid)
    aid = pending(r, cid, step)
    stale = r.client.post(f"/api/v2/cases/{cid}/diagnosis/areas/{aid}/activate",
        headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
        json={"expected_revision": 3, "graph_epoch": 1})
    assert stale.status_code == 409
    key = uuid4().hex
    first = activate(r, cid, aid, 3, key)
    assert first.status_code == 202, first.text
    assert activate(r, cid, aid, 3, key).json() == first.json()
    assert activate(r, cid, aid, 3).status_code == 409
    child_id = UUID(first.json()["run_id"])
    with r.store.engine.connect() as c:
        assert len(c.execute(select(runs.c.id).where(runs.c.case_id == cid,
            runs.c.input_payload["area_activation"].as_string() == str(aid))).all()) == 1
        assert c.execute(select(diagnosis_steps.c.status).where(
            diagnosis_steps.c.id == UUID(step["id"]))).scalar_one() == "completed"
        assert c.execute(select(observations.c.id).where(observations.c.id == obs_id)).first()
        assert len(c.execute(select(diagnosis_area_conclusions.c.id).where(
            diagnosis_area_conclusions.c.area_id == UUID(step["area_id"]))).all()) == 1
    next_step = next_candidate(cite)
    next_checked = proposal.validate(ProposalContext(r.actor, cid, 3), next_step)
    assert next_checked["accepted"], next_checked["issues"]
    lease = r.store.claim_legacy("activation-next", run_id=child_id)
    try:
        r.store.stage_diagnosis(lease, next_checked)
        r.store.finish(lease, result=next_checked)
    finally:
        lease.close()
    current = DiagnosisService(r.store.engine).current(r.actor, cid)
    assert current["status"] == "waiting_input"
    assert current["current_step"]["candidate"]["component_key"] == "Q02"


def test_completed_area_with_revoked_source_cannot_activate(indexed_rig):
    r = indexed_rig
    cid, step, proposal, cite = setup_turn(r)
    rid = answer(r, cid, step)
    close_first(r, cid, step, proposal, cite, rid)
    aid = pending(r, cid, step)
    with r.store.engine.begin() as c:
        c.execute(update(case_evidence).where(case_evidence.c.case_id == cid)
            .values(needs_review=True, review_reasons=["synthetic_revocation"]))
    response = activate(r, cid, aid, 3)
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "AREA_SOURCE_INVALID"
    with r.store.engine.connect() as c:
        assert c.execute(select(runs.c.id).where(runs.c.case_id == cid,
            runs.c.input_payload["area_activation"].as_string() == str(aid))).first() is None
        assert c.execute(select(cases.c.revision).where(cases.c.id == cid)).scalar_one() == 3


def test_same_group_conflict_cannot_publicly_skip_old_area(indexed_rig):
    r = indexed_rig
    cid, step, proposal, cite = setup_turn(r)
    rid = answer(r, cid, step)
    aid = pending(r, cid, step)
    standard = next(line for line in (FIX / "extra-synthetic.md").read_text(
        encoding="utf-8").splitlines() if line.startswith("P01 synthetic standard"))
    standard_ref = cite(standard)
    made = spec(r, {"evidence_id": standard_ref["references"][0]["evidence_id"]},
                component_key="P01")
    sid = made["spec"]["id"]
    assert approve(r, sid).status_code == 200
    within = compare(r, sid, value="1.5", unit="V")
    outside = compare(r, sid, value="3", unit="V")
    with r.store.engine.begin() as c:
        first = c.execute(select(diagnosis_steps).where(
            diagnosis_steps.c.id == UUID(step["id"]))).mappings().one()
        for ordinal, comp in enumerate((within, outside), 2):
            synthetic_step_id = uuid4()
            c.execute(diagnosis_steps.insert().values(
                id=synthetic_step_id, case_id=cid, area_id=UUID(step["area_id"]),
                run_id=first["run_id"], turn_id=uuid4(), ordinal=ordinal,
                candidate_json=first["candidate_json"], validation_json={"issues": []},
                status="completed"))
            c.execute(observations.insert().values(
                id=uuid4(), case_id=cid, area_id=UUID(step["area_id"]),
                step_id=synthetic_step_id, kind="measurement", actor_id=r.actor,
                created_revision=2, payload={"component_key": "P01", "checked": True,
                    "measurements": [{"spec_id": sid, "conditions": {"engine": "off"},
                        "comparison_id": comp["id"], "outcome": comp["result"]["outcome"]}]}))
    publish_next(r, cid, rid, proposal, cite)
    response = activate(r, cid, aid, 2)
    assert response.status_code == 409, response.text
    with r.store.engine.connect() as c:
        assert c.execute(select(runs.c.id).where(runs.c.case_id == cid,
            runs.c.input_payload["area_activation"].as_string() == str(aid))).first() is None


def test_auto_enqueued_area_is_not_reenqueued(indexed_rig):
    r = indexed_rig
    cid, step, proposal, cite = setup_turn(r)
    rid = answer(r, cid, step)
    aid = pending(r, cid, step)
    with r.store.engine.connect() as c:
        obs_id = c.execute(select(observations.c.id).where(
            observations.c.case_id == cid)).scalar_one()
    candidate = dict(type="conclude_area", component_key="P01",
        finding=cite("P01 是隔离台架的合成检查部件。"),
        assessment="unknown", observation_ids=[str(obs_id)])
    checked = proposal.validate(ProposalContext(r.actor, cid, 2), candidate)
    assert checked["accepted"], checked["issues"]
    lease = r.store.claim_legacy("activation-auto", run_id=rid)
    try:
        r.store.stage_diagnosis(lease, checked)
        r.store.finish(lease, result=checked)
    finally:
        lease.close()
    assert activate(r, cid, aid, 3).status_code == 409
    with r.store.engine.connect() as c:
        children = c.execute(select(runs.c.id).where(runs.c.case_id == cid,
            runs.c.input_payload["area_activation"].as_string() == str(aid))).all()
        assert len(children) == 1
    RunService(r.store.engine).cancel(r.actor, children[0][0], uuid4().hex)
    assert activate(r, cid, aid, 3).status_code == 409
    with r.store.engine.connect() as c:
        assert len(c.execute(select(runs.c.id).where(runs.c.case_id == cid,
            runs.c.input_payload["area_activation"].as_string() == str(aid))).all()) == 1
