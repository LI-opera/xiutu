"""Shared current-qualification and owner serialization for WP06."""

import hashlib

from sqlalchemy import select, text, update

from app.domain.policies import DomainError
from app.infrastructure.orm import (
    case_evidence,
    cases,
    documents,
    index_versions,
    measurement_comparisons,
    measurement_specs,
)
from app.infrastructure.orm import document_versions as versions
from app.retrieval.eligibility import applicability, exclusion


def owner_lock(c, actor):
    key = int.from_bytes(
        hashlib.sha256(("wp06:" + str(actor)).encode()).digest()[:8], "big", signed=True
    )
    c.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def owned_case(c, actor, cid):
    row = (
        c.execute(select(cases).where(cases.c.id == cid, cases.c.owner_id == actor))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise DomainError("NOT_FOUND", "Case not found", 404)
    return row


def freeze_manifest(c, actor, vehicle, profile):
    rows = (
        c.execute(
            select(versions)
            .join(documents, documents.c.id == versions.c.document_id)
            .where(documents.c.owner_id == actor)
            .order_by(versions.c.id)
            .with_for_update(of=versions)
        )
        .mappings()
        .all()
    )
    out = []
    for row in rows:
        if (
            exclusion(row, profile)
            or applicability(row["review_snapshot"].get("scope", {}), vehicle)["status"]
            == "mismatch"
        ):
            continue
        index = (
            c.execute(
                select(index_versions).where(
                    index_versions.c.id == row["active_index_id"],
                    index_versions.c.status == "ready",
                    index_versions.c.profile == profile,
                )
            )
            .mappings()
            .one_or_none()
        )
        if index:
            out.append(
                dict(
                    document_version_id=str(row["id"]),
                    index_id=str(index["id"]),
                    authorization_epoch=row["authorization_epoch"],
                    profile=profile,
                )
            )
    return out


def invalidate_source(c, vid):
    reason = ["source_review_changed"]
    c.execute(
        update(case_evidence)
        .where(case_evidence.c.document_version_id == vid)
        .values(needs_review=True, review_reasons=reason)
    )
    eids = select(case_evidence.c.id).where(case_evidence.c.document_version_id == vid)
    c.execute(
        update(measurement_specs)
        .where(measurement_specs.c.evidence_id.in_(eids))
        .values(needs_review=True, review_reasons=reason)
    )
    sids = select(measurement_specs.c.id).where(measurement_specs.c.evidence_id.in_(eids))
    c.execute(
        update(measurement_comparisons)
        .where(measurement_comparisons.c.spec_id.in_(sids))
        .values(needs_review=True, review_reasons=reason)
    )
    # Includes a frozen session which has not bound a chunk yet.
    c.execute(
        text(
            "UPDATE cases SET status='needs_review' WHERE corpus_manifest @> CAST(:entry AS jsonb)"
        ),
        {"entry": '[{"document_version_id":"' + str(vid) + '"}]'},
    )
    # WP-12 cards preserve their historical content but cannot remain current
    # after any frozen source in the session loses authorization.
    c.execute(
        text("""
            UPDATE diagnosis_area_conclusions
               SET needs_review=true, review_reason='source_review_changed'
             WHERE case_id IN (
                 SELECT id FROM cases
                  WHERE corpus_manifest @> CAST(:entry AS jsonb)
             )
        """),
        {"entry": '[{"document_version_id":"' + str(vid) + '"}]'},
    )


def source(c, actor, case, vid, iid, profile):
    entry = next(
        (
            x
            for x in case["corpus_manifest"]
            if x["document_version_id"] == str(vid) and x["index_id"] == str(iid)
        ),
        None,
    )
    if not entry:
        raise DomainError("CORPUS_NOT_ALLOWED", "Source is outside frozen case corpus")
    row = (
        c.execute(
            select(versions)
            .join(documents, documents.c.id == versions.c.document_id)
            .where(versions.c.id == vid, documents.c.owner_id == actor)
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise DomainError("NOT_FOUND", "Source not found", 404)
    if (
        exclusion(row, profile)
        or entry.get("profile") != profile
        or entry.get("authorization_epoch") != row["authorization_epoch"]
    ):
        raise DomainError("SOURCE_INVALID", "Source authorization changed")
    index = (
        c.execute(
            select(index_versions).where(
                index_versions.c.id == iid,
                index_versions.c.document_version_id == vid,
                index_versions.c.status == "ready",
                index_versions.c.profile == profile,
            )
        )
        .mappings()
        .one_or_none()
    )
    if index is None:
        raise DomainError("INDEX_INVALID", "Frozen index unavailable")
    match = applicability(row["review_snapshot"].get("scope", {}), case["vehicle_json"])
    if match["status"] == "mismatch":
        raise DomainError("SCOPE_MISMATCH", "Source scope conflicts with vehicle")
    return row, match
