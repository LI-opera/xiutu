import os
from uuid import UUID

from sqlalchemy import select

from app.config import load_settings
from app.domain.documents import IngestError
from app.infrastructure.model_factory import embedding_factory
from app.infrastructure.orm import chunks, index_versions


def build_index(store, lease, stopped, hook=None):
    settings = load_settings(project_env=os.environ.get("XIUTU_LOAD_PROJECT_ENV") == "1")
    vid = UUID(lease.job["payload"]["version_id"])
    with store.engine.connect() as c:
        config = c.execute(
            select(index_versions.c.config_json).where(
                index_versions.c.id == UUID(lease.job["payload"]["index_id"])
            )
        ).scalar_one()
        model = embedding_factory(settings, config)
        source = (
            c.execute(
                select(chunks).where(chunks.c.document_version_id == vid).order_by(chunks.c.ordinal)
            )
            .mappings()
            .all()
        )
    store.stage_index(lease, None)
    for start in range(0, len(source), 8):
        if stopped.is_set():
            raise IngestError("INDEX_INTERRUPTED")
        batch = source[start : start + 8]
        vectors = model.embed_documents([x["text"] for x in batch])
        if stopped.is_set():
            raise IngestError("INDEX_INTERRUPTED")
        store.stage_index(
            lease,
            [
                dict(chunk_id=x["id"], text_hash=x["text_hash"], embedding=v)
                for x, v in zip(batch, vectors, strict=True)
            ],
        )
        if hook:
            hook("after_index_batch", lease.job)
    return {"index_id": lease.job["payload"]["index_id"]}
