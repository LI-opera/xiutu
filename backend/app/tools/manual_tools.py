import hashlib
import json
from copy import deepcopy
from uuid import UUID

from sqlalchemy import select

from app.domain.measurements import CompareInput
from app.domain.policies import DomainError
from app.domain.retrieval import SearchInput, VehicleScope
from app.infrastructure.orm import (
    case_evidence,
    chunk_embeddings,
    chunks,
    idempotency_keys,
    measurement_specs,
)
from app.infrastructure.uow import UnitOfWork
from app.repositories.observations import ObservationRepository
from app.retrieval.eligibility import applicability
from app.retrieval.service import RetrievalService
from app.services.document_service import DocumentService
from app.services.evidence_scope import owner_lock, source
from app.services.evidence_service import EvidenceService, row_owned


def narrow(vehicle, requested):
    result = {k: v for k, v in vehicle.items() if k in VehicleScope.model_fields and v is not None}
    for k, v in requested.model_dump(exclude_none=True).items():
        old = result.get(k)
        if old is not None and (str(old).strip().casefold() != str(v).strip().casefold()):
            raise DomainError("SCOPE_CONFLICT", "Requested scope conflicts with case", 403)
        result[k] = v
    return result


def chunk_body(row, index_id, match):
    return dict(
        chunk_id=str(row["id"]),
        document_version_id=str(row["document_version_id"]),
        index_id=str(index_id),
        text=row["text"],
        content_hash=row["text_hash"],
        locator=row["locator_json"],
        applicability=match,
    )


class ManualTools:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings
        self.evidence = EvidenceService(engine, settings)

    def approved(self, c, ctx, sid):
        row = row_owned(c, ctx["actor_id"], measurement_specs, sid)
        ev = row_owned(c, ctx["actor_id"], case_evidence, row["evidence_id"])
        if ev["case_id"] != ctx["case_id"]:
            raise DomainError("NOT_FOUND", "Spec not in case", 404)
        valid = self.evidence.validity(c, ctx["actor_id"], ev)
        if row["needs_review"] or not valid["valid"]:
            raise DomainError("SOURCE_INVALID", "Spec source invalid")
        if row["review_status"] != "approved":
            raise DomainError("SPEC_NOT_APPROVED", "Reviewed spec required")
        if valid["applicability"]["status"] != "matched":
            raise DomainError("SCOPE_UNKNOWN", "Exact applicability required")
        return row, ev

    def execute(self, name, body, ctx, case, call_id, connection=None):
        actor = ctx["actor_id"]
        if name == "search_manuals":
            vehicle = narrow(case["vehicle_json"], body.vehicle_scope)
            found = RetrievalService(self.engine, self.settings).search(
                actor,
                SearchInput(query=body.query, vehicle_scope=vehicle, top_k=body.top_k),
                manifest=ctx["manifest"],
                narrow_scope=True,
            )
            with self.engine.connect() as c:
                result = []
                for x in found["chunks"]:
                    row = (
                        c.execute(select(chunks).where(chunks.c.id == UUID(x["chunk_id"])))
                        .mappings()
                        .one()
                    )
                    result.append(chunk_body(row, x["index_id"], x["applicability"]))
            return dict(empty=not result, chunks=result)
        with UnitOfWork(self.engine, connection=connection) as u:
            c = u.connection
            owner_lock(c, actor)
            if name == "get_evidence_context":
                entry = next(
                    (
                        x
                        for x in ctx["manifest"]
                        if x["document_version_id"] == str(body.document_version_id)
                    ),
                    None,
                )
                if entry is None:
                    raise DomainError("CORPUS_NOT_ALLOWED", "Version outside corpus", 403)
                version, match = source(
                    c,
                    actor,
                    case,
                    body.document_version_id,
                    UUID(entry["index_id"]),
                    ctx["profile"],
                )
                rows = DocumentService.context_rows(
                    c,
                    actor,
                    version["document_id"],
                    body.document_version_id,
                    body.chunk_id,
                    body.neighbors,
                )
                return dict(
                    empty=False, chunks=[chunk_body(x, entry["index_id"], match) for x in rows]
                )
            if name == "get_measurement_spec":
                vehicle = narrow(case["vehicle_json"], body.vehicle_scope)
                rows = (
                    c.execute(
                        select(measurement_specs)
                        .join(case_evidence, case_evidence.c.id == measurement_specs.c.evidence_id)
                        .where(
                            case_evidence.c.case_id == case["id"],
                            measurement_specs.c.review_status == "approved",
                            measurement_specs.c.definition["component_key"].astext
                            == body.component_key,
                            measurement_specs.c.definition["quantity"].astext == body.quantity,
                        )
                        .order_by(measurement_specs.c.id)
                    )
                    .mappings()
                    .all()
                )
                result = []
                for row in rows:
                    try:
                        row, ev = self.approved(c, ctx, row["id"])
                    except DomainError:
                        continue
                    if (
                        applicability(ev["review_snapshot"].get("scope", {}), vehicle)["status"]
                        != "matched"
                    ):
                        continue
                    result.append(
                        dict(
                            spec_id=str(row["id"]),
                            evidence_id=str(row["evidence_id"]),
                            version=row["version"],
                            definition=row["definition"],
                        )
                    )
                if len(result) > 20:
                    raise DomainError("RESULT_TOO_LARGE", "Too many matching specs", 422)
                return dict(empty=not result, candidates=result)
            if name == "compare_measurement":
                row, _ = self.approved(c, ctx, body.spec_id)
                data = CompareInput(
                    quantity=row["definition"]["quantity"], **body.model_dump(exclude={"spec_id"})
                )
                _, saved = self.evidence.compare(
                    actor, body.spec_id, data, "tool-" + str(call_id), connection=c
                )
                result = saved["result"]
                return dict(
                    comparison_id=saved["id"],
                    **{
                        k: result[k]
                        for k in [
                            "spec_id",
                            "spec_version",
                            "outcome",
                            "input",
                            "converted",
                            "converted_exact",
                            "synthetic",
                            "diagnosis",
                        ]
                    },
                )
            if name == "get_case_observations":
                if body.at_revision > ctx["revision"]:
                    raise DomainError("REVISION_INVALID", "Revision exceeds context", 422)
                rows = ObservationRepository(c).read(case["id"], body.area_id, body.at_revision)
                return dict(
                    empty=not rows,
                    observations=[
                        {
                            k: x[k]
                            for k in [
                                "id",
                                "area_id",
                                "step_id",
                                "kind",
                                "payload",
                                "created_revision",
                                "supersedes_id",
                            ]
                        }
                        for x in rows
                    ],
                )
        raise DomainError("TOOL_UNKNOWN", "Tool not registered", 404)

    def summarize(self, name, answer):
        """Receipt v2: only schema-owned positions are references, never dynamic keys."""
        saved = deepcopy(answer)
        data = saved["data"]
        if name in ("search_manuals", "get_evidence_context"):
            for chunk in data["chunks"]:
                del chunk["text"]
        elif name == "get_case_observations":
            for observation in data["observations"]:
                del observation["payload"]
        return dict(receipt_version=2, tool=name, answer=saved)

    def hydrate(self, c, ctx, case, name, body, call):
        receipt = call["result_summary"]
        if (
            not isinstance(receipt, dict)
            or type(receipt.get("receipt_version")) is not int
            or receipt.get("receipt_version") != 2
            or receipt.get("tool") != name
            or set(receipt) != {"receipt_version", "tool", "answer"}
        ):
            raise DomainError("RECEIPT_UNSUPPORTED", "Receipt cannot be safely replayed")
        answer = deepcopy(receipt["answer"])
        data = answer["data"]
        if name in ("search_manuals", "get_evidence_context"):
            for item in data["chunks"]:
                vid, iid = UUID(item["document_version_id"]), UUID(item["index_id"])
                # Frozen index, owner, epoch and CURRENT qualification, not UUID/hash authority.
                version, _ = source(c, ctx["actor_id"], case, vid, iid, ctx["profile"])
                if name == "get_evidence_context":
                    if vid != body.document_version_id:
                        raise DomainError("SOURCE_INVALID", "Context version changed")
                    allowed = DocumentService.context_rows(
                        c,
                        ctx["actor_id"],
                        version["document_id"],
                        vid,
                        body.chunk_id,
                        body.neighbors,
                    )
                    if not any(str(x["id"]) == item["chunk_id"] for x in allowed):
                        raise DomainError("SOURCE_INVALID", "Context neighborhood changed")
                elif (
                    applicability(
                        version["review_snapshot"].get("scope", {}),
                        narrow(case["vehicle_json"], body.vehicle_scope),
                    )["status"]
                    == "mismatch"
                ):
                    raise DomainError("SOURCE_INVALID", "Replay scope changed")
                row = (
                    c.execute(
                        select(chunks)
                        .join(chunk_embeddings, chunk_embeddings.c.chunk_id == chunks.c.id)
                        .where(
                            chunks.c.id == UUID(item["chunk_id"]),
                            chunks.c.document_version_id == vid,
                            chunk_embeddings.c.index_id == iid,
                            chunk_embeddings.c.text_hash == item["content_hash"],
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if (
                    row is None
                    or row["text_hash"] != item["content_hash"]
                    or row["locator_json"] != item["locator"]
                ):
                    raise DomainError("SOURCE_INVALID", "Replay chunk changed")
                item["text"] = row["text"]
        elif name == "get_case_observations":
            if body.at_revision > ctx["revision"]:
                raise DomainError("REVISION_INVALID", "Revision exceeds context", 422)
            allowed = {
                str(x["id"]): x
                for x in ObservationRepository(c).read(
                    ctx["case_id"], body.area_id, body.at_revision
                )
            }
            for item in data["observations"]:
                row = allowed.get(item["id"])
                if row is None:
                    raise DomainError("SOURCE_INVALID", "Observation outside requested history")
                for key in ("area_id", "step_id", "supersedes_id", "kind", "created_revision"):
                    value = str(row[key]) if isinstance(row[key], UUID) else row[key]
                    if value != item[key]:
                        raise DomainError("SOURCE_INVALID", "Observation reference changed")
                item["payload"] = deepcopy(row["payload"])
        elif name == "compare_measurement":
            view = self.evidence.get_comparison(
                ctx["actor_id"], UUID(data["comparison_id"]), connection=c
            )
            comparison = view["comparison"]
            if comparison["case_id"] != str(ctx["case_id"]) or comparison["spec_id"] != str(
                body.spec_id
            ):
                raise DomainError("SOURCE_INVALID", "Comparison relationship changed")
            if not view["current_validity"]["valid"]:
                raise DomainError("COMPARISON_INVALID", "Historical comparison requires review")
            spec, _ = self.approved(c, ctx, body.spec_id)
            request = CompareInput(
                quantity=spec["definition"]["quantity"], **body.model_dump(exclude={"spec_id"})
            )
            digest = hashlib.sha256(
                json.dumps(
                    request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            idem = (
                c.execute(
                    select(idempotency_keys).where(
                        idempotency_keys.c.actor_id == ctx["actor_id"],
                        idempotency_keys.c.route_scope == "compare:" + str(body.spec_id),
                        idempotency_keys.c.key == "tool-" + str(call["id"]),
                    )
                )
                .mappings()
                .one_or_none()
            )
            if (
                idem is None
                or idem["request_hash"] != digest
                or idem["response_status"] != 201
                or idem["response_json"].get("id") != comparison["id"]
                or {k: comparison["result"].get(k) for k in data if k != "comparison_id"}
                != {k: v for k, v in data.items() if k != "comparison_id"}
            ):
                raise DomainError("SOURCE_INVALID", "Comparison receipt does not match call")
        return answer
