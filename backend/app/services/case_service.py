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
from app.infrastructure.orm import (
    cases, diagnosis_steps, idempotency_keys, runs,
)
from app.infrastructure.uow import UnitOfWork
from app.repositories.cases import CaseRepository, snapshot

SCOPE = "POST /api/v2/cases"


class CaseService:
    def __init__(self, engine, cursor_secret, profile="formal", report_settings=None):
        self.engine, self.cursor_secret = engine, cursor_secret
        self.profile = profile
        self.report_settings = report_settings

    def create(self, actor, data, key):
        if data.workbench_flow != "template-match-v1":
            raise DomainError("LEGACY_CASE_READ_ONLY",
                              "旧版病例入口已停用；请使用车辆信息匹配模板创建病例。", 409)
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
            from app.services.evidence_scope import owner_lock

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
            from app.services.workbench_templates import frozen_snapshot
            if data.topic_version is not None or data.diagnosis_mode is not None:
                raise DomainError("INTAKE_FLOW_CONFLICT", "模板入口不能同时指定旧专题流程", 422)
            snap = frozen_snapshot(conn, data)
            normalized = data.model_copy(update={"vehicle": data.vehicle.model_copy(update=snap["vehicle"])})
            row = CaseRepository(conn).create(actor, normalized, [], intake_override=snap)
            conn.execute(update(cases).where(cases.c.id == row["id"]).values(
                revision=1, status="waiting_input", updated_at=text("clock_timestamp()")))
            row = conn.execute(select(cases).where(cases.c.id == row["id"])).mappings().one()
            body = self.with_active(conn, row)
            conn.execute(update(idempotency_keys).where(*match).values(response_json=body))
            return 201, body

    def get(self, actor, case_id, expected_revision=None):
        with UnitOfWork(self.engine) as uow:
            row = CaseRepository(uow.connection).get(actor, case_id)
            if row is None:
                raise DomainError("NOT_FOUND", "Case not found", 404)
            if expected_revision is not None:
                check_revision(row["revision"], expected_revision)
            return self.with_active(uow.connection, row)

    def with_active(self, conn, row):
        body = snapshot(row)
        if (row["intake_snapshot"] or {}).get("workbench_flow") == "template-match-v1":
            from app.services.template_case_history import load_summary

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
        if self.report_settings is not None:
            from app.services.report_policy import final_gate
            from app.services.report_policy import snapshot as report_snapshot

            gate = final_gate(conn, row["owner_id"],
                              report_snapshot(conn, row["owner_id"], row["id"],
                                              self.report_settings), self.report_settings)
            body["report_gate"] = {"available": gate["allowed"],
                                   "reason": None if gate["allowed"] else "FINAL_NOT_READY",
                                   "blocking_items": gate["blocking_items"]}
        check = conn.execute(select(diagnosis_steps).where(
            diagnosis_steps.c.case_id == row["id"],
            diagnosis_steps.c.status == "waiting_input")
        ).mappings().one_or_none()
        if check is not None:
            body["current_check"] = {
                "id": str(check["id"]), "area_id": str(check["area_id"]),
                "run_id": str(check["run_id"]), "status": check["status"],
                "candidate": check["candidate_json"],
                "validation": check["validation_json"],
            }
        active = (
            conn.execute(
                select(runs.c.id, runs.c.kind, runs.c.status).where(
                    runs.c.case_id == row["id"],
                    runs.c.status.in_(["queued", "running", "cancel_requested"]),
                )
            )
            .mappings()
            .one_or_none()
        )
        if active:
            body["active_run"] = dict(
                id=str(active["id"]), kind=active["kind"], status=active["status"]
            )
        body["experience"] = dict(
            category="reference", label="历史病例 · 只读",
            guidance="原有记录和建议保留，旧流程不再新增或更正。", priority=50,
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
                items=[self.with_active(uow.connection, x) for x in rows[:limit]],
                next_cursor=self.encode_cursor(actor, rows[limit - 1])
                if len(rows) > limit
                else None,
            )
