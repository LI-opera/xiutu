"""A411: conservative area closure using isolated synthetic material."""

from uuid import UUID, uuid4
from threading import Event
import copy

import pytest
from sqlalchemy import select, update

from app.agents.state import ProposalContext
from app.legacy_execution.graph import DiagnosisGraph
from app.legacy_execution.checkpoint import FencedPostgresSaver
from app.config import Settings
from app.domain.policies import DomainError
from app.infrastructure.orm import (
    case_evidence, cases, diagnosis_area_conclusions, diagnosis_areas,
    diagnosis_publications, diagnosis_steps, graph_progress, observations,
    run_events, runs,
)
from app.infrastructure.job_store import LeaseLost
from app.services.diagnosis_service import DiagnosisService, StartDiagnosis
from test_document_ingest import docrig as docrig
from test_evidence_measurement import approve, compare, spec
from test_evidence_measurement import indexed_rig as indexed_rig
from test_wp10_proposals import FIX, prepare, synthetic_step


pytestmark = pytest.mark.database


def setup_turn(r):
    source = (FIX / "extra-synthetic.md").read_text(encoding="utf-8") + "\n\n" + "\n\n".join([
        "P01 外观完好。", "Q02 是隔离台架的合成检查部件。",
        "Q02 位于隔离台架右侧。", "检查 Q02 外观。", "Q02 外观完好。",
    ])
    _, case, _, proposal, cite = prepare(r, source.encode())
    r.store.lease_seconds = 60
    r.store.settings = Settings(app_mode="test", retrieval_profile="synthetic")
    cid = UUID(case["id"])
    first = synthetic_step(cite)
    first["input"]["choices"] = [cite("P01 外观完好。")]
    checked = proposal.validate(ProposalContext(r.actor, cid, 0), first)
    assert checked["accepted"], checked["issues"]
    rid = UUID(DiagnosisService(r.store.engine).start(
        r.actor, cid, StartDiagnosis(expected_revision=0), uuid4().hex)[1]["run_id"])
    lease = r.store.claim_legacy("area-first", run_id=rid)
    try:
        r.store.stage_diagnosis(lease, checked)
        r.store.finish(lease, result=checked)
    finally:
        lease.close()
    step = DiagnosisService(r.store.engine).current(r.actor, cid)["current_step"]
    return cid, step, proposal, cite


def next_candidate(cite):
    return dict(type="propose_step", component_key="Q02", title="合成右侧检查",
                purpose=cite("Q02 是隔离台架的合成检查部件。"),
                location=cite("Q02 位于隔离台架右侧。"),
                prerequisites=[cite("发动机关闭，engine=off。")],
                actions=[dict(**cite("检查 Q02 外观。"), operation="inspect")],
                input=dict(kind="choice", choices=[cite("Q02 外观完好。")]))


def answer(r, cid, step, *, unavailable=False):
    body = dict(expected_revision=1, graph_epoch=0, step_id=step["id"])
    if unavailable:
        body.update(kind="unavailable", reason="Synthetic fixture: instrument absent")
    else:
        body.update(kind="choice", choice_index=0, conditions={"engine": "off"})
    response = r.client.post(f"/api/v2/cases/{cid}/observations",
        headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}), json=body)
    assert response.status_code == 202, response.text
    return UUID(response.json()["run_id"])


def publish_next(r, cid, rid, proposal, cite):
    candidate = next_candidate(cite)
    checked = proposal.validate(ProposalContext(r.actor, cid, 2), candidate)
    assert checked["accepted"], checked["issues"]
    lease = r.store.claim_legacy("area-next", run_id=rid)
    assert lease is not None
    try:
        r.store.stage_diagnosis(lease, checked)
        r.store.finish(lease, result=checked)
    finally:
        lease.close()


def test_area_completion_card_is_atomic_and_not_duplicated(indexed_rig):
    r = indexed_rig
    cid, step, proposal, cite = setup_turn(r)
    rid = answer(r, cid, step)
    with r.store.engine.connect() as c:
        assert c.execute(select(diagnosis_area_conclusions.c.id).where(
            diagnosis_area_conclusions.c.area_id == UUID(step["area_id"]))).first() is None
    publish_next(r, cid, rid, proposal, cite)
    with r.store.engine.connect() as c:
        cards = c.execute(select(diagnosis_area_conclusions).where(
            diagnosis_area_conclusions.c.area_id == UUID(step["area_id"]))).mappings().all()
        assert len(cards) == 1 and cards[0]["assessment"] == "unknown"
        assert cards[0]["content_json"]["diagnosis"] is False
        assert c.execute(select(diagnosis_areas.c.status).where(
            diagnosis_areas.c.id == UUID(step["area_id"]))).scalar_one() == "completed"
        assert c.execute(select(run_events.c.id).where(
            run_events.c.run_id == rid, run_events.c.type == "area.completed")).first()
    current = DiagnosisService(r.store.engine).current(r.actor, cid)
    assert current["current_step"]["candidate"]["component_key"] == "Q02"
    assert current["status"] == "waiting_input"
    r.store.reconcile_wait(rid)
    with r.store.engine.connect() as c:
        assert len(c.execute(select(diagnosis_area_conclusions.c.id).where(
            diagnosis_area_conclusions.c.area_id == UUID(step["area_id"]))).all()) == 1


def test_explicit_area_end_is_server_summarized_and_checkpointed(indexed_rig):
    r = indexed_rig
    cid, step, proposal, cite = setup_turn(r)
    rid = answer(r, cid, step)
    with r.store.engine.connect() as c:
        obs_id = c.execute(select(observations.c.id).where(
            observations.c.case_id == cid)).scalar_one()
    candidate = dict(type="conclude_area", component_key="P01",
        finding=cite("P01 是隔离台架的合成检查部件。"),
        assessment="unknown", observation_ids=[str(obs_id)])
    checked = proposal.validate(ProposalContext(r.actor, cid, 2), candidate)
    assert checked["accepted"], checked["issues"]
    lease = r.store.claim_legacy("area-end", run_id=rid)
    try:
        r.store.stage_diagnosis(lease, checked)
        DiagnosisGraph(r.store, lease, Event()).execute()
        r.store.finish(lease, result=checked)
        different = copy.deepcopy(checked)
        different["candidate"]["finding"]["text"] = "Synthetic different area end"
        with pytest.raises(DomainError) as changed:
            r.store.finish(lease, result=different)
        assert changed.value.code == "PUBLICATION_CONFLICT"
    finally:
        lease.close()
    with r.store.engine.connect() as c:
        assert c.execute(select(runs.c.status).where(runs.c.id == rid)).scalar_one() == "succeeded"
        assert c.execute(select(graph_progress.c.phase).where(
            graph_progress.c.run_id == rid)).scalar_one() == "completed"
        assert c.execute(select(diagnosis_publications.c.node).where(
            diagnosis_publications.c.run_id == rid)).scalar_one() == "area_close"
        assert c.execute(select(diagnosis_areas.c.status).where(
            diagnosis_areas.c.id == UUID(step["area_id"]))).scalar_one() == "completed"
        assert len(c.execute(select(diagnosis_area_conclusions.c.id).where(
            diagnosis_area_conclusions.c.area_id == UUID(step["area_id"]))).all()) == 1
    current = DiagnosisService(r.store.engine).current(r.actor, cid)
    assert current["current_step"] is None and current["status"] == "needs_review"


def test_area_end_selects_existing_pending_area_without_losing_old_step(indexed_rig):
    r = indexed_rig
    cid, step, proposal, cite = setup_turn(r)
    rid = answer(r, cid, step)
    pending_id = uuid4()
    with r.store.engine.begin() as c:
        previous = c.execute(select(diagnosis_areas).where(
            diagnosis_areas.c.id == UUID(step["area_id"]))).mappings().one()
        c.execute(diagnosis_areas.insert().values(
            id=pending_id, case_id=cid, workflow_id=previous["workflow_id"],
            graph_epoch=0, component_key="Q02", title="合成待生成区域",
            provenance_json={"source": "synthetic_test_pending"}, status="pending"))
        obs_id = c.execute(select(observations.c.id).where(
            observations.c.case_id == cid)).scalar_one()
    candidate = dict(type="conclude_area", component_key="P01",
        finding=cite("P01 是隔离台架的合成检查部件。"),
        assessment="unknown", observation_ids=[str(obs_id)])
    checked = proposal.validate(ProposalContext(r.actor, cid, 2), candidate)
    assert checked["accepted"], checked["issues"]
    lease = r.store.claim_legacy("area-pending", run_id=rid)
    try:
        r.store.stage_diagnosis(lease, checked)
        DiagnosisGraph(r.store, lease, Event()).execute()
    finally:
        lease.close()
    with r.store.engine.connect() as c:
        child = c.execute(select(runs).where(runs.c.parent_run_id == rid)).mappings().one()
        assert child["input_payload"]["area_activation"] == str(pending_id)
        assert child["input_revision"] == 3
        assert c.execute(select(diagnosis_steps.c.status).where(
            diagnosis_steps.c.id == UUID(step["id"]))).scalar_one() == "completed"
    assert DiagnosisService(r.store.engine).current(r.actor, cid)["status"] == "analyzing"


def test_active_run_and_unaudited_retirement_cannot_complete_area(indexed_rig):
    r = indexed_rig
    cid, step, proposal, cite = setup_turn(r)
    rid = answer(r, cid, step)
    # Explicit legacy card is a read-side summary, not a way to bypass a live
    # worker or mark the area complete.
    denied = r.client.post(
        f"/api/v2/cases/{cid}/diagnosis/areas/{step['area_id']}/conclude",
        headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
        json={"expected_revision": 2, "graph_epoch": 0})
    assert denied.status_code == 409 and denied.json()["error"]["code"] == "ACTIVE_RUN"
    with r.store.engine.begin() as c:
        previous = c.execute(select(diagnosis_areas).where(
            diagnosis_areas.c.id == UUID(step["area_id"]))).mappings().one()
        c.execute(diagnosis_areas.insert().values(
            id=uuid4(), case_id=cid, workflow_id=previous["workflow_id"],
            graph_epoch=0, component_key="R03", title="Synthetic unaudited retirement",
            provenance_json={"source": "synthetic_test"}, status="retired",
            retired_reason="Untrusted free-text reason"))
    publish_next(r, cid, rid, proposal, cite)
    with r.store.engine.connect() as c:
        assert c.execute(select(runs.c.error_json).where(
            runs.c.id == rid)).scalar_one()["code"] == "AREA_RETIRED_UNVERIFIED"
        assert c.execute(select(diagnosis_area_conclusions.c.id).where(
            diagnosis_area_conclusions.c.area_id == UUID(step["area_id"]))).first() is None
        assert c.execute(select(cases.c.status).where(cases.c.id == cid)).scalar_one() == "needs_review"


def test_same_spec_same_conditions_conflict_blocks_area_end(indexed_rig):
    """Direct synthetic saved facts isolate the A411 conflict branch, not an AI path."""
    r = indexed_rig
    cid, step, proposal, cite = setup_turn(r)
    rid = answer(r, cid, step)
    standard = next(line for line in (FIX / "extra-synthetic.md").read_text(
        encoding="utf-8").splitlines() if line.startswith("P01 synthetic standard"))
    standard_ref = cite(standard)
    made = spec(r, {"evidence_id": standard_ref["references"][0]["evidence_id"]},
                component_key="P01")
    sid = made["spec"]["id"]
    assert approve(r, sid).status_code == 200
    within = compare(r, sid, value="1.5", unit="V")
    outside = compare(r, sid, value="3", unit="V")
    assert within["result"]["outcome"] == "within_range"
    assert outside["result"]["outcome"] == "out_of_range"
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
    with r.store.engine.connect() as c:
        assert c.execute(select(runs.c.error_json).where(
            runs.c.id == rid)).scalar_one()["code"] == "AREA_CONFLICTING"
        assert c.execute(select(diagnosis_areas.c.status).where(
            diagnosis_areas.c.id == UUID(step["area_id"]))).scalar_one() == "active"
        assert c.execute(select(diagnosis_area_conclusions.c.id).where(
            diagnosis_area_conclusions.c.area_id == UUID(step["area_id"]))).first() is None


def test_old_area_end_checkpoint_rejected_after_epoch_change(indexed_rig):
    r = indexed_rig
    cid, step, proposal, cite = setup_turn(r)
    rid = answer(r, cid, step)
    with r.store.engine.connect() as c:
        obs_id = c.execute(select(observations.c.id).where(
            observations.c.case_id == cid)).scalar_one()
    candidate = dict(type="conclude_area", component_key="P01",
        finding=cite("P01 是隔离台架的合成检查部件。"),
        assessment="unknown", observation_ids=[str(obs_id)])
    checked = proposal.validate(ProposalContext(r.actor, cid, 2), candidate)
    assert checked["accepted"], checked["issues"]
    lease = r.store.claim_legacy("stale-checkpoint", run_id=rid)
    try:
        r.store.stage_diagnosis(lease, checked)
        r.store.finish(lease, result=checked)
        saver = FencedPostgresSaver(r.store, lease)
        config = {"configurable": {"thread_id": saver.workflow_id}}
        # Isolated DB fault boundary: a committed correction advanced the
        # authoritative epoch before the old worker wrote its checkpoint.
        with r.store.engine.begin() as c:
            c.execute(update(cases).where(cases.c.id == cid).values(graph_epoch=1))
        with pytest.raises(LeaseLost):
            saver.get_tuple(config)
    finally:
        lease.close()
    # The previous waiting publication is now historical. Global recovery
    # must skip its stale epoch rather than block unrelated worker starts.
    r.store.reconcile_pending()


@pytest.mark.parametrize("block", ["unavailable", "source_invalid"])
def test_area_does_not_converge_when_incomplete(indexed_rig, block):
    r = indexed_rig
    cid, step, proposal, cite = setup_turn(r)
    rid = answer(r, cid, step, unavailable=block == "unavailable")
    if block == "source_invalid":
        with r.store.engine.begin() as c:
            c.execute(update(case_evidence).where(
                case_evidence.c.case_id == cid,
                case_evidence.c.quote.like("P01%"))
                      .values(needs_review=True, review_reasons=["synthetic_fixture"]))
    publish_next(r, cid, rid, proposal, cite)
    with r.store.engine.connect() as c:
        assert c.execute(select(diagnosis_area_conclusions.c.id).where(
            diagnosis_area_conclusions.c.area_id == UUID(step["area_id"]))).first() is None
        assert c.execute(select(diagnosis_areas.c.status).where(
            diagnosis_areas.c.id == UUID(step["area_id"]))).scalar_one() == "active"
        assert c.execute(select(diagnosis_steps.c.id).where(
            diagnosis_steps.c.case_id == cid,
            diagnosis_steps.c.candidate_json["component_key"].as_string() == "Q02")).first() is None
        assert c.execute(select(cases.c.status).where(cases.c.id == cid)).scalar_one() == "needs_review"
