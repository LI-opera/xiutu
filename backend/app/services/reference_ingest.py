"""Manual ingest: upload Markdown -> sections -> identifiers -> vectors, for one vehicle.

One version of a document is one row of area_reference_documents. Uploading creates the row
as "queued" with the vehicle it applies to and schedules a worker job; the job splits the body
exactly as section retrieval does (### chunks under ## sections), stores the chunks with their
identifiers, embeds each chunk with the configured local model, and marks the version "ready".
Analyses then find manuals by the case's vehicle and choose among them by content (two-step
retrieval); nothing ties a manual to a template or an area. The seed script uses the same
processing.
"""
import hashlib
import os
import re
from datetime import datetime, timezone

from sqlalchemy import func, select, update

from app.domain.documents import IngestError
from app.domain.policies import DomainError
from app.infrastructure.orm import area_reference_chunk_vectors as vectors
from app.infrastructure.orm import area_reference_chunks as chunks
from app.infrastructure.orm import area_reference_documents as documents
from app.infrastructure.orm import workbench_template_matches
from app.infrastructure.uow import UnitOfWork
from app.retrieval.section_search import split
from app.services.retrieval_reading import NAVIGATION, section_ranges

CHUNKER_VERSION = "markdown-sections-v1"
JOB_KIND = "reference_ingest"
DOCUMENT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,99}$")
MAX_CHARS = 2_000_000
EMBED_BATCH = 16


# ---------------------------------------------------------------- pure parts

def normalize(content):
    """Uploaded text in the same form the seed script reads files: no BOM, LF line ends."""
    return content.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")


def content_hash(body):
    return hashlib.sha256(body.encode()).hexdigest()


def build_chunks(document_id, body):
    """Every ### chunk with its place in the document; navigation sections are kept, unsearchable.

    The searchable chunks are exactly what section retrieval searches: split() with the
    navigation patterns skipped yields the same list in the same order.
    """
    result = []
    for ordinal, chunk in enumerate(split(document_id, body)):
        result.append({
            "ordinal": ordinal, "section": chunk.section, "subsection": chunk.subsection,
            "text": chunk.text, "char_start": chunk.start, "char_end": chunk.end,
            "identifiers": sorted(chunk.identifiers),
            "searchable": not any(re.search(p, chunk.section) for p in NAVIGATION),
            "search_text": chunk.search_text,
            "search_hash": content_hash(chunk.search_text),
        })
    return result


def headings(body):
    """The document's ## headings, the unit an always-included section is chosen by."""
    return list(section_ranges(body))


def validate_content(body, always_include):
    if not body.strip():
        raise DomainError("REFERENCE_EMPTY", "资料内容为空。", 422)
    if len(body) > MAX_CHARS:
        raise DomainError("REFERENCE_TOO_LARGE", f"资料超过 {MAX_CHARS} 字。", 422)
    built = build_chunks("validation", body)
    if not any(c["searchable"] for c in built):
        raise DomainError("REFERENCE_NO_SECTIONS",
                          "没有找到可检索的章节：资料需要用 \"## 标题\" 分章节，章节下要有正文。", 422)
    missing = [h for h in always_include if h not in set(headings(body))]
    if missing:
        raise DomainError("REFERENCE_SECTION_NOT_FOUND", "必带章节在资料里找不到：" + "、".join(missing),
                          422, details={"missing": missing})


def next_version(existing):
    numbers = [int(v) for v in existing if v.isdigit()]
    return str(max(numbers, default=0) + 1)


# ---------------------------------------------------------------- embedding

def load_embedder():
    """The local model the API would use, with its fingerprint; raises if unavailable."""
    from app.config import load_settings
    from app.infrastructure.model_factory import embedding_factory, selected_config
    settings = load_settings(project_env=os.environ.get("XIUTU_LOAD_PROJECT_ENV") == "1")
    config = selected_config(settings)
    return embedding_factory(settings, config), config["config_version"]


def embed(built, embedder, stopped=None):
    model, _ = embedder
    searchable = [c for c in built if c["searchable"]]
    result = {}
    for start in range(0, len(searchable), EMBED_BATCH):
        if stopped is not None and stopped.is_set():
            raise IngestError("REFERENCE_INGEST_STOPPED")
        batch = searchable[start:start + EMBED_BATCH]
        for chunk, vector in zip(batch, model.embed_documents([c["search_text"] for c in batch]),
                                 strict=True):
            values = [float(x) for x in vector]
            if not any(values):
                raise IngestError("REFERENCE_VECTOR_EMPTY")
            result[chunk["ordinal"]] = values
    return result


# ---------------------------------------------------------------- processing

def _row(conn, document_id, version, lock=False):
    query = select(documents).where(documents.c.document_id == document_id,
                                    documents.c.version == version)
    return conn.execute(query.with_for_update() if lock else query).mappings().one_or_none()


def _set_status(engine, document_id, version, status, error_code=None):
    with engine.begin() as conn:
        conn.execute(update(documents).where(documents.c.document_id == document_id,
                                             documents.c.version == version)
                     .values(status=status, error_code=error_code, updated_at=func.now()))


def store(conn, document_id, version, built, vectors_by_ordinal, fingerprint):
    """Replace this version's chunks and vectors (a retry rewrites them whole)."""
    conn.execute(vectors.delete().where(vectors.c.document_id == document_id,
                                        vectors.c.version == version))
    conn.execute(chunks.delete().where(chunks.c.document_id == document_id,
                                       chunks.c.version == version))
    if built:
        conn.execute(chunks.insert(), [
            {"document_id": document_id, "version": version, **{k: c[k] for k in (
                "ordinal", "section", "subsection", "text", "char_start", "char_end",
                "identifiers", "searchable", "search_hash")}} for c in built])
    by_ordinal = {c["ordinal"]: c for c in built}
    if vectors_by_ordinal:
        conn.execute(vectors.insert(), [
            {"document_id": document_id, "version": version, "ordinal": ordinal,
             "fingerprint": fingerprint, "search_hash": by_ordinal[ordinal]["search_hash"],
             "embedding": vector} for ordinal, vector in vectors_by_ordinal.items()])


def process(engine, document_id, version, embedder, stopped=None):
    """Chunk, embed and publish one version; marks it failed (and re-raises) on any error.

    embedder is (model, fingerprint), or None to store chunks without vectors (seed script on
    a machine without the model). The model runs outside any database transaction.
    """
    with engine.begin() as conn:
        row = _row(conn, document_id, version, lock=True)
        if row is None:
            raise IngestError("REFERENCE_NOT_FOUND")
        conn.execute(update(documents).where(documents.c.document_id == document_id,
                                             documents.c.version == version)
                     .values(status="processing", error_code=None, updated_at=func.now()))
    try:
        built = build_chunks(document_id, row["body"])
        if not any(c["searchable"] for c in built):
            raise IngestError("REFERENCE_NO_SECTIONS")
        embedded = embed(built, embedder, stopped) if embedder is not None else {}
        fingerprint = embedder[1] if embedder is not None else None
        with engine.begin() as conn:
            current = _row(conn, document_id, version, lock=True)
            if current is None or current["content_hash"] != row["content_hash"]:
                raise IngestError("REFERENCE_CHANGED")
            store(conn, document_id, version, built, embedded, fingerprint)
            conn.execute(update(documents).where(documents.c.document_id == document_id,
                                                 documents.c.version == version)
                         .values(status="ready", error_code=None, chunker_version=CHUNKER_VERSION,
                                 chunk_count=len(built), vector_fingerprint=fingerprint,
                                 updated_at=func.now()))
    except Exception as exc:
        code = getattr(exc, "code", None) or type(exc).__name__
        _set_status(engine, document_id, version, "failed", str(code)[:80])
        raise
    return {"document_id": document_id, "version": version, "chunks": len(built),
            "vectors": len(embedded), "fingerprint": fingerprint}


def run_job(engine, payload, stopped):
    """Worker entry for a reference_ingest job."""
    try:
        embedder = load_embedder()
    except Exception as exc:
        code = getattr(exc, "code", None) or "EMBEDDING_UNAVAILABLE"
        _set_status(engine, payload["document_id"], payload["version"], "failed", str(code)[:80])
        raise IngestError(str(code)) from None
    return process(engine, payload["document_id"], payload["version"], embedder, stopped)


# ---------------------------------------------------------------- service (API)

VEHICLE_FIELDS = ("brand", "model", "year", "engine_code")


def vehicle_of(row):
    """The vehicle a stored version applies to, as the API shows it (None for unknown parts)."""
    return {"brand": row["vehicle_brand"], "model": row["vehicle_model"], "year": row["vehicle_year"],
            "engine_code": row["vehicle_engine_code"]}


def normalize_vehicle(vehicle):
    brand, model, engine = (vehicle[k].strip() for k in ("brand", "model", "engine_code"))
    if not (brand and model and engine):
        raise DomainError("REFERENCE_VEHICLE_REQUIRED", "请填写适用车型：品牌、车型、年款和发动机代码。", 422)
    return {"vehicle_brand": brand, "vehicle_model": model, "vehicle_year": int(vehicle["year"]),
            "vehicle_engine_code": engine.upper()}


def _summary(row):
    return {"document_id": row["document_id"], "version": row["version"], "title": row["title"],
            "status": row["status"], "error_code": row["error_code"], "source_kind": row["source_kind"],
            "content_hash": row["content_hash"], "chars": len(row["body"]),
            "chunk_count": row["chunk_count"], "chunker_version": row["chunker_version"],
            "vector_fingerprint": row["vector_fingerprint"], "always_include": row["always_include"],
            "vehicle": vehicle_of(row),
            "created_at": row["created_at"].isoformat(), "updated_at": row["updated_at"].isoformat()}


class ReferenceIngestService:
    def __init__(self, engine):
        self.engine = engine

    def _queue(self, conn, actor, document_id, values, body):
        """Insert one queued version (numbered after the existing ones) and schedule its job."""
        from app.services.run_service import enqueue
        existing = conn.execute(select(documents.c.version).where(
            documents.c.document_id == document_id)).scalars().all()
        version = next_version(existing)
        conn.execute(documents.insert().values(
            document_id=document_id, version=version, body=body, content_hash=content_hash(body),
            source_kind="upload", status="queued", **values))
        _, run = enqueue(conn, actor, JOB_KIND, {"document_id": document_id, "version": version})
        return 202, {"document_id": document_id, "version": version, "status": "queued",
                     "reused": False, "run_id": run["run_id"]}

    def _reuse(self, conn, actor, row):
        """Same content again: return that version; a failed one is queued again (retry)."""
        from app.services.run_service import enqueue
        run = None
        if row["status"] == "failed":
            conn.execute(update(documents).where(documents.c.document_id == row["document_id"],
                                                 documents.c.version == row["version"])
                         .values(status="queued", error_code=None, updated_at=func.now()))
            _, run = enqueue(conn, actor, JOB_KIND, {"document_id": row["document_id"], "version": row["version"]})
        return 200, {"document_id": row["document_id"], "version": row["version"],
                     "status": "queued" if run else row["status"], "reused": True,
                     "run_id": run["run_id"] if run else None}

    @staticmethod
    def _lock(conn, document_id):
        # One upload of a document at a time: versions are numbered in order.
        conn.execute(select(func.pg_advisory_xact_lock(func.hashtext(document_id))))

    def upload(self, actor, data):
        """A new manual. An existing document number must be updated through add_version."""
        body = normalize(data.content)
        validate_content(body, data.always_include)
        if not DOCUMENT_ID.fullmatch(data.document_id):
            raise DomainError("REFERENCE_ID_INVALID", "资料编号只能用小写字母、数字和连字符，2～100 个字符。", 422)
        vehicle = normalize_vehicle(data.vehicle.model_dump())
        with UnitOfWork(self.engine) as u:
            conn = u.connection
            self._lock(conn, data.document_id)
            existing = conn.execute(select(documents).where(
                documents.c.document_id == data.document_id)).mappings().all()
            same = next((r for r in existing if r["content_hash"] == content_hash(body)), None)
            if same is not None:
                return self._reuse(conn, actor, same)
            if existing:
                raise DomainError("REFERENCE_EXISTS", "已有同编号的资料。要更新它，请在资料列表里点“上传新版本”。", 409)
            return self._queue(conn, actor, data.document_id, {
                "title": data.title.strip(), "always_include": data.always_include, **vehicle,
                "provenance": {"upload": {"filename": data.filename, "uploaded_by": str(actor),
                                          "uploaded_at": datetime.now(timezone.utc).isoformat()},
                               "images_sent": False}}, body)

    def add_version(self, actor, document_id, data):
        """A new version of an existing manual: title and vehicle carry over from the latest one."""
        body = normalize(data.content)
        with UnitOfWork(self.engine) as u:
            conn = u.connection
            self._lock(conn, document_id)
            existing = conn.execute(select(documents).where(documents.c.document_id == document_id)
                                    .order_by(documents.c.created_at)).mappings().all()
            if not existing:
                raise DomainError("REFERENCE_NOT_FOUND", "找不到这份资料。", 404)
            latest = max(existing, key=lambda r: (int(r["version"]) if r["version"].isdigit() else -1,
                                                  r["created_at"]))
            # Always-sent sections carry over where the new body still has them.
            always = [h for h in latest["always_include"] if h in set(headings(body))]
            validate_content(body, always)
            same = next((r for r in existing if r["content_hash"] == content_hash(body)), None)
            if same is not None:
                return self._reuse(conn, actor, same)
            return self._queue(conn, actor, document_id, {
                "title": latest["title"], "always_include": always,
                **{k: latest[k] for k in ("vehicle_brand", "vehicle_model", "vehicle_year", "vehicle_engine_code")},
                "provenance": {"upload": {"filename": data.filename, "uploaded_by": str(actor),
                                          "uploaded_at": datetime.now(timezone.utc).isoformat(),
                                          "previous_version": latest["version"]},
                               "images_sent": False}}, body)

    def list(self):
        with self.engine.connect() as conn:
            rows = conn.execute(select(documents).order_by(
                documents.c.document_id, documents.c.created_at)).mappings().all()
        return {"items": [_summary(r) for r in rows]}

    def vehicles(self):
        """Vehicles already known (templates and manuals), to suggest while typing."""
        with self.engine.connect() as conn:
            known = {(r.brand, r.model, r.year_from, r.engine_code) for r in conn.execute(select(
                workbench_template_matches.c.brand, workbench_template_matches.c.model,
                workbench_template_matches.c.year_from, workbench_template_matches.c.engine_code))}
            known |= {tuple(r) for r in conn.execute(select(
                documents.c.vehicle_brand, documents.c.vehicle_model, documents.c.vehicle_year,
                documents.c.vehicle_engine_code).where(documents.c.vehicle_brand.is_not(None)))}
        return {"vehicles": [dict(zip(VEHICLE_FIELDS, v)) for v in sorted(known, key=lambda v: tuple(map(str, v)))]}

    def chunks(self, document_id, version):
        with self.engine.connect() as conn:
            row = _row(conn, document_id, version)
            if row is None:
                raise DomainError("REFERENCE_NOT_FOUND", "找不到这份资料。", 404)
            items = conn.execute(select(chunks).where(chunks.c.document_id == document_id,
                                                      chunks.c.version == version)
                                 .order_by(chunks.c.ordinal)).mappings().all()
            with_vector = set(conn.execute(select(vectors.c.ordinal).where(
                vectors.c.document_id == document_id, vectors.c.version == version,
                vectors.c.fingerprint == row["vector_fingerprint"])).scalars()) \
                if row["vector_fingerprint"] else set()
        return {"document_id": document_id, "version": version, "status": row["status"],
                "vector_fingerprint": row["vector_fingerprint"],
                "items": [{"ordinal": c["ordinal"], "section": c["section"], "subsection": c["subsection"],
                           "text": c["text"], "char_start": c["char_start"], "char_end": c["char_end"],
                           "identifiers": c["identifiers"], "searchable": c["searchable"],
                           "has_vector": c["ordinal"] in with_vector} for c in items]}
