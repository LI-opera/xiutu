import hashlib
from decimal import Decimal
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, update

from app.domain.policies import DomainError
from app.infrastructure.orm import case_evidence as evidence
from app.infrastructure.orm import chunk_embeddings, chunks, document_versions
from app.infrastructure.orm import measurement_comparisons as comparisons
from app.infrastructure.orm import measurement_spec_reviews as reviews
from app.infrastructure.orm import measurement_specs as specs
from app.infrastructure.uow import UnitOfWork
from app.services.evidence_scope import owned_case, owner_lock, source
from app.services.run_service import idempotent
from app.tools.measurement import MeasurementComparator


def encoded(row):
    # No decimal number passes through float JSON encoding.
    d = dict(row)
    for key in ["lower_value", "upper_value"]:
        if key in d and d[key] is not None:
            d[key] = str(d[key])
    return jsonable_encoder(d)


def row_owned(c, actor, table, identifier):
    from app.infrastructure.orm import cases

    if table is evidence:
        query = select(table).join(cases, cases.c.id == table.c.case_id)
    elif table is specs:
        query = (
            select(table)
            .join(evidence, evidence.c.id == table.c.evidence_id)
            .join(cases, cases.c.id == evidence.c.case_id)
        )
    else:
        query = select(table).join(cases, cases.c.id == table.c.case_id)
    row = (
        c.execute(query.where(table.c.id == identifier, cases.c.owner_id == actor))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise DomainError("NOT_FOUND", "Resource not found", 404)
    return row


class EvidenceService:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings

    def search(self, actor, cid, body):
        from app.domain.retrieval import SearchInput
        from app.retrieval.service import RetrievalService

        with UnitOfWork(self.engine) as u:
            case = owned_case(u.connection, actor, cid)
        vehicle = {k: v for k, v in case["vehicle_json"].items() if k != "vin"}
        data = SearchInput(query=body.query, vehicle_scope=vehicle, top_k=body.top_k)
        return RetrievalService(self.engine, self.settings).search(
            actor, data, manifest=case["corpus_manifest"]
        )

    def validity(self, c, actor, row):
        if row["needs_review"]:
            return dict(valid=False, reasons=row["review_reasons"])
        case = owned_case(c, actor, row["case_id"])
        try:
            version, match = source(
                c,
                actor,
                case,
                row["document_version_id"],
                row["index_id"],
                self.settings.retrieval_profile,
            )
            chunk = (
                c.execute(
                    select(chunks).where(
                        chunks.c.id == row["chunk_id"],
                        chunks.c.document_version_id == row["document_version_id"],
                    )
                )
                .mappings()
                .one_or_none()
            )
            if (
                chunk is None
                or chunk["text"][row["start_offset"] : row["end_offset"]] != row["quote"]
                or hashlib.sha256(row["quote"].encode()).hexdigest() != row["content_hash"]
                or chunk["text_hash"] != row["chunk_hash"]
                or row["locator"]["source"] != chunk["locator_json"]
            ):
                return dict(valid=False, reasons=["citation_integrity"])
            return dict(valid=True, reasons=[], applicability=match)
        except DomainError as exc:
            return dict(valid=False, reasons=[exc.code])

    def evidence_body(self, c, actor, row):
        locator = row["locator"]
        source_locator = locator.get("source") if isinstance(locator, dict) else None
        source_locator = source_locator if isinstance(source_locator, dict) else {}
        version = (
            c.execute(
                select(document_versions).where(
                    document_versions.c.id == row["document_version_id"],
                    document_versions.c.document_id == locator.get("document_id"),
                )
            )
            .mappings()
            .one_or_none()
        )
        kind = "pdf" if version and version["mime"] == "application/pdf" else "text"
        base = (
            f"/api/v2/documents/{locator.get('document_id')}/versions/"
            f"{row['document_version_id']}/content"
        )
        page = source_locator.get("page")
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            page = None
        page_count = version["page_count"] if version else None
        needs_ocr = bool(version and version["parse_status"] == "needs_ocr")
        if kind == "text":
            status, content_url, image_status = "available", base, "not_applicable"
        elif page is None:
            status, content_url, image_status = "page_missing", None, "unavailable"
        elif page_count is not None and page > page_count:
            status, content_url, image_status = "mapping_missing", None, "unavailable"
        else:
            status = "needs_ocr" if needs_ocr else "available"
            content_url = f"{base}?page={page}#page={page}"
            image_status = "unavailable"
        source_access = dict(
            kind=kind,
            status=status,
            page=page,
            page_count=page_count,
            needs_ocr=needs_ocr,
            content_url=content_url,
            page_image_url=None,
            page_image_status=image_status,
        )
        return dict(
            evidence_id=str(row["id"]),
            snapshot=encoded(row),
            current_validity=self.validity(c, actor, row),
            synthetic=row["profile"] == "synthetic",
            source_content_url=content_url,
            source_access=source_access,
        )

    def bind(self, actor, cid, data, key, *, connection=None):
        with UnitOfWork(self.engine, connection=connection) as u:
            c = u.connection
            owner_lock(c, actor)
            case = owned_case(c, actor, cid)

            def action():
                version, match = source(
                    c,
                    actor,
                    case,
                    data.document_version_id,
                    data.index_id,
                    self.settings.retrieval_profile,
                )
                chunk = (
                    c.execute(
                        select(chunks)
                        .join(chunk_embeddings, chunk_embeddings.c.chunk_id == chunks.c.id)
                        .where(
                            chunks.c.id == data.chunk_id,
                            chunks.c.document_version_id == data.document_version_id,
                            chunk_embeddings.c.index_id == data.index_id,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if chunk is None:
                    raise DomainError(
                        "CITATION_INVALID", "Chunk/version/index relationship invalid", 422
                    )
                if (
                    data.end > len(chunk["text"])
                    or chunk["text"][data.start : data.end] != data.quote
                ):
                    raise DomainError(
                        "CITATION_INVALID", "Quote is not the exact source slice", 422
                    )
                old = (
                    c.execute(
                        select(evidence).where(
                            evidence.c.case_id == cid,
                            evidence.c.chunk_id == data.chunk_id,
                            evidence.c.index_id == data.index_id,
                            evidence.c.start_offset == data.start,
                            evidence.c.end_offset == data.end,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if old:
                    return 200, self.evidence_body(c, actor, old)
                row = (
                    c.execute(
                        evidence.insert()
                        .values(
                            case_id=cid,
                            document_version_id=data.document_version_id,
                            chunk_id=data.chunk_id,
                            index_id=data.index_id,
                            authorization_epoch=version["authorization_epoch"],
                            start_offset=data.start,
                            end_offset=data.end,
                            quote=data.quote,
                            content_hash=hashlib.sha256(data.quote.encode()).hexdigest(),
                            chunk_hash=chunk["text_hash"],
                            locator=dict(
                                document_id=str(version["document_id"]),
                                source=chunk["locator_json"],
                                start=data.start,
                                end=data.end,
                                offset_unit="unicode_codepoint",
                            ),
                            applicability=match,
                            review_snapshot=version["review_snapshot"],
                            profile=self.settings.retrieval_profile,
                        )
                        .returning(evidence)
                    )
                    .mappings()
                    .one()
                )
                return 201, self.evidence_body(c, actor, row)

            return idempotent(
                c, actor, "bind:" + str(cid), key, data.model_dump(mode="json"), action
            )

    def get(self, actor, eid):
        with UnitOfWork(self.engine) as u:
            owner_lock(u.connection, actor)
            row = row_owned(u.connection, actor, evidence, eid)
            return self.evidence_body(u.connection, actor, row)

    def spec_body(self, c, actor, row):
        ev = row_owned(c, actor, evidence, row["evidence_id"])
        history = (
            c.execute(
                select(reviews)
                .where(reviews.c.spec_id == row["id"])
                .order_by(reviews.c.created_at, reviews.c.id)
            )
            .mappings()
            .all()
        )
        return dict(
            spec=encoded(row),
            source=self.evidence_body(c, actor, ev),
            review_history=[encoded(x) for x in history],
        )

    def create_spec(self, actor, data, key):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            owner_lock(c, actor)

            def action():
                ev = row_owned(c, actor, evidence, data.evidence_id)
                if not self.validity(c, actor, ev)["valid"]:
                    raise DomainError("SOURCE_INVALID", "Evidence requires review")
                identifier = uuid4()
                root = identifier
                version = 1
                if data.supersedes_id:
                    prior = row_owned(c, actor, specs, data.supersedes_id)
                    prior_ev = row_owned(c, actor, evidence, prior["evidence_id"])
                    if (
                        prior_ev["case_id"] != ev["case_id"]
                        or prior["definition"]["component_key"] != data.component_key
                        or prior["definition"]["quantity"] != data.quantity
                    ):
                        raise DomainError(
                            "SPEC_LINEAGE_INVALID",
                            "Spec lineage must share case, component and quantity",
                        )
                    if c.execute(
                        select(specs.c.id).where(specs.c.supersedes_id == prior["id"])
                    ).first():
                        raise DomainError("SPEC_SUPERSEDED", "A successor already exists")
                    root, version = prior["spec_root_id"], prior["version"] + 1
                row = (
                    c.execute(
                        specs.insert()
                        .values(
                            id=identifier,
                            evidence_id=data.evidence_id,
                            spec_root_id=root,
                            supersedes_id=data.supersedes_id,
                            version=version,
                            definition=data.model_dump(mode="json"),
                            lower_value=Decimal(data.lower) if data.lower is not None else None,
                            upper_value=Decimal(data.upper) if data.upper is not None else None,
                            lower_inclusive=data.lower_inclusive,
                            upper_inclusive=data.upper_inclusive,
                        )
                        .returning(specs)
                    )
                    .mappings()
                    .one()
                )
                return 201, self.spec_body(c, actor, row)

            return idempotent(c, actor, "create_spec", key, data.model_dump(mode="json"), action)

    def get_spec(self, actor, sid):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            owner_lock(c, actor)
            return self.spec_body(c, actor, row_owned(c, actor, specs, sid))

    def review_spec(self, actor, sid, data, key):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            owner_lock(c, actor)

            def action():
                row = row_owned(c, actor, specs, sid)
                ev = row_owned(c, actor, evidence, row["evidence_id"])
                valid = self.validity(c, actor, ev)
                if data.decision == "approved":
                    if row["needs_review"] or not valid["valid"]:
                        raise DomainError(
                            "SOURCE_INVALID", "Create a new reviewed specification version"
                        )
                    if valid["applicability"]["status"] != "matched":
                        raise DomainError("SCOPE_UNKNOWN", "Exact vehicle applicability required")
                c.execute(
                    reviews.insert().values(
                        spec_id=sid, actor_id=actor, decision=data.decision, note=data.note
                    )
                )
                if data.decision != "approved":
                    c.execute(
                        update(comparisons)
                        .where(comparisons.c.spec_id == sid)
                        .values(needs_review=True, review_reasons=["spec_review_changed"])
                    )
                row = (
                    c.execute(
                        update(specs)
                        .where(specs.c.id == sid)
                        .values(review_status=data.decision)
                        .returning(specs)
                    )
                    .mappings()
                    .one()
                )
                return 200, self.spec_body(c, actor, row)

            return idempotent(
                c, actor, "spec_review:" + str(sid), key, data.model_dump(mode="json"), action
            )

    def compare(self, actor, sid, data, key, *, connection=None):
        with UnitOfWork(self.engine, connection=connection) as u:
            c = u.connection
            owner_lock(c, actor)

            def action():
                row = row_owned(c, actor, specs, sid)
                ev = row_owned(c, actor, evidence, row["evidence_id"])
                valid = self.validity(c, actor, ev)
                result = MeasurementComparator.compare(row["definition"], data)
                if row["needs_review"] or not valid["valid"]:
                    result.update(outcome="evidence_invalid", converted=None, converted_exact=None)
                elif row["review_status"] != "approved":
                    result.update(outcome="spec_not_approved", converted=None, converted_exact=None)
                elif valid["applicability"]["status"] != "matched":
                    result.update(
                        outcome="scope_" + valid["applicability"]["status"],
                        converted=None,
                        converted_exact=None,
                    )
                result.update(
                    spec_id=str(sid),
                    spec_root_id=str(row["spec_root_id"]),
                    spec_version=row["version"],
                    spec_definition=row["definition"],
                    evidence_id=str(ev["id"]),
                    provenance=self.evidence_body(c, actor, ev),
                    synthetic=ev["profile"] == "synthetic",
                    diagnosis=False,
                )
                saved = (
                    c.execute(
                        comparisons.insert()
                        .values(spec_id=sid, case_id=ev["case_id"], result=result)
                        .returning(comparisons)
                    )
                    .mappings()
                    .one()
                )
                return 201, encoded(saved)

            return idempotent(
                c, actor, "compare:" + str(sid), key, data.model_dump(mode="json"), action
            )

    def get_comparison(self, actor, identifier, *, connection=None):
        with UnitOfWork(self.engine, connection=connection) as u:
            c = u.connection
            owner_lock(c, actor)
            row = row_owned(c, actor, comparisons, identifier)
            spec = row_owned(c, actor, specs, row["spec_id"])
            ev = row_owned(c, actor, evidence, spec["evidence_id"])
            valid = self.validity(c, actor, ev)
            if row["needs_review"] or spec["needs_review"] or spec["review_status"] != "approved":
                valid = dict(valid=False, reasons=["spec_or_result_requires_review"])
            return dict(comparison=encoded(row), current_validity=valid)

    def validate_references(self, actor, cid, evidence_ids, spec_ids=(), *, formal=True):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            owner_lock(c, actor)
            owned_case(c, actor, cid)
            reasons = []
            if not evidence_ids:
                reasons.append("evidence_required")
            for eid in evidence_ids:
                ev = row_owned(c, actor, evidence, eid)
                if ev["case_id"] != cid:
                    raise DomainError("CITATION_INVALID", "Evidence belongs to another case")
                valid = self.validity(c, actor, ev)
                if not valid["valid"]:
                    reasons.extend(valid["reasons"])
                elif valid["applicability"]["status"] != "matched":
                    reasons.append("scope_not_matched")
                if formal and ev["profile"] == "synthetic":
                    reasons.append("synthetic_not_formal")
            for sid in spec_ids:
                spec = row_owned(c, actor, specs, sid)
                if spec["evidence_id"] not in evidence_ids:
                    reasons.append("spec_evidence_required")
                if spec["needs_review"] or spec["review_status"] != "approved":
                    reasons.append("spec_not_approved")
            return dict(
                allowed=not reasons,
                reasons=sorted(set(reasons)),
                formal=formal,
                report_implemented=False,
                semantic_support_verified=False,
            )
