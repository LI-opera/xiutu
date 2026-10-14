
"""Real SDK HTTP client; retries belong exclusively to ToolExecutor."""

import asyncio
import json
from contextlib import AsyncExitStack
from datetime import timedelta
from urllib.parse import urlsplit

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import SecretStr, field_validator

from app.domain.policies import DomainError
from app.mcp_server.config import TOOLS, Binding, Strict, output_schema, read_config
from app.mcp_server.validation import checked, provenance
from app.tools.schemas import INPUTS, Envelope


class ClientConfig(Strict):
    url: str
    token: SecretStr
    binding: Binding

    @field_validator("url")
    @classmethod
    def safe_endpoint(cls, value):
        p = urlsplit(value)
        if (
            p.scheme != "http"
            or p.hostname not in {"127.0.0.1", "localhost", "manual-mcp"}
            or p.path != "/mcp"
            or p.query
            or p.fragment
            or p.username
            or p.password
            or not p.port
        ):
            raise ValueError("Only fixed local/internal MCP endpoint supported")
        return value


class ManualMCPClient:
    def __init__(self, config, timeout=10):
        self.config = config
        self.timeout = min(10, timeout)
        self.stack = None
        self.session = None
        self.protocol = None

    async def connect(self):
        self.stack = AsyncExitStack()
        await self.stack.__aenter__()
        try:
            client = await self.stack.enter_async_context(
                httpx.AsyncClient(
                    headers={"Authorization": "Bearer " + self.config.token.get_secret_value()},
                    timeout=httpx.Timeout(self.timeout),
                    trust_env=False,
                )
            )
            read, write, _ = await self.stack.enter_async_context(
                streamable_http_client(self.config.url, http_client=client)
            )
            self.session = await self.stack.enter_async_context(
                ClientSession(read, write, read_timeout_seconds=timedelta(seconds=self.timeout))
            )
            initialized = await self.session.initialize()
            self.protocol = initialized.protocolVersion
            if self.protocol != "2025-11-25":
                raise DomainError("MCP_PROTOCOL_INVALID", "Unexpected MCP protocol", 502)
            await self.discover()
            return self
        except BaseException:
            await self.close()
            raise

    async def discover(self):
        result = await self.session.list_tools()
        found = {t.name: t for t in result.tools}
        if (
            result.nextCursor
            or len(found) != 3
            or len(result.tools) != 3
            or set(found) != set(TOOLS)
        ):
            raise DomainError("MCP_SCHEMA_INVALID", "Unexpected MCP tools", 502)
        for name, t in found.items():
            if (
                t.inputSchema != INPUTS[name].model_json_schema()
                or t.outputSchema != output_schema(name)
                or not t.annotations
                or t.annotations.readOnlyHint is not True
            ):
                raise DomainError("MCP_SCHEMA_INVALID", "MCP schema differs", 502)
        return found

    async def call(self, name, arguments):
        if name not in TOOLS:
            raise DomainError("TOOL_FORBIDDEN", "Remote tool forbidden", 403)
        result = await self.session.call_tool(name, arguments)
        try:
            answer = Envelope.model_validate(result.structuredContent).model_dump(mode="json")
            if len(json.dumps(answer, ensure_ascii=False).encode()) > 65536:
                raise DomainError("RESULT_TOO_LARGE", "Remote result too large", 502)
            if not answer["ok"]:
                if answer["error"] is None or answer["data"] is not None or not result.isError:
                    raise ValueError("Inconsistent error")
                # Remote service never authorizes retries of semantic/SQL errors.
                raise DomainError(answer["error"]["code"], "Remote call rejected", 502)
            if answer["error"] is not None or result.isError:
                raise ValueError("Inconsistent success")
            answer["data"] = checked(name, answer["data"])
            if answer["provenance"] != provenance(answer["data"]):
                raise ValueError("Provenance mismatch")
            return answer
        except DomainError:
            raise
        except Exception:
            raise DomainError("OUTPUT_INVALID", "Invalid remote envelope", 502) from None

    async def close(self):
        if self.stack is not None:
            stack, self.stack = self.stack, None
            await stack.aclose()
        self.session = None

    async def exchange(self, name, args):
        try:
            async with asyncio.timeout(self.timeout):
                await self.connect()
                try:
                    return await self.call(name, args)
                finally:
                    await self.close()
        except BaseException as exc:
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise classify(exc) from None


def classify(exc):
    if isinstance(exc, BaseExceptionGroup):
        errors = [classify(x) for x in exc.exceptions]
        # Any permanent failure takes precedence over retryable transport failures.
        return next((x for x in errors if x.code != "TOOL_TRANSIENT"), errors[0])
    if isinstance(exc, DomainError):
        return exc
    if isinstance(exc, httpx.HTTPStatusError):
        return DomainError(
            "MCP_UNAUTHORIZED" if exc.response.status_code == 401 else "MCP_HTTP_REJECTED",
            "MCP request rejected",
            502,
        )
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return DomainError("TOOL_TIMEOUT", "MCP deadline exceeded", 504)
    if isinstance(exc, (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError)):
        return DomainError("TOOL_TRANSIENT", "MCP transport interrupted", 503)
    return DomainError("MCP_PROTOCOL_ERROR", "MCP exchange failed", 502)


def remote_call(path, ctx, name, body, timeout=10):
    try:
        cfg = read_config(path, ClientConfig)
    except Exception:
        raise DomainError(
            "MCP_CONFIG_UNAVAILABLE", "Protected MCP client configuration required", 503
        ) from None
    bound = cfg.binding.context()
    if (
        any(bound[k] != ctx[k] for k in ("actor_id", "case_id", "revision", "manifest", "profile"))
        or name not in bound["allowlist"]
    ):
        raise DomainError("CONTEXT_INVALID", "Credential does not match application context", 403)
    return asyncio.run(ManualMCPClient(cfg, timeout).exchange(name, body.model_dump(mode="json")))[
        "data"
    ]
