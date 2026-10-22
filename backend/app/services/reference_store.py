"""Section search over chunks and vectors stored at ingest (area_reference_chunks / _vectors).

Gives the same chunks, in the same order, as splitting the body now (reference_ingest stores
exactly what section retrieval splits), so the chosen sections are the same; only where the
work happens changes:
  - exact codes: array overlap in PostgreSQL (GIN index on identifiers);
  - BM25: in the program, over the stored chunk texts (PostgreSQL has no BM25, and Chinese
    tokenizing would need an extension; a few hundred chunks take milliseconds);
  - vectors: cosine distance in PostgreSQL (pgvector), against vectors of the same model.
A document without usable stored data (not processed, other chunker or model, body changed)
falls back to computing, so an analysis never fails for that reason.
"""
from sqlalchemy import bindparam, func, select, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.types import Text

from app.infrastructure.orm import area_reference_chunk_vectors as vectors
from app.infrastructure.orm import area_reference_chunks as chunks
from app.infrastructure.orm import area_reference_documents as documents
from app.retrieval.section_search import BM25, Chunk, identifiers
from app.services.reference_ingest import CHUNKER_VERSION, content_hash

EXACT = text("""
    SELECT ordinal,
           cardinality(ARRAY(SELECT unnest(identifiers) INTERSECT SELECT unnest(:wanted))) AS shared
    FROM area_reference_chunks
    WHERE document_id = :document_id AND version = :version AND searchable AND identifiers && :wanted
""").bindparams(bindparam("wanted", type_=ARRAY(Text)))


class StoredSections:
    source = "stored"

    def __init__(self, conn, key, rows, embeddings, fingerprint):
        self.conn, self.key = conn, key
        self.embeddings, self.fingerprint = embeddings, fingerprint
        self.ordinals = [r["ordinal"] for r in rows]
        self.position = {ordinal: i for i, ordinal in enumerate(self.ordinals)}
        self.chunks = [Chunk(key[0], r["section"], r["subsection"], r["text"], r["char_start"],
                             r["char_end"], set(r["identifiers"])) for r in rows]
        self.index = BM25([c.search_text for c in self.chunks])

    def exact(self, query):
        wanted = sorted(identifiers(query))
        if not wanted:
            return []
        rows = self.conn.execute(EXACT, {"document_id": self.key[0], "version": self.key[1],
                                         "wanted": wanted}).all()
        return [self.position[o] for o, shared in sorted(rows, key=lambda r: (-r[1], self.position[r[0]]))]

    def keywords(self, query):
        return self.index.rank(query)

    def dense(self, query):
        if self.embeddings is None:
            return None
        distance = vectors.c.embedding.cosine_distance(self.embeddings.query(query))
        rows = self.conn.execute(select(vectors.c.ordinal).where(
            vectors.c.document_id == self.key[0], vectors.c.version == self.key[1],
            vectors.c.fingerprint == self.fingerprint,
            vectors.c.ordinal.in_(self.ordinals)).order_by(distance, vectors.c.ordinal)).scalars()
        return [self.position[o] for o in rows]


def load(conn, document, embeddings):
    """(stored source or None, always-included sections or None) for one document.

    None as source means: compute now. None as sections means: use the reviewed config.
    """
    row = conn.execute(select(documents.c.status, documents.c.chunker_version,
                              documents.c.content_hash, documents.c.always_include).where(
        documents.c.document_id == document["id"],
        documents.c.version == document.get("version"))).mappings().one_or_none()
    if row is None or row["content_hash"] != document.get("content_hash"):
        return None, None
    always = list(row["always_include"]) or None
    if row["status"] != "ready" or row["chunker_version"] != CHUNKER_VERSION:
        return None, always
    rows = conn.execute(select(chunks).where(
        chunks.c.document_id == document["id"], chunks.c.version == document["version"],
        chunks.c.searchable).order_by(chunks.c.ordinal)).mappings().all()
    if not rows:
        return None, always
    fingerprint = getattr(embeddings, "fingerprint", None) if embeddings is not None else None
    if embeddings is not None:
        stored = conn.execute(select(func.count()).select_from(vectors).where(
            vectors.c.document_id == document["id"], vectors.c.version == document["version"],
            vectors.c.fingerprint == fingerprint,
            vectors.c.ordinal.in_([r["ordinal"] for r in rows]))).scalar_one()
        if stored != len(rows):
            return None, always  # no vectors for this model yet: compute now
    source = StoredSections(conn, (document["id"], document["version"]), rows, embeddings, fingerprint)
    # The stored text must still be exactly what was indexed.
    if any(content_hash(c.search_text) != r["search_hash"] for c, r in zip(source.chunks, rows)):
        return None, always
    return source, always


def provider(conn, embeddings):
    """For enrich(): look up stored search data per document inside the caller's transaction."""
    return lambda document: load(conn, document, embeddings)
