from sqlalchemy import select

from app.config import Settings
from app.domain.documents import IngestError
from app.domain.policies import DomainError
from app.infrastructure.ingest_state import version_id
from app.infrastructure.orm import document_versions
from app.infrastructure.storage import Storage
from app.retrieval.chunker import chunks
from app.retrieval.parsers import markdown, pdf


def parse_ingest(engine, payload, stopped, settings=None):
    identifier = version_id(payload)
    with engine.connect() as conn:
        row = (
            conn.execute(select(document_versions).where(document_versions.c.id == identifier))
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise IngestError("INVALID_INGEST_INPUT")
    settings = settings or Settings()
    try:
        data = Storage(settings.data_path).read(row["storage_key"], row["sha256"])
    except DomainError:
        raise IngestError("SOURCE_UNAVAILABLE") from None
    if stopped.is_set():
        raise IngestError("PARSE_STOPPED")
    parser = (
        markdown
        if row["mime"] == "text/markdown"
        else pdf
        if row["mime"] == "application/pdf"
        else None
    )
    if parser is None:
        raise IngestError("UNSUPPORTED_FORMAT")
    parsed = parser.parse(data, stopped)
    return chunks(
        parsed,
        stopped,
        settings.chunk_target_tokens,
        settings.chunk_max_tokens,
        settings.chunk_overlap_tokens,
    )
