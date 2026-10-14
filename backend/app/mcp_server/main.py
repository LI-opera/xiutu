"""SDK Streamable HTTP service. No application cookies, budget or audit writes."""

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from uuid import uuid4

import anyio
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.domain.policies import DomainError
from app.infrastructure.schema_version import EXPECTED_REVISION
from app.infrastructure.uow import UnitOfWork
from app.mcp_server.config import TOOLS, ServerConfig, output_schema, read_config
from app.mcp_server.validation import provenance, validate_result
from app.services.evidence_scope import owned_case, owner_lock
from app.tools.context import validate_scope
from app.tools.manual_tools import ManualTools
from app.tools.schemas import INPUTS, Envelope


def create_app():
    # Suppress SDK warnings interpolating an untrusted tool name.
    logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.ERROR)
    path = os.environ["MANUAL_MCP_CONFIG"]
    initial = read_config(path, ServerConfig)
    engine = initial.database.engine()
    tools = ManualTools(engine, initial)
    server = Server("xiutu-manuals", version="wp08")

    def config():
        cfg = read_config(path, ServerConfig)
        # Database/profile/mount changes require restart, grants can revoke live.
        if cfg.model_dump(exclude={"grants"}) != initial.model_dump(exclude={"grants"}):
            raise DomainError("MCP_CONFIG_CHANGED", "Restart after configuration change", 503)
        return cfg

    def authorized(header, c):
        binding = config().authenticate(header)
        ctx = binding.context()
        owner_lock(c, ctx["actor_id"])
        case = owned_case(c, ctx["actor_id"], ctx["case_id"])
        validate_scope(c, ctx, case, initial.retrieval_profile)
        return ctx, case

    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name=n,
                description="Readonly authorized manual tool: " + n,
                inputSchema=INPUTS[n].model_json_schema(),
                outputSchema=output_schema(n),
                annotations=ToolAnnotations(
                    readOnlyHint=True, destructiveHint=False, openWorldHint=False
                ),
            )
            for n in TOOLS
        ]

    def execute(header, name, arguments):
        start = time.monotonic()
        try:
            if name not in TOOLS:
                raise DomainError("TOOL_FORBIDDEN", "Readonly tool not allowed", 403)
            body = INPUTS[name].model_validate(arguments)
            with UnitOfWork(engine) as u:
                ctx, case = authorized(header, u.connection)
                if name not in ctx["allowlist"]:
                    raise DomainError("TOOL_FORBIDDEN", "Tool outside credential scope", 403)
            data = tools.execute(name, body, ctx, case, uuid4())
            with UnitOfWork(engine) as u:
                fresh, current = authorized(header, u.connection)
                if fresh != ctx:
                    raise DomainError("CONTEXT_STALE", "Grant changed during call")
                data = validate_result(tools, u.connection, fresh, current, name, body, data)
                if time.monotonic() - start >= 10:
                    raise DomainError("TOOL_TIMEOUT", "Readonly processing deadline", 504)
                answer = Envelope(
                    ok=True,
                    data=data,
                    error=None,
                    provenance=provenance(data),
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
                if len(answer.model_dump_json().encode()) > 65536:
                    raise DomainError("RESULT_TOO_LARGE", "MCP envelope exceeds limit", 422)
                payload = answer.model_dump(mode="json")
                # Final authorization point: AFTER every blocking lock/source SQL,
                # while the original owner lock is still held. Only read-only
                # transaction exit and SDK response serialization follow this check.
                latest = config().authenticate(header).context()
                if latest != ctx:
                    raise DomainError("CONTEXT_STALE", "Grant changed during call")
                if name not in latest["allowlist"]:
                    raise DomainError("TOOL_FORBIDDEN", "Tool outside credential scope", 403)
                if time.monotonic() - start >= 10:
                    raise DomainError("TOOL_TIMEOUT", "Readonly processing deadline", 504)
                return payload
        except ValidationError:
            code = "PARAM_INVALID"
        except DomainError as exc:
            code = exc.code
        except SQLAlchemyError:
            code = "DATABASE_UNAVAILABLE"
        except Exception:
            code = "MCP_INTERNAL_ERROR"
        return Envelope(
            ok=False,
            data=None,
            error=dict(code=code, message="MCP call rejected: " + code, retryable=False),
            duration_ms=int((time.monotonic() - start) * 1000),
        ).model_dump(mode="json")

    @server.call_tool(validate_input=False)
    async def call_tool(name, arguments):
        # Never let SDK serialize exception strings containing inputs or SQL.
        header = server.request_context.request.headers.get("authorization")
        answer = await anyio.to_thread.run_sync(execute, header, name, arguments)
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(answer))],
            structuredContent=answer,
            isError=not answer["ok"],
        )

    manager = StreamableHTTPSessionManager(
        server, json_response=True, stateless=True, max_request_body_size=65536
    )

    async def health(request):
        try:
            config()
            with engine.connect() as c:
                row = c.execute(
                    text(
                        "select current_user,current_setting('transaction_read_only'),(select version_num from alembic_version),(select extversion from pg_extension where extname='vector')"
                    )
                ).one()
                role = c.execute(
                    text(
                        "select rolsuper,rolcreaterole,rolcreatedb,rolbypassrls from pg_roles where rolname=current_user"
                    )
                ).one()
                if (
                    row[0] != initial.database.user
                    or row[1] != "on"
                    or row[2] != EXPECTED_REVISION
                    or not row[3]
                    or any(role)
                ):
                    raise ValueError("Readonly configuration invalid")
            return JSONResponse({"status": "ready", "protocol": "2025-11-25", "readonly": True})
        except Exception:
            return JSONResponse({"status": "unavailable"}, status_code=503)

    @asynccontextmanager
    async def lifespan(app):
        async with manager.run():
            yield
        engine.dispose()

    app = Starlette(routes=[Route("/health", health)], lifespan=lifespan)

    # Use an ASGI wrapper so exact /mcp has no redirect and auth covers EVERY method.
    async def protected(scope, receive, send):
        if scope["type"] != "http":
            return await app(scope, receive, send)
        request = Request(scope)
        try:
            cfg = config()
            if request.headers.get("host") not in cfg.hosts:
                raise DomainError("MCP_HOST_DENIED", "Host denied", 403)
            origin = request.headers.get("origin")
            if origin is not None and origin not in cfg.origins:
                raise DomainError("MCP_ORIGIN_DENIED", "Origin denied", 403)
            if scope["path"] == "/mcp":
                cfg.authenticate(request.headers.get("authorization"))
                if "mcp-session-id" in request.headers:
                    raise DomainError("MCP_SESSION_DENIED", "Stateless sessions required", 400)
                return await manager.handle_request(scope, receive, send)
        except DomainError as exc:
            return await JSONResponse({"error": exc.code}, status_code=exc.status)(
                scope, receive, send
            )
        except Exception:
            return await JSONResponse({"error": "MCP_UNAVAILABLE"}, status_code=503)(
                scope, receive, send
            )
        return await app(scope, receive, send)

    return protected
