"""Small ingest publication hooks; called inside the queue's fenced transaction."""

from uuid import UUID

from sqlalchemy import select, update

from app.domain.documents import IngestError
from app.infrastructure.orm import chunks
from app.infrastructure.orm import document_versions as versions


def version_id(payload):
    try:
        if set(payload) != {"version_id"}:
            raise ValueError()
        return UUID(payload["version_id"])
    except (ValueError, TypeError, KeyError):
        raise IngestError("INVALID_INGEST_INPUT") from None


def state(conn, run_id, status, error=None):
    conn.execute(
        update(versions)
        .where(versions.c.current_run_id == run_id)
        .values(parse_status=status, parse_error=error or {})
    )


def publish(conn, job, result, *, validate_lease):
    identifier = version_id(job["payload"])
    row = (
        conn.execute(
            select(versions)
            .where(versions.c.id == identifier, versions.c.current_run_id == job["run_id"])
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    # This row lock can wait past the lease deadline; revalidate before writing.
    validate_lease()
    if row is None or result is None:
        raise IngestError("INVALID_INGEST_PUBLICATION")
    if conn.execute(
        select(chunks.c.id).where(chunks.c.document_version_id == identifier).limit(1)
    ).first():
        raise IngestError("INGEST_ALREADY_PUBLISHED")
    if result["chunks"]:
        conn.execute(
            chunks.insert(),
            [dict(document_version_id=identifier, **item) for item in result["chunks"]],
        )
    values = {
        k: result[k]
        for k in ["parser_version", "chunker_version", "tokenizer", "page_count", "page_issues"]
    }
    conn.execute(
        update(versions)
        .where(versions.c.id == identifier)
        .values(
            **values,
            parse_status="needs_ocr" if result["page_issues"] else "review_pending",
            parse_error={},
        )
    )
