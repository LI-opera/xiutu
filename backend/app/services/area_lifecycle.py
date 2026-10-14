"""Conservative, fenced area closure inside a diagnosis publication transaction."""

from uuid import UUID, uuid4

from sqlalchemy import select, update

from app.domain.policies import DomainError
from app.infrastructure.event_store import append_event
from app.infrastructure.orm import (
    case_evidence, diagnosis_area_conclusions, diagnosis_areas, diagnosis_steps,
    jobs, measurement_comparisons, runs,
)
from app.repositories.observations import ObservationRepository
from app.services.evidence_service import EvidenceService, row_owned


def close_before_next_area(c, *, case, actor, previous_area_id, next_area_id,
                           run_id, settings, allow_unavailable_terminal=False):
    """Close only when this publication leaves a fully checked, valid area.

    The caller holds the owner/case/advisory locks and performs the final lease
    and DB-clock checks after this function. Any rejection rolls back the entire
    publication, including a card inserted here.
    """
    if next_area_id is not None and previous_area_id == next_area_id:
        return None
    areas = c.execute(select(diagnosis_areas).where(
        diagnosis_areas.c.case_id == case["id"],
        diagnosis_areas.c.graph_epoch == case["graph_epoch"])
        .order_by(diagnosis_areas.c.created_at, diagnosis_areas.c.id)
        .with_for_update()).mappings().all()
    # Retirement is not implemented by the trusted service yet. A row with a
    # reason alone has no merge/duplicate evidence or audit event and cannot
    # remove a pending area from the completion calculation.
    if any(item["status"] == "retired" for item in areas):
        raise DomainError("AREA_RETIRED_UNVERIFIED", "Retired area lacks trusted merge evidence")
    pending = [item for item in areas if item["status"] == "pending"]
    if next_area_id is not None and pending and pending[0]["id"] != next_area_id:
        raise DomainError("NEXT_AREA_MISMATCH", "An older unfinished area must be selected")
    observations, source_ids = completion_basis(
        c, case=case, actor=actor, area_id=previous_area_id,
        run_id=run_id, settings=settings, expected_status="active",
        allow_unavailable_terminal=allow_unavailable_terminal)
    existing = c.execute(select(diagnosis_area_conclusions).where(
        diagnosis_area_conclusions.c.area_id == previous_area_id,
        diagnosis_area_conclusions.c.created_revision == case["revision"])
        .with_for_update()).mappings().one_or_none()
    if existing is not None:
        if existing["needs_review"] or existing["assessment"] != "unknown":
            raise DomainError("AREA_NOT_READY", "Previous area card is not current")
        card_id = existing["id"]
    else:
        card_id = uuid4()
        c.execute(diagnosis_area_conclusions.insert().values(
            id=card_id, case_id=case["id"], area_id=previous_area_id,
            graph_epoch=case["graph_epoch"], created_revision=case["revision"],
            assessment="unknown", content_json={
                "observation_ids": [str(obs["id"]) for obs in observations],
                "source_evidence_ids": sorted(source_ids),
                "basis": "observations_without_trusted_conclusion",
                "diagnosis": False,
            }))
    c.execute(update(diagnosis_areas).where(diagnosis_areas.c.id == previous_area_id)
              .values(status="completed"))
    append_event(c, run_id, "area.completed", {
        "area_id": str(previous_area_id), "card_id": str(card_id),
        "next_area_id": str(next_area_id), "assessment": "unknown",
    })
    return card_id


def completion_basis(c, *, case, actor, area_id, run_id, settings,
                     expected_status, allow_unavailable_terminal=False):
    """Recheck the same bounded facts for publishing and later activation.

    The caller owns the owner/case locks. Publication excludes its own running
    run; an activation excludes none and requires every earlier task terminal.
    """
    area = c.execute(select(diagnosis_areas).where(
        diagnosis_areas.c.id == area_id,
        diagnosis_areas.c.case_id == case["id"],
        diagnosis_areas.c.graph_epoch == case["graph_epoch"])
        .with_for_update()).mappings().one_or_none()
    if area is None or area["status"] != expected_status:
        raise DomainError("AREA_NOT_READY", "Previous area is not ready")
    steps = c.execute(select(diagnosis_steps).where(
        diagnosis_steps.c.area_id == area_id,
        diagnosis_steps.c.case_id == case["id"]).with_for_update()
    ).mappings().all()
    if not steps or any(step["status"] != "completed" for step in steps):
        raise DomainError("AREA_NOT_READY", "Previous area has unanswered checks")
    # A second active diagnosis run may never be silently treated as completion.
    active_query = select(runs.c.id).join(jobs, jobs.c.run_id == runs.c.id).where(
        runs.c.case_id == case["id"], runs.c.kind == "diagnosis",
        jobs.c.status.in_(["queued", "running"]))
    if run_id is not None:
        active_query = active_query.where(runs.c.id != run_id)
    active = c.execute(active_query).first()
    if active:
        raise DomainError("AREA_NOT_READY", "Another diagnosis task is active")
    observations = ObservationRepository(c).read(
        case["id"], area_id, case["revision"])
    by_step = {obs["step_id"]: obs for obs in observations}
    if any(step["id"] not in by_step for step in steps):
        raise DomainError("AREA_NOT_READY", "Previous area has an unanswered check")
    evidence = EvidenceService(None, settings)
    source_ids = set()
    groups = {}
    for step in steps:
        obs = by_step[step["id"]]
        if ((obs["kind"] == "unavailable" and not allow_unavailable_terminal)
                or (obs["kind"] != "unavailable" and obs["payload"].get("checked") is not True)):
            raise DomainError("AREA_NEEDS_INPUT", "Previous area needs an actual check")
        candidate = step["candidate_json"]
        claims = [candidate["purpose"], candidate.get("location"),
                  *candidate.get("prerequisites", []), *candidate.get("actions", []),
                  *candidate.get("input", {}).get("choices", [])]
        for claim in claims:
            if not claim:
                continue
            for ref in claim.get("references", []):
                try:
                    ev = row_owned(c, actor, case_evidence, UUID(ref["evidence_id"]))
                    if (ev["case_id"] != case["id"] or
                            str(ev["document_version_id"]) != ref["document_version_id"] or
                            not evidence.validity(c, actor, ev)["valid"]):
                        raise ValueError()
                except (DomainError, ValueError, KeyError):
                    raise DomainError("AREA_SOURCE_INVALID", "Previous area source is invalid") from None
                source_ids.add(str(ev["id"]))
        for item in obs["payload"].get("measurements", []):
            key = (item["spec_id"], tuple(sorted(item["conditions"].items())))
            groups.setdefault(key, set()).add(item["outcome"])
            try:
                comp = row_owned(c, actor, measurement_comparisons,
                                 UUID(item["comparison_id"]))
                if (comp["case_id"] != case["id"] or
                        str(comp["spec_id"]) != item["spec_id"] or
                        not evidence.get_comparison(actor, comp["id"],
                                                    connection=c)["current_validity"]["valid"]):
                    raise ValueError()
            except (DomainError, ValueError, KeyError):
                raise DomainError("AREA_SOURCE_INVALID", "Previous area comparison is invalid") from None
    if not source_ids:
        raise DomainError("AREA_SOURCE_INVALID", "Previous area has no current source")
    if any({"within_range", "out_of_range"} <= outcomes for outcomes in groups.values()):
        raise DomainError("AREA_CONFLICTING", "Previous area observations conflict")
    return observations, source_ids
