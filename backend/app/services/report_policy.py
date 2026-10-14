"""The six server-side final-report gates, evaluated against current DB facts."""

from uuid import UUID

from sqlalchemy import select

from app.domain.policies import DomainError
from app.infrastructure.orm import (
    case_evidence,
    cases,
    diagnosis_area_conclusions,
    diagnosis_areas,
    diagnosis_steps,
    measurement_specs,
    runs,
)
from app.repositories.observations import ObservationRepository
from app.services.evidence_scope import source
from app.services.evidence_service import EvidenceService, row_owned


def _ids(values):
    if not isinstance(values, list) or len(values) > 100:
        return None
    try:
        return [UUID(value) for value in values if isinstance(value, str)] if all(
            isinstance(value, str) for value in values) else None
    except (ValueError, TypeError):
        return None


def snapshot(c, actor, case_id, settings, *, lock=False):
    q = select(cases).where(cases.c.id == case_id, cases.c.owner_id == actor)
    case = c.execute(q.with_for_update() if lock else q).mappings().one_or_none()
    if case is None:
        raise DomainError("NOT_FOUND", "Case not found", 404)
    areas = c.execute(select(diagnosis_areas).where(
        diagnosis_areas.c.case_id == case_id,
        diagnosis_areas.c.graph_epoch == case["graph_epoch"])
        .order_by(diagnosis_areas.c.created_at, diagnosis_areas.c.id)
    ).mappings().all()
    cards = {}
    for area in areas:
        card = c.execute(select(diagnosis_area_conclusions).where(
            diagnosis_area_conclusions.c.area_id == area["id"],
            diagnosis_area_conclusions.c.graph_epoch == case["graph_epoch"])
            .order_by(diagnosis_area_conclusions.c.created_revision.desc(),
                      diagnosis_area_conclusions.c.created_at.desc())
            .limit(1)).mappings().one_or_none()
        if card:
            cards[area["id"]] = card
    # Topic and matched-template workbenches permit full question libraries.
    # Preserve the legacy cap for other flows, but let the unchanged final gate see
    # every effective workbench observation instead of failing after the 50th item.
    topic_binding = (case["intake_snapshot"] or {}).get("topic_binding") or {}
    bound_b01 = topic_binding.get("version") in {"2.2.0-b01", "2.2.1-b02"}
    bound_template = (case["intake_snapshot"] or {}).get("workbench_flow") == "template-match-v1"
    effective = ObservationRepository(c).read(
        case_id, None, case["revision"], max_results=None if bound_b01 or bound_template else 50)
    obs = {row["id"]: row for row in effective}
    steps = c.execute(select(diagnosis_steps).where(
        diagnosis_steps.c.case_id == case_id).order_by(diagnosis_steps.c.created_at,
                                                       diagnosis_steps.c.id)).mappings().all()
    return dict(case=case, areas=areas, cards=cards, observations=obs,
                steps={step["id"]: step for step in steps})


def final_gate(c, actor, snap, settings):
    """Return non-sensitive, structured blockers. Every invocation checks live sources."""
    case, areas, cards, obs = (snap[k] for k in
                              ("case", "areas", "cards", "observations"))
    issues = []

    def block(code, area=None):
        item = {"code": code}
        if area is not None:
            item["area_id"] = str(area["id"])
        if item not in issues:
            issues.append(item)

    active = [a for a in areas if a["status"] != "retired"]
    if not active:
        block("NO_EFFECTIVE_AREA")
    if any(a["status"] == "retired" for a in areas):
        block("RETIRED_AREA_UNVERIFIED")
    if c.execute(select(runs.c.id).where(
        runs.c.case_id == case["id"], runs.c.kind == "diagnosis",
        runs.c.status.in_(["queued", "running", "cancel_requested"])).limit(1)).first():
        block("DIAGNOSIS_ACTIVE")
    if case["status"] in {"needs_review", "failed"}:
        block("CASE_NEEDS_REVIEW")
    for entry in case["corpus_manifest"]:
        try:
            _, match = source(c, actor, case, UUID(entry["document_version_id"]),
                              UUID(entry["index_id"]), settings.retrieval_profile)
            if match["status"] != "matched":
                block("APPLICABILITY_UNKNOWN")
        except (DomainError, KeyError, ValueError, TypeError):
            block("SOURCE_INVALID")
    evidence = EvidenceService(None, settings)
    for area in active:
        if area["status"] != "completed":
            block("AREA_UNFINISHED", area)
        card = cards.get(area["id"])
        if card is None:
            block("CONCLUSION_MISSING", area)
            continue
        if card["assessment"] not in {"supported", "ruled_out"}:
            block("CONCLUSION_NOT_FINAL", area)
        if card["needs_review"] or card["created_revision"] > case["revision"]:
            block("CONCLUSION_INVALID", area)
        body = card["content_json"] or {}
        obs_ids = _ids(body.get("observation_ids"))
        source_ids = _ids(body.get("source_evidence_ids"))
        if not obs_ids or not source_ids:
            block("CONCLUSION_BASIS_MISSING", area)
            continue
        for oid in obs_ids:
            row = obs.get(oid)
            if row is None or row["area_id"] != area["id"] or row["payload"].get("checked") is not True:
                block("OBSERVATION_INVALID", area)
        for eid in source_ids:
            try:
                row = row_owned(c, actor, case_evidence, eid)
                valid = evidence.validity(c, actor, row)
                if row["case_id"] != case["id"] or not valid["valid"]:
                    block("SOURCE_INVALID", area)
                elif valid.get("applicability", {}).get("status") != "matched":
                    block("APPLICABILITY_UNKNOWN", area)
            except DomainError:
                block("SOURCE_INVALID", area)
        spec_ids = _ids(body.get("spec_ids", []))
        if spec_ids is None:
            block("SPEC_INVALID", area)
            spec_ids = []
        for sid in spec_ids:
            try:
                spec = row_owned(c, actor, measurement_specs, sid)
                linked = row_owned(c, actor, case_evidence, spec["evidence_id"])
                if (linked["case_id"] != case["id"] or spec["review_status"] != "approved"
                        or spec["needs_review"] or not evidence.validity(c, actor, linked)["valid"]):
                    block("SPEC_INVALID", area)
            except DomainError:
                block("SPEC_INVALID", area)
        if body.get("conflicting") or card["assessment"] == "conflicting":
            block("EVIDENCE_CONFLICT", area)
    if any(row["kind"] == "unavailable" or not row["payload"].get("checked")
           or row.get("needs_review", False) for row in obs.values()):
        block("OBSERVATION_UNRESOLVED")
    groups = {}
    for row in obs.values():
        for item in row["payload"].get("measurements", []):
            if not isinstance(item, dict):
                block("EVIDENCE_CONFLICT")
                continue
            key = (item.get("spec_id"), str(sorted((item.get("conditions") or {}).items())))
            groups.setdefault(key, set()).add(item.get("outcome"))
    if any({"within_range", "out_of_range"} <= outcomes for outcomes in groups.values()):
        block("EVIDENCE_CONFLICT")
    return {"allowed": not issues, "blocking_items": issues,
            "case_revision": case["revision"], "graph_epoch": case["graph_epoch"]}
