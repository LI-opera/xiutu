import hashlib
from uuid import UUID, uuid4

from sqlalchemy import select, tuple_, update

from app.domain.documents import IngestError
from app.domain.policies import DomainError
from app.infrastructure.orm import chunks, document_reviews, documents, index_versions
from app.infrastructure.orm import document_versions as versions
from app.infrastructure.storage import Storage
from app.infrastructure.uow import UnitOfWork
from app.retrieval.eligibility import exclusion
from app.retrieval.parsers import markdown, pdf
from app.services.case_service import CaseService
from app.services.index_service import schedule
from app.services.run_service import enqueue, idempotent


def owned(conn, actor, document_id, version_id=None, lock=False):
    query = select(documents).where(documents.c.id == document_id, documents.c.owner_id == actor)
    if lock:
        query = query.with_for_update()
    row = conn.execute(query).mappings().one_or_none()
    if row is None:
        raise DomainError("NOT_FOUND", "Document not found", 404)
    if version_id is None:
        return row
    query = select(versions).where(
        versions.c.document_id == document_id, versions.c.id == version_id
    )
    if lock:
        query = query.with_for_update()
    row = conn.execute(query).mappings().one_or_none()
    if row is None:
        raise DomainError("NOT_FOUND", "Version not found", 404)
    return row


def safety(row, conn, profile):
    active = (
        conn.execute(
            select(index_versions).where(
                index_versions.c.id == row["active_index_id"], index_versions.c.status == "ready"
            )
        )
        .mappings()
        .one_or_none()
    )
    building = (
        conn.execute(
            select(index_versions).where(
                index_versions.c.document_version_id == row["id"],
                index_versions.c.status == "building",
            )
        )
        .mappings()
        .one_or_none()
    )
    latest = (
        conn.execute(
            select(index_versions)
            .where(index_versions.c.document_version_id == row["id"])
            .order_by(index_versions.c.created_at.desc(), index_versions.c.id.desc())
            .limit(1)
        )
        .mappings()
        .one_or_none()
    )
    reason = exclusion(row, profile)
    usable = active is not None and not reason and active["profile"] == profile
    return dict(
        index_status="building"
        if building
        else "ready"
        if usable
        else "failed"
        if latest is not None and latest["status"] == "failed" and not reason
        else "index_pending"
        if not reason
        else "blocked",
        index_implemented=True,
        formal_usable=usable and profile == "formal",
        active_index_id=str(row["active_index_id"]) if row["active_index_id"] else None,
        index_run_id=str(building["run_id"])
        if building
        else str(latest["run_id"])
        if latest
        else None,
        last_index_status=latest["status"] if latest else None,
        index_error=latest["error_json"] if latest else {},
        index_exclusion=reason,
    )


class DocumentService:
    def __init__(self, engine, settings, secret):
        self.engine = engine
        self.settings = settings
        self.storage = Storage(settings.data_path)
        # Distinct cursor HMAC domain prevents cases/documents cursor substitution.
        self.cursors = CaseService(engine, hashlib.sha256(b"documents:" + secret).digest())

    def cleanup_candidate(self, key):
        if not key:
            return
        try:
            with self.engine.connect() as conn:
                referenced = conn.execute(
                    select(versions.c.id).where(versions.c.storage_key == key)
                ).first()
            if not referenced:
                self.storage.discard(key)
        except Exception:
            # Ambiguous commit/DB outage: retain orphan candidate, never remove a winner.
            pass

    def upload(self, actor, data, upload, key):
        digest = upload.digest.hexdigest()
        raw = self.storage.read(upload.key, digest)
        try:
            if upload.suffix == ".pdf":
                pdf.reader(raw)
                mime = "application/pdf"
            else:
                markdown.decode(raw)
                mime = "text/markdown"
        except IngestError as exc:
            raise DomainError(exc.code, "Unsupported or invalid source", 415) from None
        metadata = data.model_dump(mode="json", exclude={"document_id"})
        body = dict(
            metadata=metadata,
            document_id=str(data.document_id) if data.document_id else None,
            sha256=digest,
            mime=mime,
        )
        with UnitOfWork(self.engine) as u:
            conn = u.connection
            if data.document_id:
                owned(conn, actor, data.document_id)

            def action():
                identifier = data.document_id or uuid4()
                if data.document_id:
                    # Serialize same-logical-document dedup before checking hash.
                    owned(conn, actor, identifier, lock=True)
                else:
                    conn.execute(
                        documents.insert().values(
                            id=identifier,
                            owner_id=actor,
                            title=data.title,
                            source_kind=data.source_kind,
                        )
                    )
                old = (
                    conn.execute(
                        select(versions).where(
                            versions.c.document_id == identifier, versions.c.sha256 == digest
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if old:
                    if old["metadata_json"] != metadata or old["mime"] != mime:
                        raise DomainError(
                            "METADATA_CONFLICT", "Identical source has different immutable metadata"
                        )
                    return 200, dict(
                        document_id=str(identifier),
                        version_id=str(old["id"]),
                        run_id=str(old["current_run_id"]),
                        reused=True,
                    )
                vid = uuid4()
                conn.execute(
                    versions.insert().values(
                        id=vid,
                        document_id=identifier,
                        sha256=digest,
                        storage_key=upload.key,
                        mime=mime,
                        metadata_json=metadata,
                        scope_json=metadata["scope"],
                    )
                )
                _, run = enqueue(conn, actor, "ingest", dict(version_id=str(vid)))
                conn.execute(
                    update(versions)
                    .where(versions.c.id == vid)
                    .values(current_run_id=UUID(run["run_id"]))
                )
                return 202, dict(
                    document_id=str(identifier),
                    version_id=str(vid),
                    run_id=run["run_id"],
                    reused=False,
                )

            return idempotent(conn, actor, "POST documents", key, body, action)

    def list(self, actor, limit, cursor):
        after = self.cursors.decode_cursor(actor, cursor) if cursor else None
        with UnitOfWork(self.engine) as u:
            query = select(documents).where(documents.c.owner_id == actor)
            if after:
                query = query.where(tuple_(documents.c.created_at, documents.c.id) < tuple_(*after))
            rows = (
                u.connection.execute(
                    query.order_by(documents.c.created_at.desc(), documents.c.id.desc()).limit(
                        limit + 1
                    )
                )
                .mappings()
                .all()
            )
            items = []
            for row in rows[:limit]:
                latest = u.connection.execute(
                    select(versions.c.id)
                    .where(versions.c.document_id == row["id"])
                    .order_by(versions.c.created_at.desc(), versions.c.id.desc())
                    .limit(1)
                ).scalar_one_or_none()
                items.append(
                    dict(
                        id=str(row["id"]),
                        title=row["title"],
                        source_kind=row["source_kind"],
                        created_at=row["created_at"].isoformat(),
                        latest_version_id=str(latest) if latest else None,
                    )
                )
            return dict(
                items=items,
                next_cursor=self.cursors.encode_cursor(actor, rows[limit - 1])
                if len(rows) > limit
                else None,
            )

    def get(self, actor, identifier, vid):
        with UnitOfWork(self.engine) as u:
            row = owned(u.connection, actor, identifier, vid)
            history = (
                u.connection.execute(
                    select(document_reviews)
                    .where(document_reviews.c.document_version_id == vid)
                    .order_by(document_reviews.c.created_at, document_reviews.c.id)
                )
                .mappings()
                .all()
            )
            return dict(
                document_id=str(identifier),
                version_id=str(vid),
                sha256=row["sha256"],
                mime=row["mime"],
                metadata=row["metadata_json"],
                parse_status=row["parse_status"],
                review_status=row["review_status"],
                run_id=str(row["current_run_id"]),
                parser_version=row["parser_version"],
                chunker_version=row["chunker_version"],
                tokenizer=row["tokenizer"],
                page_count=row["page_count"],
                page_issues=row["page_issues"],
                parse_error=row["parse_error"],
                review_history=[
                    dict(
                        id=str(x["id"]),
                        actor=str(x["actor_id"]),
                        at=x["created_at"].isoformat(),
                        **x["review_json"],
                    )
                    for x in history
                ],
                **safety(row, u.connection, self.settings.retrieval_profile),
            )

    @staticmethod
    def context_rows(connection, actor, identifier, vid, chunk_id, neighbors):
        """Authorized same-version neighborhood for trusted WP07 tools; no new public route."""
        owned(connection, actor, identifier, vid)
        center = (
            connection.execute(
                select(chunks).where(chunks.c.id == chunk_id, chunks.c.document_version_id == vid)
            )
            .mappings()
            .one_or_none()
        )
        if center is None:
            raise DomainError("NOT_FOUND", "Chunk not in version", 404)
        return (
            connection.execute(
                select(chunks)
                .where(
                    chunks.c.document_version_id == vid,
                    chunks.c.ordinal.between(
                        center["ordinal"] - neighbors, center["ordinal"] + neighbors
                    ),
                )
                .order_by(chunks.c.ordinal)
            )
            .mappings()
            .all()
        )

    def read_chunks(self, actor, identifier, vid, limit, after):
        with UnitOfWork(self.engine) as u:
            owned(u.connection, actor, identifier, vid)
            rows = (
                u.connection.execute(
                    select(chunks)
                    .where(chunks.c.document_version_id == vid, chunks.c.ordinal > after)
                    .order_by(chunks.c.ordinal)
                    .limit(limit + 1)
                )
                .mappings()
                .all()
            )
            items = [
                {
                    k: v
                    for k, v in dict(row).items()
                    if k not in {"id", "document_version_id", "parent_id"}
                }
                for row in rows[:limit]
            ]
            return dict(
                items=items, next_cursor=rows[limit - 1]["ordinal"] if len(rows) > limit else None
            )

    def review(self, actor, identifier, vid, data, key):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            from app.services.evidence_scope import invalidate_source, owner_lock

            owner_lock(c, actor)
            owned(c, actor, identifier, vid)

            def action():
                row = owned(c, actor, identifier, vid, lock=True)
                if data.decision == "approved" and row["parse_status"] != "review_pending":
                    raise DomainError(
                        "REVIEW_NOT_ALLOWED", "Parsing must be complete without page gaps"
                    )
                fields = ("decision", "scope", "source_status", "license_status")
                changed = any(
                    row["review_snapshot"].get(k) != data.model_dump(mode="json")[k] for k in fields
                )
                if changed:
                    invalidate_source(c, vid)
                epoch = row["authorization_epoch"] + int(changed)
                c.execute(
                    document_reviews.insert().values(
                        document_version_id=vid,
                        actor_id=actor,
                        decision=data.decision,
                        review_json=data.model_dump(mode="json"),
                    )
                )
                row = (
                    c.execute(
                        update(versions)
                        .where(versions.c.id == vid)
                        .values(
                            authorization_epoch=epoch,
                            review_status=data.decision,
                            review_snapshot=data.model_dump(mode="json"),
                        )
                        .returning(versions)
                    )
                    .mappings()
                    .one()
                )
                scheduled = False
                if not exclusion(row, self.settings.retrieval_profile):
                    building = c.execute(
                        select(index_versions.c.id).where(
                            index_versions.c.document_version_id == vid,
                            index_versions.c.status == "building",
                        )
                    ).first()
                    if building is None:
                        schedule(c, actor, row, self.settings.retrieval_profile, self.settings)
                        scheduled = True
                return (202 if scheduled else 200), dict(
                    document_id=str(identifier),
                    version_id=str(vid),
                    review_status=data.decision,
                    **safety(row, c, self.settings.retrieval_profile),
                )

            return idempotent(
                c, actor, "review:" + str(vid), key, data.model_dump(mode="json"), action
            )

    def content(self, actor, identifier, vid, page):
        with UnitOfWork(self.engine) as u:
            row = owned(u.connection, actor, identifier, vid)
        if page is not None and (row["page_count"] is None or page > row["page_count"]):
            raise DomainError("INVALID_PAGE", "Page locator unavailable", 422)
        return self.storage.read(row["storage_key"], row["sha256"]), row["mime"], row["page_count"]
