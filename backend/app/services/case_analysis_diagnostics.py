"""Single bounded, owner-restricted diagnostic payload; never advice content."""

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.infrastructure.orm import case_analyses
from app.infrastructure.uow import UnitOfWork

MAX_RESPONSE_BYTES = 32768
RETENTION_DAYS = 30
_SECRET = re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+\S+|\bsk-[a-z0-9_-]{12,}\b)")


def _row(conn, analysis_id):
    row = conn.execute(select(case_analyses).where(case_analyses.c.id == analysis_id)
                       .with_for_update()).mappings().one()
    if row["status"] != "draft" or row["dispatch_state"] != "reserved":
        raise RuntimeError("ANALYSIS_DIAGNOSTIC_STATE_CONFLICT")
    return row


def record_response(engine, analysis_id, raw, metadata):
    original = raw if isinstance(raw, str) else None
    safe, count = _SECRET.subn("[REDACTED_CREDENTIAL]", original) if original is not None else (None, 0)
    safe_bytes = safe.encode("utf-8") if safe is not None else None
    bounded = safe_bytes[:MAX_RESPONSE_BYTES].decode("utf-8", errors="ignore") if safe_bytes is not None else None
    now = datetime.now(timezone.utc)
    with UnitOfWork(engine) as u:
        row = _row(u.connection, analysis_id)
        diagnostic = {
            "version": "c04-v1", "analysis_id": str(analysis_id),
            "input_revision": row["input_revision"], "stage": "response_received",
            "raw_response": bounded,
            "response_available": original is not None,
            "response_characters": len(original) if original is not None else None,
            "response_utf8_bytes": len(original.encode("utf-8")) if original is not None else None,
            "sha256": hashlib.sha256(original.encode()).hexdigest() if original is not None else None,
            "truncated": len(safe_bytes) > MAX_RESPONSE_BYTES if safe_bytes is not None else None,
            "diagnostic_storage_truncated": (len(safe_bytes) > MAX_RESPONSE_BYTES
                                             if safe_bytes is not None else None),
            "provider_output_truncated": bool(metadata.get("provider_output_truncated")),
            "credentials_redacted": bool(count),
            "call_key": metadata.get("call_key", "")[:120],
            "finish_reason": str(metadata.get("finish_reason", ""))[:40],
            "returned_model": str(metadata["returned_model"])[:120] if metadata.get("returned_model") else None,
            "usage": metadata.get("usage"),
            "usage_available": metadata.get("usage") is not None,
            "retained_until": (now + timedelta(days=RETENTION_DAYS)).isoformat(),
        }
        u.connection.execute(update(case_analyses).where(case_analyses.c.id == analysis_id)
                             .values(diagnostic_json=diagnostic))
        # Future diagnostics expire lazily; historical advice and case facts stay intact.
        cutoff = now - timedelta(days=RETENTION_DAYS)
        u.connection.execute(update(case_analyses).where(
            case_analyses.c.id != analysis_id, case_analyses.c.created_at < cutoff,
            case_analyses.c.diagnostic_json != {}).values(diagnostic_json={}))


def record_result(engine, analysis_id, *, stage, code=None, details=None, parsed=None):
    with UnitOfWork(engine) as u:
        row = _row(u.connection, analysis_id)
        diagnostic = dict(row["diagnostic_json"] or {})
        diagnostic.setdefault("retained_until", (datetime.now(timezone.utc) +
                              timedelta(days=RETENTION_DAYS)).isoformat())
        diagnostic.update(version="c04-v1", analysis_id=str(analysis_id),
                          input_revision=row["input_revision"], stage=stage)
        if code:
            diagnostic["error_code"] = code[:80]
        if details:
            diagnostic["validation"] = details
        if parsed is not None:
            # Distinguish a successful parse without duplicating the response body.
            value = parsed.model_dump(mode="json") if hasattr(parsed, "model_dump") else parsed
            shape = value if isinstance(value, dict) else {}
            diagnostic["parsed_outline"] = {
                "fields": sorted(shape)[:24],
                "supported_direction_count": len(shape.get("supported_directions", [])),
                "step_kinds": [item.get("kind") for item in shape.get("steps", [])[:6]],
                "action_ids": [item.get("action_id") for item in shape.get("steps", [])[:6]],
                "sha256": hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            }
            diagnostic["parsed_type"] = type(parsed).__name__
            diagnostic["parsed_valid"] = True
        u.connection.execute(update(case_analyses).where(case_analyses.c.id == analysis_id)
                             .values(diagnostic_json=diagnostic))
