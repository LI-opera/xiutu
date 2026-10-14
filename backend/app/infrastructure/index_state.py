"""Staged index batches are invisible until a fenced activation transaction."""

from uuid import UUID

from sqlalchemy import delete, select, update

from app.domain.documents import IngestError
from app.infrastructure.embedding_gateway import validate_vectors
from app.infrastructure.model_factory import check_fingerprint
from app.infrastructure.orm import chunk_embeddings as embeddings
from app.infrastructure.orm import chunks
from app.infrastructure.orm import document_versions as versions
from app.infrastructure.orm import index_versions as indexes
from app.retrieval.eligibility import exclusion


def state(c, run_id, error):
    c.execute(
        update(indexes)
        .where(indexes.c.run_id == run_id, indexes.c.status == "building")
        .values(status="failed", error_json=error)
    )


def locked(c, job):
    row = (
        c.execute(
            select(indexes)
            .where(indexes.c.id == UUID(job["payload"]["index_id"]))
            .with_for_update()
        )
        .mappings()
        .one()
    )
    if (
        row["run_id"] != job["run_id"]
        or row["status"] != "building"
        or row["config_json"] != check_fingerprint(row["config_json"])
    ):
        raise IngestError("INDEX_SUPERSEDED")
    return row


def stage(c, job, batch):
    row = locked(c, job)
    if batch is None:
        c.execute(delete(embeddings).where(embeddings.c.index_id == row["id"]))
        return
    vectors = validate_vectors([x["embedding"] for x in batch], len(batch), row["dimension"])
    for item, vector in zip(batch, vectors, strict=True):
        source = c.execute(
            select(chunks.c.text_hash).where(
                chunks.c.id == item["chunk_id"],
                chunks.c.document_version_id == row["document_version_id"],
            )
        ).scalar_one_or_none()
        if source != item["text_hash"]:
            raise IngestError("INDEX_SOURCE_CHANGED")
        c.execute(
            embeddings.insert().values(
                index_id=row["id"], chunk_id=item["chunk_id"], text_hash=source, embedding=vector
            )
        )


def publish(c, job, validate_lease):
    vid = UUID(job["payload"]["version_id"])
    version = (
        c.execute(select(versions).where(versions.c.id == vid).with_for_update()).mappings().one()
    )
    validate_lease()
    row = locked(c, job)
    if row["document_version_id"] != vid or exclusion(version, row["profile"]):
        raise IngestError("INDEX_NOT_ELIGIBLE")
    expected = dict(
        c.execute(
            select(chunks.c.id, chunks.c.text_hash).where(chunks.c.document_version_id == vid)
        ).all()
    )
    actual = (
        c.execute(select(embeddings).where(embeddings.c.index_id == row["id"])).mappings().all()
    )
    if (
        row["dimension"] != row["config_json"]["dimension"]
        or len(expected) != row["chunk_count"]
        or len(actual) != len(expected)
    ):
        raise IngestError("INDEX_INCOMPLETE")
    if {x["chunk_id"]: x["text_hash"] for x in actual} != expected:
        raise IngestError("INDEX_SOURCE_CHANGED")
    validate_vectors([x["embedding"] for x in actual], len(actual), row["dimension"])
    c.execute(
        update(indexes).where(indexes.c.id == row["id"]).values(status="ready", error_json={})
    )
    c.execute(update(versions).where(versions.c.id == vid).values(active_index_id=row["id"]))
