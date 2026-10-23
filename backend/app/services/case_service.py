import base64
import hashlib
import hmac
import json
import re
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert

from app.domain.policies import DomainError, check_revision
from app.infrastructure.orm import cases, idempotency_keys
from app.infrastructure.uow import UnitOfWork
from app.repositories.cases import CaseRepository, snapshot
from app.services.template_case_history import load_summary
from app.services.workbench_templates import frozen_snapshot

SCOPE = "POST /api/v2/cases"


def owner_lock(conn, actor):
    key = int.from_bytes(hashlib.sha256(("case-create:" + str(actor)).encode()).digest()[:8],
                         "big", signed=True)
    conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


class CaseService:
    def __init__(self, engine, cursor_secret):
        self.engine, self.cursor_secret = engine, cursor_secret

    def create(self, actor, data, key):
        if not key or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", key):
            raise DomainError("VALIDATION_ERROR", "Valid Idempotency-Key required", 422)
        digest = hashlib.sha256(
            json.dumps(
                data.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        match = (
            idempotency_keys.c.actor_id == actor,
            idempotency_keys.c.route_scope == SCOPE,
            idempotency_keys.c.key == key,
        )
        with UnitOfWork(self.engine) as uow:
            conn = uow.connection
            # One creation at a time per user, so two tabs cannot race on the same key.
            owner_lock(conn, actor)
            acquired = conn.execute(
                insert(idempotency_keys)
                .values(
                    actor_id=actor,
                    route_scope=SCOPE,
                    key=key,
                    request_hash=digest,
                    response_status=201,
                    response_json={},
                )
                .on_conflict_do_nothing(index_elements=["actor_id", "route_scope", "key"])
                .returning(idempotency_keys.c.key)
            ).scalar_one_or_none()
            if acquired is None:
                saved = conn.execute(select(idempotency_keys).where(*match)).mappings().one()
                if saved["request_hash"] != digest:
                    raise DomainError(
                        "IDEMPOTENCY_CONFLICT", "Idempotency key belongs to a different request"
                    )
                return saved["response_status"], saved["response_json"]
            snap = frozen_snapshot(conn, data)
            normalized = data.model_copy(update={"vehicle": data.vehicle.model_copy(update=snap["vehicle"])})
            row = CaseRepository(conn).create(actor, normalized, snap)
            conn.execute(update(cases).where(cases.c.id == row["id"]).values(
                revision=1, status="waiting_input", updated_at=text("clock_timestamp()")))
            row = conn.execute(select(cases).where(cases.c.id == row["id"])).mappings().one()
            body = self.with_progress(conn, row)
            conn.execute(update(idempotency_keys).where(*match).values(response_json=body))
            return 201, body

    def get(self, actor, case_id, expected_revision=None):
        with UnitOfWork(self.engine) as uow:
            row = CaseRepository(uow.connection).get(actor, case_id)
            if row is None:
                raise DomainError("NOT_FOUND", "Case not found", 404)
            if expected_revision is not None:
                check_revision(row["revision"], expected_revision)
            return self.with_progress(uow.connection, row)

    def with_progress(self, conn, row):
        """Case snapshot plus its progress summary (checks recorded, repair rounds, retests)."""
        body = snapshot(row)
        summary = load_summary(conn, row)
        body["template_progress"] = summary
        guidance = (f"检查 {summary['recorded']}/{summary['total']} 项 · "
                    f"处理 {summary['repair_rounds']} 轮 · 待复检 {summary['pending_retests']} 轮")
        body["experience"] = dict(
            category="completed" if summary["closed"] else
                     "waiting" if summary["pending_retests"] else "continue",
            label=summary["label"], guidance=guidance,
            priority=30 if summary["closed"] else 10,
        )
        return body

    def encode_cursor(self, actor, row):
        payload = json.dumps(
            [1, str(actor), row["created_at"].isoformat(), str(row["id"])], separators=(",", ":")
        ).encode()
        signature = hmac.digest(self.cursor_secret, payload, "sha256")
        return base64.urlsafe_b64encode(payload + signature).decode().rstrip("=")

    def decode_cursor(self, actor, value):
        try:
            if len(value) > 512 or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
                raise ValueError()
            raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
            payload, signature = raw[:-32], raw[-32:]
            if not hmac.compare_digest(
                hmac.digest(self.cursor_secret, payload, "sha256"), signature
            ):
                raise ValueError()
            version, owner, ts, identifier = json.loads(payload)
            moment = datetime.fromisoformat(ts)
            if version != 1 or owner != str(actor) or moment.tzinfo is None:
                raise ValueError()
            return moment, UUID(identifier)
        except (ValueError, TypeError, UnicodeError):
            raise DomainError("INVALID_CURSOR", "Invalid pagination cursor", 400) from None

    def list(self, actor, limit, cursor=None, scope='all'):
        after = self.decode_cursor(actor, cursor) if cursor else None
        with UnitOfWork(self.engine) as uow:
            rows = CaseRepository(uow.connection).list(actor, limit, after, scope=scope)
            return dict(
                items=[self.with_progress(uow.connection, x) for x in rows[:limit]],
                next_cursor=self.encode_cursor(actor, rows[limit - 1])
                if len(rows) > limit
                else None,
            )
