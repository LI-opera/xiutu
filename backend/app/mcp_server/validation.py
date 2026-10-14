"""Revalidate readonly output against authorized immutable sources, on both sides."""

import json
from uuid import UUID

from pydantic import ValidationError

from app.domain.policies import DomainError
from app.retrieval.eligibility import applicability
from app.services.evidence_scope import source
from app.tools.manual_tools import narrow
from app.tools.schemas import OUTPUTS, Envelope


def checked(name, data):
    try:
        out = OUTPUTS[name].model_validate(data).model_dump(mode="json")
    except (ValidationError, TypeError):
        raise DomainError("OUTPUT_INVALID", "Invalid MCP output", 502) from None
    if len(json.dumps(out, ensure_ascii=False).encode()) > 65536:
        raise DomainError("RESULT_TOO_LARGE", "MCP result too large", 422)
    return out


def validate_result(tools, c, ctx, case, name, body, data):
    data = checked(name, data)
    if name in ("search_manuals", "get_evidence_context"):
        ids = [x["chunk_id"] for x in data["chunks"]]
        if len(ids) != len(set(ids)) or (name == "search_manuals" and len(ids) > body.top_k):
            raise DomainError("OUTPUT_INVALID", "Duplicate or excessive chunks")
        for item in data["chunks"]:
            version, match = source(
                c,
                ctx["actor_id"],
                case,
                UUID(item["document_version_id"]),
                UUID(item["index_id"]),
                ctx["profile"],
            )
            if name == "search_manuals":
                match = applicability(
                    version["review_snapshot"].get("scope", {}),
                    narrow(case["vehicle_json"], body.vehicle_scope),
                )
            if item["applicability"] != match:
                raise DomainError("SOURCE_INVALID", "Remote applicability differs")
        envelope = Envelope(ok=True, data=data, error=None, duration_ms=0).model_dump(mode="json")
        restored = tools.hydrate(
            c, ctx, case, name, body, dict(result_summary=tools.summarize(name, envelope))
        )
        if restored["data"] != data:
            raise DomainError("SOURCE_INVALID", "Remote content does not match source")
        if data["empty"] != (not data["chunks"]):
            raise DomainError("OUTPUT_INVALID", "Empty flag mismatch")
    else:
        ids = [x["spec_id"] for x in data["candidates"]]
        if len(ids) != len(set(ids)):
            raise DomainError("OUTPUT_INVALID", "Duplicate specifications")
        vehicle = narrow(case["vehicle_json"], body.vehicle_scope)
        for item in data["candidates"]:
            row, ev = tools.approved(c, ctx, UUID(item["spec_id"]))
            expected = dict(
                spec_id=str(row["id"]),
                evidence_id=str(row["evidence_id"]),
                version=row["version"],
                definition=row["definition"],
            )
            if (
                item != expected
                or row["definition"]["component_key"] != body.component_key
                or row["definition"]["quantity"] != body.quantity
                or applicability(ev["review_snapshot"].get("scope", {}), vehicle)["status"]
                != "matched"
            ):
                raise DomainError("SOURCE_INVALID", "Remote specification not authorized")
        if data["empty"] != (not data["candidates"]):
            raise DomainError("OUTPUT_INVALID", "Empty flag mismatch")
    return data


def provenance(data):
    if "chunks" in data:
        return [
            {
                k: x[k]
                for k in ("chunk_id", "document_version_id", "index_id", "content_hash", "locator")
            }
            for x in data["chunks"]
        ]
    return [
        dict(spec_id=x["spec_id"], evidence_id=x["evidence_id"], version=x["version"])
        for x in data["candidates"]
    ]
