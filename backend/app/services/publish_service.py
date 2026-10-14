"""One fenced transaction publishes one current diagnosis check."""

import hashlib
import json
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, text, update

from app.agents.state import ConcludeArea, ProposalContext, ProposeStep
from app.domain.policies import DomainError
from app.infrastructure.event_store import append_event
from app.infrastructure.orm import (
    cases,
    diagnosis_area_conclusions,
    diagnosis_areas,
    diagnosis_publications,
    diagnosis_steps,
    graph_progress,
    jobs,
    observations,
    runs,
)
from app.services.area_lifecycle import close_before_next_area
from app.services.evidence_scope import owner_lock, source
from app.services.run_service import enqueue
from app.validators.proposal import HardGate
from app.validators.repetition import fingerprint


def payload_digest(candidate, validation):
    # The stable identity excludes timing/prose-only validation metadata.
    return hashlib.sha256(json.dumps(candidate, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def publish_waiting(c, store, lease, result, settings):
    """Caller owns the original advisory-lock connection and an open transaction.

    No commit happens here. The caller's final DB-clock fence follows all SQL.
    """
    run_id = lease.job["run_id"]
    preliminary = c.execute(select(runs).where(runs.c.id == run_id)).mappings().one()
    if preliminary["kind"] != "diagnosis" or preliminary["case_id"] is None:
        raise DomainError("DIAGNOSIS_RUN_INVALID", "Diagnosis run required")
    owner = c.execute(select(cases.c.owner_id).where(
        cases.c.id == preliminary["case_id"])).scalar_one()
    # Lock order matches source revocation (owner lock -> case) and API cancel
    # (case -> job -> run); waiting for either cannot invert this order.
    owner_lock(c, owner)
    case = c.execute(select(cases).where(cases.c.id == preliminary["case_id"])
                     .with_for_update()).mappings().one()
    job = c.execute(select(jobs).where(jobs.c.id == lease.job["id"])
                    .with_for_update()).mappings().one()
    run = c.execute(select(runs).where(runs.c.id == run_id)
                    .with_for_update()).mappings().one()
    if case["owner_id"] != owner or lease.lost:
        raise DomainError("DIAGNOSIS_STOPPED", "Diagnosis no longer authorized")
    deadline = job["lease_until"] or lease.final_deadline
    if deadline is None:
        raise DomainError("DIAGNOSIS_STOPPED", "Diagnosis has no valid lease")
    store._finish_valid(lease, deadline)
    progress = c.execute(select(graph_progress).where(
        graph_progress.c.run_id == run_id).with_for_update()).mappings().one()
    if progress["graph_epoch"] != case["graph_epoch"] or progress["turn_id"] != run["turn_id"]:
        raise DomainError("GRAPH_EPOCH_STALE", "Diagnosis graph changed")
    turn_deadline = progress["created_at"] + timedelta(seconds=120)
    if c.execute(select(text("clock_timestamp()"))).scalar_one() >= turn_deadline:
        raise DomainError("MODEL_TURN_TIMEOUT", "Diagnosis turn deadline elapsed")
    if not isinstance(result, dict) or not result.get("accepted"):
        raise DomainError("PROPOSAL_NOT_ACCEPTED", "Candidate was not accepted")
    candidate = ProposeStep.model_validate(result.get("candidate"))
    encoded = candidate.model_dump(mode="json")
    digest = payload_digest(encoded, result)
    previous = c.execute(select(diagnosis_publications).where(
        diagnosis_publications.c.workflow_id == run["workflow_id"],
        diagnosis_publications.c.turn_id == run["turn_id"],
        diagnosis_publications.c.node == "publish").with_for_update()
    ).mappings().one_or_none()
    if previous is not None:
        if previous["payload_hash"] != digest:
            raise DomainError("PUBLICATION_CONFLICT", "Turn already published different content")
        if job["status"] != "completed" or run["status"] != "waiting_input":
            raise DomainError("PUBLICATION_INCONSISTENT", "Published turn state differs")
        return previous["response_json"], deadline
    if job["status"] != "running" or run["status"] != "running":
        raise DomainError("DIAGNOSIS_STOPPED", "Diagnosis no longer active")
    if run["input_revision"] != case["revision"]:
        raise DomainError("REVISION_CONFLICT", "Case changed before publication")
    target_area = run["input_payload"].get("area_activation")
    if target_area:
        area_target = c.execute(select(diagnosis_areas).where(
            diagnosis_areas.c.id == UUID(target_area),
            diagnosis_areas.c.case_id == case["id"],
            diagnosis_areas.c.graph_epoch == case["graph_epoch"])
            .with_for_update()).mappings().one_or_none()
        if (area_target is None or area_target["status"] in {"retired", "stale", "completed"}
                or area_target["component_key"] != candidate.component_key):
            raise DomainError("AREA_ACTIVATION_INVALID", "Candidate belongs to another area")
    prior_step = c.execute(select(diagnosis_steps).where(
        diagnosis_steps.c.case_id == case["id"],
        diagnosis_steps.c.status == "waiting_input").with_for_update()
    ).mappings().one_or_none()
    observation_id = run["input_payload"].get("observation_id")
    if prior_step is not None:
        if not observation_id or progress["step_id"] != prior_step["id"]:
            raise DomainError("ACTIVE_STEP", "Current check is already waiting")
        observation = c.execute(select(observations).where(
            observations.c.id == UUID(observation_id),
            observations.c.case_id == case["id"],
            observations.c.step_id == prior_step["id"],
            observations.c.created_revision <= case["revision"])).mappings().one_or_none()
        successor = c.execute(select(observations.c.id).where(
            observations.c.supersedes_id == UUID(observation_id),
            observations.c.created_revision <= case["revision"])).first()
        if observation is None or successor is not None:
            raise DomainError("OBSERVATION_INVALID", "Saved observation is not current")
    elif observation_id:
        # WP-12 commits the answer and completes the step before queuing the
        # next run. The prior step remains an immutable fact, not a waiting row.
        old_step = c.execute(select(diagnosis_steps).where(
            diagnosis_steps.c.id == progress["step_id"],
            diagnosis_steps.c.case_id == case["id"],
            diagnosis_steps.c.status == "completed").with_for_update()
        ).mappings().one_or_none()
        observation = c.execute(select(observations).where(
            observations.c.id == UUID(observation_id),
            observations.c.case_id == case["id"],
            observations.c.step_id == progress["step_id"],
            observations.c.created_revision == case["revision"])).mappings().one_or_none()
        if old_step is None or observation is None:
            raise DomainError("OBSERVATION_INVALID", "Completed check has no current answer")
        successor = c.execute(select(observations.c.id).where(
            observations.c.supersedes_id == UUID(observation_id))).first()
        if successor is not None:
            raise DomainError("OBSERVATION_INVALID", "Answer was superseded")
    context = ProposalContext(owner, case["id"], case["revision"])
    gate = HardGate(None, settings)
    loaded = gate.load(c, context, candidate)
    if loaded["issues"]:
        raise DomainError("SOURCE_INVALID", "Candidate sources are no longer valid")
    old_checks = c.execute(select(diagnosis_steps.c.candidate_json).join(
        diagnosis_areas, diagnosis_areas.c.id == diagnosis_steps.c.area_id).where(
        diagnosis_steps.c.case_id == case["id"],
        diagnosis_areas.c.graph_epoch == case["graph_epoch"])).scalars().all()
    if not result.get("protocol_decision") and candidate.retest is None and any(
        fingerprint(ProposeStep.model_validate(old)) == fingerprint(candidate)
        for old in old_checks
    ):
        raise DomainError("DUPLICATE_CHECK", "Check already published")
    # Also recheck every frozen source: even unquoted corpus may have been revoked.
    for entry in case["corpus_manifest"]:
        source(c, owner, case, UUID(entry["document_version_id"]),
               UUID(entry["index_id"]), settings.retrieval_profile)
    area = c.execute(select(diagnosis_areas).where(
        diagnosis_areas.c.case_id == case["id"],
        diagnosis_areas.c.graph_epoch == case["graph_epoch"],
        diagnosis_areas.c.component_key == candidate.component_key
    ).with_for_update()).mappings().one_or_none()
    if area is None:
        area_id = uuid4()
        c.execute(diagnosis_areas.insert().values(
            id=area_id, case_id=case["id"], workflow_id=run["workflow_id"],
            graph_epoch=case["graph_epoch"], component_key=candidate.component_key,
            title=candidate.title, provenance_json={"source": "validated_step"},
        ))
    else:
        area_id = area["id"]
        if area["status"] in {"retired", "stale", "completed"}:
            raise DomainError("AREA_NOT_ACTIVE", "Area cannot receive a new check")
    previous_area_id = (prior_step or (old_step if observation_id else None))
    if previous_area_id is not None:
        close_before_next_area(
            c, case=case, actor=owner,
            previous_area_id=previous_area_id["area_id"], next_area_id=area_id,
            run_id=run_id, settings=settings,
        )
    c.execute(update(diagnosis_areas).where(diagnosis_areas.c.id == area_id)
              .values(status="active"))
    ordinal = c.execute(select(text("count(*)")).select_from(diagnosis_steps).where(
        diagnosis_steps.c.case_id == case["id"])).scalar_one() + 1
    step_id = uuid4()
    if prior_step is not None:
        c.execute(update(diagnosis_steps).where(diagnosis_steps.c.id == prior_step["id"])
                  .values(status="completed"))
    c.execute(diagnosis_steps.insert().values(
        id=step_id, case_id=case["id"], area_id=area_id, run_id=run_id,
        turn_id=run["turn_id"], ordinal=ordinal, candidate_json=encoded,
        validation_json={"issues": [], "provenance": result.get("provenance", []),
                         **({"protocol": result["protocol_decision"]} if result.get("protocol_decision") else {})},
        status="waiting_input",
    ))
    revision = case["revision"] + 1
    c.execute(update(cases).where(cases.c.id == case["id"]).values(
        revision=revision, status="waiting_input", updated_at=text("clock_timestamp()")))
    c.execute(update(runs).where(runs.c.id == run_id).values(
        status="waiting_input", output_revision=revision, error_json={}))
    c.execute(update(jobs).where(jobs.c.id == job["id"]).values(
        status="completed", lease_until=None))
    # Progress/checkpoint is deliberately finalized in a later transaction.
    # A crash here leaves an authoritative publication/run/step to reconcile.
    response = {"case_id": str(case["id"]), "step_id": str(step_id),
                "run_id": str(run_id), "output_revision": revision,
                "status": "waiting_input"}
    c.execute(diagnosis_publications.insert().values(
        id=uuid4(), workflow_id=run["workflow_id"], turn_id=run["turn_id"],
        run_id=run_id, case_id=case["id"], step_id=step_id,
        node="publish", payload_hash=digest, output_revision=revision,
        response_json=response))
    append_event(c, run_id, "run.waiting_input",
                 {"step_id": str(step_id), "output_revision": revision})
    # The database clock is checked after every potentially blocking publish
    # statement, before the caller's lease fence and the transaction commit.
    if c.execute(select(text("clock_timestamp()"))).scalar_one() >= turn_deadline:
        raise DomainError("MODEL_TURN_TIMEOUT", "Diagnosis turn deadline elapsed")
    return response, deadline


def publish_area_close(c, store, lease, result, settings):
    """Finish an explicitly proposed area end without manufacturing a check.

    Model text is only an end intent. The card and next-area choice come from
    current database facts while the original advisory connection is fenced.
    """
    run_id = lease.job["run_id"]
    preliminary = c.execute(select(runs).where(runs.c.id == run_id)).mappings().one()
    if preliminary["kind"] != "diagnosis" or preliminary["case_id"] is None:
        raise DomainError("DIAGNOSIS_RUN_INVALID", "Diagnosis run required")
    owner = c.execute(select(cases.c.owner_id).where(
        cases.c.id == preliminary["case_id"])).scalar_one()
    owner_lock(c, owner)
    case = c.execute(select(cases).where(cases.c.id == preliminary["case_id"])
                     .with_for_update()).mappings().one()
    job = c.execute(select(jobs).where(jobs.c.id == lease.job["id"])
                    .with_for_update()).mappings().one()
    run = c.execute(select(runs).where(runs.c.id == run_id)
                    .with_for_update()).mappings().one()
    if case["owner_id"] != owner or lease.lost:
        raise DomainError("DIAGNOSIS_STOPPED", "Diagnosis no longer authorized")
    deadline = job["lease_until"] or lease.final_deadline
    if deadline is None:
        raise DomainError("DIAGNOSIS_STOPPED", "Diagnosis has no valid lease")
    store._finish_valid(lease, deadline)
    progress = c.execute(select(graph_progress).where(
        graph_progress.c.run_id == run_id).with_for_update()).mappings().one()
    if progress["graph_epoch"] != case["graph_epoch"] or progress["turn_id"] != run["turn_id"]:
        raise DomainError("GRAPH_EPOCH_STALE", "Diagnosis graph changed")
    turn_deadline = progress["created_at"] + timedelta(seconds=120)
    if c.execute(select(text("clock_timestamp()"))).scalar_one() >= turn_deadline:
        raise DomainError("MODEL_TURN_TIMEOUT", "Diagnosis turn deadline elapsed")
    if not isinstance(result, dict) or not result.get("accepted"):
        raise DomainError("PROPOSAL_NOT_ACCEPTED", "Candidate was not accepted")
    candidate = ConcludeArea.model_validate(result.get("candidate"))
    if candidate.assessment != "unknown" or result.get("disposition") != "needs_input":
        raise DomainError("AREA_CONCLUSION_UNSUPPORTED", "Only a conservative area end is supported")
    digest = payload_digest(candidate.model_dump(mode="json"), result)
    previous = c.execute(select(diagnosis_publications).where(
        diagnosis_publications.c.workflow_id == run["workflow_id"],
        diagnosis_publications.c.turn_id == run["turn_id"],
        diagnosis_publications.c.node == "area_close").with_for_update()
    ).mappings().one_or_none()
    if previous is not None:
        if previous["payload_hash"] != digest:
            raise DomainError("PUBLICATION_CONFLICT", "Area turn already published different content")
        if job["status"] != "completed" or run["status"] != "succeeded":
            raise DomainError("PUBLICATION_INCONSISTENT", "Area turn state differs")
        return previous["response_json"], deadline
    if job["status"] != "running" or run["status"] != "running":
        raise DomainError("DIAGNOSIS_STOPPED", "Diagnosis no longer active")
    if run["input_revision"] != case["revision"] or not run["input_payload"].get("observation_id"):
        raise DomainError("REVISION_CONFLICT", "Area end requires the current saved observation")
    step = c.execute(select(diagnosis_steps).where(
        diagnosis_steps.c.id == progress["step_id"],
        diagnosis_steps.c.case_id == case["id"],
        diagnosis_steps.c.status == "completed").with_for_update()
    ).mappings().one_or_none()
    observation = c.execute(select(observations).where(
        observations.c.id == UUID(run["input_payload"]["observation_id"]),
        observations.c.case_id == case["id"],
        observations.c.step_id == progress["step_id"],
        observations.c.created_revision == case["revision"])).mappings().one_or_none()
    if step is None or observation is None:
        raise DomainError("OBSERVATION_INVALID", "Current area has no saved answer")
    area = c.execute(select(diagnosis_areas).where(
        diagnosis_areas.c.id == step["area_id"],
        diagnosis_areas.c.case_id == case["id"],
        diagnosis_areas.c.graph_epoch == case["graph_epoch"])
        .with_for_update()).mappings().one_or_none()
    if area is None or area["component_key"] != candidate.component_key:
        raise DomainError("AREA_NOT_READY", "Area end targets another component")
    # Recheck the frozen corpus as well as each cited step source.
    for entry in case["corpus_manifest"]:
        source(c, owner, case, UUID(entry["document_version_id"]),
               UUID(entry["index_id"]), settings.retrieval_profile)
    card_id = close_before_next_area(
        c, case=case, actor=owner, previous_area_id=area["id"],
        next_area_id=None, run_id=run_id, settings=settings,
        allow_unavailable_terminal=bool(result.get("protocol_terminal")))
    terminal = result.get("protocol_terminal")
    if terminal:
        card = c.execute(select(diagnosis_area_conclusions.c.content_json).where(
            diagnosis_area_conclusions.c.id == card_id).with_for_update()).scalar_one()
        c.execute(update(diagnosis_area_conclusions).where(
            diagnosis_area_conclusions.c.id == card_id).values(
                content_json={**card, "protocol_terminal": terminal,
                              "diagnosis": False, "synthetic": True,
                              "formal_usable": False}))
    revision = case["revision"] + 1
    c.execute(update(cases).where(cases.c.id == case["id"]).values(
        revision=revision, status="needs_review", updated_at=text("clock_timestamp()")))
    c.execute(update(runs).where(runs.c.id == run_id).values(
        status="succeeded", output_revision=revision, error_json={}))
    c.execute(update(jobs).where(jobs.c.id == job["id"]).values(
        status="completed", lease_until=None))
    c.execute(update(graph_progress).where(graph_progress.c.id == progress["id"])
              .values(phase="completed"))
    pending = c.execute(select(diagnosis_areas).where(
        diagnosis_areas.c.case_id == case["id"],
        diagnosis_areas.c.graph_epoch == case["graph_epoch"],
        diagnosis_areas.c.status == "pending")
        .order_by(diagnosis_areas.c.created_at, diagnosis_areas.c.id)
        .with_for_update()).mappings().first()
    next_run_id = None
    if pending is not None:
        _, queued = enqueue(c, owner, "diagnosis",
            {"case_id": str(case["id"]), "area_activation": str(pending["id"])},
            case["id"], revision, parent=run, new_turn=True)
        next_run_id = UUID(queued["run_id"])
        next_run = c.execute(select(runs).where(runs.c.id == next_run_id)).mappings().one()
        c.execute(graph_progress.insert().values(
            workflow_id=next_run["workflow_id"], turn_id=next_run["turn_id"],
            case_id=case["id"], run_id=next_run_id,
            graph_epoch=case["graph_epoch"], phase="queued"))
        c.execute(update(cases).where(cases.c.id == case["id"]).values(status="analyzing"))
    response = {"case_id": str(case["id"]), "area_id": str(area["id"]),
                "card_id": str(card_id), "run_id": str(run_id),
                "next_run_id": str(next_run_id) if next_run_id else None,
                "output_revision": revision, "status": "completed"}
    c.execute(diagnosis_publications.insert().values(
        id=uuid4(), workflow_id=run["workflow_id"], turn_id=run["turn_id"],
        run_id=run_id, case_id=case["id"], step_id=None,
        node="area_close", payload_hash=digest, output_revision=revision,
        response_json=response))
    append_event(c, run_id, "run.succeeded", {
        "area_id": str(area["id"]), "output_revision": revision,
        "next_run_id": str(next_run_id) if next_run_id else None})
    if c.execute(select(text("clock_timestamp()"))).scalar_one() >= turn_deadline:
        raise DomainError("MODEL_TURN_TIMEOUT", "Diagnosis turn deadline elapsed")
    return response, deadline
