import hashlib
import time

from app.domain.policies import DomainError
from app.infrastructure.embedding_gateway import EmbeddingError
from app.infrastructure.model_factory import embedding_factory, supports_fingerprint
from app.infrastructure.orm import chunk_embeddings as embeddings
from app.infrastructure.orm import chunks, documents
from app.infrastructure.orm import document_versions as versions
from app.infrastructure.orm import index_versions as indexes
from app.retrieval.eligibility import applicability, exclusion
from app.retrieval.sparse import codes, rank
from sqlalchemy import select


class RetrievalService:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings

    def search(self, actor, body, *, mode="hybrid", manifest=None, narrow_scope=False):
        # mode is an internal evaluation argument, never an HTTP request parameter.
        if mode not in {"hybrid", "baseline"}:
            raise ValueError("Unknown evaluation mode")
        start = time.perf_counter()
        profile = self.settings.retrieval_profile
        excluded, allowed, shapes, snapshots = [], {}, {}, {}
        configurations = {}
        with self.engine.connect() as c:
            rows = (
                c.execute(
                    select(versions)
                    .join(documents, documents.c.id == versions.c.document_id)
                    .where(documents.c.owner_id == actor)
                )
                .mappings()
                .all()
            )
            frozen = (
                {x["document_version_id"]: x for x in manifest} if manifest is not None else None
            )
            if frozen is not None:
                rows = [x for x in rows if str(x["id"]) in frozen]
                if len(rows) != len(frozen):
                    raise DomainError("SOURCE_INVALID", "Frozen source no longer owned")
            pending = False
            for row in rows:
                vid = row["id"]
                entry = frozen.get(str(vid)) if frozen is not None else None
                if entry is not None and (
                    entry["authorization_epoch"] != row["authorization_epoch"]
                    or entry["profile"] != profile
                ):
                    raise DomainError("SOURCE_INVALID", "Frozen source authorization changed")
                reason = exclusion(row, profile)
                match = applicability(
                    row["review_snapshot"].get("scope", {}), body.vehicle_scope.model_dump()
                )
                if not reason and match["status"] == "mismatch":
                    reason = "scope_mismatch"
                if (
                    reason
                    and entry is not None
                    and not (narrow_scope and reason == "scope_mismatch")
                ):
                    raise DomainError("SOURCE_INVALID", "Frozen source is not eligible")
                if not reason:
                    idx = (
                        c.execute(
                            select(indexes).where(
                                indexes.c.id
                                == (
                                    entry["index_id"]
                                    if entry is not None
                                    else row["active_index_id"]
                                ),
                                indexes.c.document_version_id == vid,
                                indexes.c.status == "ready",
                                indexes.c.profile == profile,
                            )
                        )
                        .mappings()
                        .one_or_none()
                    )
                    if idx is None:
                        reason, pending = "index_unavailable", True
                    elif not supports_fingerprint(idx["config_json"]):
                        raise DomainError(
                            "INDEX_CONFIG_UNAVAILABLE",
                            "Active index requires unavailable model configuration",
                            503,
                        )
                    else:
                        allowed[vid] = idx["id"]
                        configurations[idx["id"]] = idx["config_json"]
                        shapes[vid] = match
                        snapshots[vid] = (
                            row["active_index_id"] if entry is None else None,
                            row["review_snapshot"],
                            row["authorization_epoch"],
                        )
                if reason:
                    excluded.append(dict(document_version_id=str(vid), reason=reason))
            if not allowed:
                if pending:
                    raise DomainError(
                        "INDEX_UNAVAILABLE", "Eligible documents have no ready index", 503
                    )
                return dict(
                    chunks=[],
                    excluded=excluded,
                    trace=dict(
                        mode=mode,
                        profile=profile,
                        candidate_count=0,
                        reason="no_eligible_candidates",
                        elapsed_ms=(time.perf_counter() - start) * 1000,
                    ),
                )
            source = (
                c.execute(
                    select(chunks)
                    .join(embeddings, embeddings.c.chunk_id == chunks.c.id)
                    .where(embeddings.c.index_id.in_(list(allowed.values())))
                    .order_by(chunks.c.id)
                )
                .mappings()
                .all()
            )
        sparse = rank(body.query, [x["text"] for x in source])
        dense = []
        if mode == "hybrid":
            try:
                # Partition by fingerprint before distance calculation: never compare mixed dimensions.
                groups = {}
                for iid, config in configurations.items():
                    key = config["config_version"]
                    groups.setdefault(key, (config, []))[1].append(iid)
                for config, ids in groups.values():
                    query_vector = embedding_factory(self.settings, config).embed_query(body.query)
                    with self.engine.connect() as c:
                        distance = embeddings.c.embedding.cosine_distance(query_vector)
                        dense.extend(
                            c.execute(
                                select(embeddings.c.chunk_id, distance.label("distance"))
                                .where(embeddings.c.index_id.in_(ids))
                                .order_by(distance, embeddings.c.chunk_id)
                                .limit(30)
                            ).all()
                        )
                dense = sorted(dense, key=lambda x: (float(x[1]), str(x[0])))[:30]
            except EmbeddingError:
                raise DomainError(
                    "EMBEDDING_UNAVAILABLE",
                    "Local embedding unavailable; no fallback performed",
                    503,
                ) from None
        scores = {}
        for position, (i, score, exact) in enumerate(sparse, 1):
            scores[source[i]["id"]] = dict(
                sparse_score=score, sparse_rank=position, rrf=1 / (60 + position), exact_dtc=exact
            )
        for position, (identifier, distance) in enumerate(dense, 1):
            row = scores.setdefault(identifier, dict(rrf=0, exact_dtc=False))
            row.update(dense_score=1 - float(distance), dense_rank=position)
            row["rrf"] += 1 / (60 + position)
        mapping = {x["id"]: x for x in source}
        selected = sorted(scores, key=lambda i: (-scores[i]["rrf"], str(i)))[:20]
        if mode == "hybrid":
            selected.sort(
                key=lambda i: (
                    shapes[mapping[i]["document_version_id"]]["status"] != "matched",
                    not bool(codes(body.query) & codes(mapping[i]["text"])),
                    -scores[i]["rrf"],
                    str(i),
                )
            )
        else:
            selected = [source[i]["id"] for i, _, _ in sparse][:20]
        # Re-read current qualification/active after inference, without holding a DB transaction during it.
        with self.engine.connect() as c:
            current = (
                c.execute(
                    select(versions)
                    .join(documents, documents.c.id == versions.c.document_id)
                    .where(versions.c.id.in_(list(allowed)), documents.c.owner_id == actor)
                )
                .mappings()
                .all()
            )
            if len(current) != len(allowed) or any(
                exclusion(x, profile)
                or (
                    x["active_index_id"] if manifest is None else None,
                    x["review_snapshot"],
                    x["authorization_epoch"],
                )
                != snapshots[x["id"]]
                for x in current
            ):
                raise DomainError(
                    "SEARCH_SNAPSHOT_CHANGED", "Index or review changed; repeat search"
                )
        output, token_count = [], 0
        for identifier in selected[: body.top_k]:
            row = mapping[identifier]
            if token_count + row["token_count"] > 8000:
                break
            token_count += row["token_count"]
            vid = row["document_version_id"]
            output.append(
                dict(
                    chunk_id=str(identifier),
                    document_version_id=str(vid),
                    index_id=str(allowed[vid]),
                    locator=row["locator_json"],
                    text=row["text"],
                    applicability=shapes[vid],
                    scores=scores[identifier],
                    channels=[x for x in ("sparse", "dense") if x + "_rank" in scores[identifier]],
                    synthetic=profile == "synthetic",
                    formal_usable=profile == "formal",
                )
            )
        return dict(
            chunks=output,
            excluded=excluded,
            trace=dict(
                mode=mode,
                profile=profile,
                query_sha256=hashlib.sha256(body.query.encode()).hexdigest(),
                model=list(groups[k][0] for k in sorted(groups)) if mode == "hybrid" else None,
                rrf_k=60,
                candidate_count=len(source),
                context_tokens=token_count,
                candidates={str(k): v for k, v in scores.items()},
                elapsed_ms=(time.perf_counter() - start) * 1000,
            ),
        )
