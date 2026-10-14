import hashlib
import json
import re
import time
from datetime import timedelta
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select, text, update
from sqlalchemy.exc import SQLAlchemyError

from app.domain.policies import DomainError
from app.infrastructure.orm import tool_calls, tool_executions
from app.infrastructure.uow import UnitOfWork
from app.services.evidence_scope import owner_lock
from app.tools.context import ContextFactory
from app.tools.manual_tools import ManualTools
from app.tools.schemas import INPUTS, OUTPUTS, Envelope


class ToolExecutor:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings
        self.contexts = ContextFactory(engine, settings)
        self.tools = ManualTools(engine, settings)

    def error(self, code, retryable=False, duration=0):
        return Envelope(
            ok=False,
            data=None,
            error=dict(
                code=code, message="Tool call did not complete: " + code, retryable=retryable
            ),
            provenance=[],
            duration_ms=duration,
        ).model_dump(mode="json")

    def checked_data(self, name, data):
        try:
            out = OUTPUTS[name].model_validate(data).model_dump(mode="json")
        except (ValidationError, TypeError):
            raise DomainError("OUTPUT_INVALID", "Invalid tool output", 500) from None
        if len(json.dumps(out, ensure_ascii=False).encode()) > 65536:
            raise DomainError("RESULT_TOO_LARGE", "Tool result exceeds limit", 422)
        return out

    def check_use(self, c, ctx, name, body, data=None):
        if name == "compare_measurement":
            self.tools.approved(c, ctx, body.spec_id)
        if name == "get_measurement_spec" and data is not None:
            from uuid import UUID

            for x in data["candidates"]:
                self.tools.approved(c, ctx, UUID(x["spec_id"]))

    def reserve(self, context, name, body, key, digest, *, retry=False):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            principal = context.auth.get(context.cookie)
            owner_lock(c, principal.actor_id)
            ctx, case = self.contexts.load(c, context, lock=True)
            if name not in ctx["allowlist"]:
                raise DomainError("TOOL_FORBIDDEN", "Tool not allowed", 403)
            self.check_use(c, ctx, name, body)
            row = (
                c.execute(
                    select(tool_calls)
                    .where(tool_calls.c.execution_id == ctx["id"], tool_calls.c.call_key == key)
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            now = c.execute(text("select clock_timestamp()")).scalar_one()
            if row:
                if row["tool"] != name or row["args_hash"] != digest:
                    raise DomainError(
                        "CALL_CONFLICT", "Logical identity reused with different input"
                    )
                if row["status"] == "running":
                    if row["deadline"] > now:
                        raise DomainError("CALL_IN_PROGRESS", "Call already running")
                    c.execute(
                        update(tool_calls)
                        .where(tool_calls.c.id == row["id"])
                        .values(status="uncertain", error_code="CALL_UNCERTAIN")
                    )
                    return None, None, self.error("CALL_UNCERTAIN")
                if row["status"] == "succeeded":
                    answer = self.tools.hydrate(c, ctx, case, name, body, row)
                    self.check_use(c, ctx, name, body, answer["data"])
                    answer["data"] = self.checked_data(name, answer["data"])
                    answer = Envelope.model_validate(answer).model_dump(mode="json")
                    if len(json.dumps(answer, ensure_ascii=False).encode()) > 65536:
                        raise DomainError("RESULT_TOO_LARGE", "Tool result exceeds limit", 422)
                    return None, None, answer
                if (
                    not retry
                    or row["status"] != "failed"
                    or row["error_code"] not in ["TOOL_TRANSIENT", "DATABASE_BUSY"]
                    or row["attempts"] > ctx["retry_limit"]
                ):
                    return None, None, self.error(row["error_code"] or "CALL_UNCERTAIN")
            if ctx["used"] >= ctx["call_limit"] or (
                name == "search_manuals" and ctx["search_used"] >= ctx["search_limit"]
            ):
                raise DomainError("BUDGET_EXHAUSTED", "Tool budget exhausted", 429)
            c.execute(
                update(tool_executions)
                .where(tool_executions.c.id == ctx["id"])
                .values(
                    used=ctx["used"] + 1,
                    search_used=ctx["search_used"] + int(name == "search_manuals"),
                )
            )
            values = dict(
                status="running",
                attempts=(row["attempts"] + 1 if row else 1),
                deadline=now + timedelta(milliseconds=ctx["timeout_ms"]),
                error_code=None,
            )
            if row:
                saved = (
                    c.execute(
                        update(tool_calls)
                        .where(tool_calls.c.id == row["id"])
                        .values(**values)
                        .returning(tool_calls)
                    )
                    .mappings()
                    .one()
                )
            else:
                saved = (
                    c.execute(
                        tool_calls.insert()
                        .values(
                            id=uuid4(),
                            execution_id=ctx["id"],
                            call_key=key,
                            tool=name,
                            args_hash=digest,
                            **values,
                        )
                        .returning(tool_calls)
                    )
                    .mappings()
                    .one()
                )
            return dict(saved), (dict(ctx), dict(case)), None

    def guard(self, c, call):
        row = (
            c.execute(select(tool_calls).where(tool_calls.c.id == call["id"]).with_for_update())
            .mappings()
            .one()
        )
        if row["status"] != "running":
            raise DomainError("CALL_UNCERTAIN", "Call state changed")
        if row["cancel_requested"]:
            raise DomainError("TOOL_CANCELLED", "Call cancelled")
        if c.execute(text("select clock_timestamp()")).scalar_one() >= call["deadline"]:
            raise DomainError("TOOL_TIMEOUT", "Deadline exceeded", 504)

    def publish(self, c, context, name, body, call, data, start):
        ctx, case = self.contexts.load(c, context)
        if self.settings.tool_mode == "remote_mcp" and name in (
            "search_manuals",
            "get_evidence_context",
            "get_measurement_spec",
        ):
            from app.mcp_server.validation import validate_result

            data = validate_result(self.tools, c, ctx, case, name, body, data)
        self.check_use(c, ctx, name, body, data)
        data = self.checked_data(name, data)
        self.guard(c, call)
        provenance = [
            {
                k: x[k]
                for k in ["chunk_id", "document_version_id", "index_id", "content_hash", "locator"]
            }
            for x in data.get("chunks", [])
        ]
        if "spec_id" in data:
            provenance = [
                dict(
                    spec_id=data["spec_id"],
                    spec_version=data["spec_version"],
                    comparison_id=data["comparison_id"],
                )
            ]
        if "candidates" in data:
            provenance = [
                dict(spec_id=x["spec_id"], evidence_id=x["evidence_id"], version=x["version"])
                for x in data["candidates"]
            ]
        answer = Envelope(
            ok=True,
            data=data,
            error=None,
            provenance=provenance,
            duration_ms=max(0, int((time.monotonic() - start) * 1000)),
        ).model_dump(mode="json")
        if len(json.dumps(answer, ensure_ascii=False).encode()) > 65536:
            raise DomainError("RESULT_TOO_LARGE", "Envelope exceeds limit", 422)
        c.execute(
            update(tool_calls)
            .where(tool_calls.c.id == call["id"])
            .values(
                status="succeeded",
                duration_ms=answer["duration_ms"],
                result_summary=self.tools.summarize(name, answer),
            )
        )
        # Last database-clock check AFTER all publication SQL; original deadline not replaced by terminal state.
        if c.execute(text("select clock_timestamp()")).scalar_one() >= call["deadline"]:
            raise DomainError("TOOL_TIMEOUT", "Deadline exceeded", 504)
        return answer

    def failure(self, call, code, duration):
        with UnitOfWork(self.engine) as u:
            u.connection.execute(
                update(tool_calls)
                .where(tool_calls.c.id == call["id"], tool_calls.c.status == "running")
                .values(status="failed", error_code=code, duration_ms=duration, result_summary={})
            )

    def cancel(self, context, call_key):
        with UnitOfWork(self.engine) as u:
            ctx, _ = self.contexts.load(u.connection, context, current=False)
            return (
                u.connection.execute(
                    update(tool_calls)
                    .where(
                        tool_calls.c.execution_id == ctx["id"],
                        tool_calls.c.call_key == call_key,
                        tool_calls.c.status == "running",
                    )
                    .values(cancel_requested=True)
                ).rowcount
                == 1
            )

    def execute(self, context, name, arguments, call_key):
        start = time.monotonic()
        call = None
        try:
            if name not in INPUTS:
                raise DomainError("TOOL_UNKNOWN", "Unknown tool", 404)
            # Validate trusted context/allowlist before processing model parameters.
            with UnitOfWork(self.engine) as u:
                ctx, _ = self.contexts.load(u.connection, context)
                if name not in ctx["allowlist"]:
                    raise DomainError("TOOL_FORBIDDEN", "Tool not allowed", 403)
            if not isinstance(call_key, str) or not re.fullmatch(
                r"[A-Za-z0-9._:-]{1,100}", call_key
            ):
                raise DomainError("CALL_ID_INVALID", "Invalid logical call identity", 422)
            try:
                body = INPUTS[name].model_validate(arguments)
            except ValidationError:
                raise DomainError("PARAM_INVALID", "Tool parameters invalid", 422) from None
            digest = hashlib.sha256(
                json.dumps(
                    body.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            retry = False
            while True:
                call, loaded, replay = self.reserve(
                    context, name, body, call_key, digest, retry=retry
                )
                if replay is not None:
                    return replay
                ctx, case = loaded
                try:
                    if name == "compare_measurement":
                        with UnitOfWork(self.engine) as u:
                            c = u.connection
                            owner_lock(c, ctx["actor_id"])
                            ctx, case = self.contexts.load(c, context)
                            remaining = max(
                                1,
                                int(
                                    (
                                        call["deadline"]
                                        - c.execute(text("select clock_timestamp()")).scalar_one()
                                    ).total_seconds()
                                    * 1000
                                ),
                            )
                            c.execute(
                                text("select set_config('statement_timeout',:ms,true)"),
                                {"ms": str(remaining)},
                            )
                            data = self.tools.execute(
                                name, body, ctx, case, call["id"], connection=c
                            )
                            return self.publish(c, context, name, body, call, data, start)
                    if self.settings.tool_mode == "remote_mcp" and name in (
                        "search_manuals",
                        "get_evidence_context",
                        "get_measurement_spec",
                    ):
                        from app.infrastructure.mcp_client import remote_call

                        data = remote_call(
                            self.settings.mcp_client_config,
                            ctx,
                            name,
                            body,
                            ctx["timeout_ms"] / 1000,
                        )
                    else:
                        data = self.tools.execute(name, body, ctx, case, call["id"])
                    with UnitOfWork(self.engine) as u:
                        owner_lock(u.connection, ctx["actor_id"])
                        return self.publish(u.connection, context, name, body, call, data, start)
                except DomainError as exc:
                    self.failure(call, exc.code, max(0, int((time.monotonic() - start) * 1000)))
                    if (
                        name != "compare_measurement"
                        and exc.code in ["TOOL_TRANSIENT", "DATABASE_BUSY"]
                        and call["attempts"] <= ctx["retry_limit"]
                    ):
                        retry = True
                        continue
                    raise
                except SQLAlchemyError as exc:
                    if getattr(getattr(exc, "orig", None), "sqlstate", None) == "57014":
                        self.failure(
                            call, "TOOL_TIMEOUT", max(0, int((time.monotonic() - start) * 1000))
                        )
                        raise DomainError(
                            "TOOL_TIMEOUT", "Database statement deadline exceeded", 504
                        ) from None
                    # Commit/connection outcome can be ambiguous: never automatically repeat a side effect.
                    raise DomainError(
                        "CALL_UNCERTAIN", "Database outcome must be inspected", 503
                    ) from None
        except DomainError as exc:
            return self.error(
                exc.code,
                exc.code in ["TOOL_TRANSIENT", "DATABASE_BUSY"],
                max(0, int((time.monotonic() - start) * 1000)),
            )
        except SQLAlchemyError:
            return self.error(
                "DATABASE_UNAVAILABLE", False, max(0, int((time.monotonic() - start) * 1000))
            )
        except Exception:
            if call:
                try:
                    self.failure(
                        call, "INTERNAL_ERROR", max(0, int((time.monotonic() - start) * 1000))
                    )
                except SQLAlchemyError:
                    pass
            return self.error("INTERNAL_ERROR")
