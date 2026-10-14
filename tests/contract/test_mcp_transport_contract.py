"""Controlled protocol failures complement (not replace) real integration transport."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from app.domain.policies import DomainError
from app.infrastructure.mcp_client import ClientConfig, ManualMCPClient, classify
from app.mcp_server.config import TOOLS, Database, output_schema
from app.tools.schemas import INPUTS
from mcp.types import Tool, ToolAnnotations


def config():
    return ClientConfig(
        url="http://127.0.0.1:8031/mcp",
        token="synthetic-test-token-not-production",
        binding=dict(
            actor_id=uuid4(), case_id=uuid4(), revision=0, manifest=[], profile="synthetic"
        ),
    )


@pytest.mark.parametrize(
    "defect", ["extra_tool", "missing_tool", "input_schema", "output_schema", "write_hint"]
)
def test_discovery_rejects_schema_or_permission_drift(defect):
    tools = [
        Tool(
            name=n,
            inputSchema=INPUTS[n].model_json_schema(),
            outputSchema=output_schema(n),
            annotations=ToolAnnotations(readOnlyHint=True),
        )
        for n in TOOLS
    ]
    if defect == "extra_tool":
        tools.append(Tool(name="compare_measurement", inputSchema={"type": "object"}))
    if defect == "missing_tool":
        tools.pop()
    if defect == "input_schema":
        tools[0].inputSchema = {"type": "object"}
    if defect == "output_schema":
        tools[0].outputSchema = {"type": "object"}
    if defect == "write_hint":
        tools[0].annotations.readOnlyHint = False

    class Session:
        async def list_tools(self):
            return SimpleNamespace(tools=tools, nextCursor=None)

    c = ManualMCPClient(config())
    c.session = Session()
    with pytest.raises(DomainError, match="MCP") as exc:
        asyncio.run(c.discover())
    assert exc.value.code == "MCP_SCHEMA_INVALID"


@pytest.mark.parametrize("defect", ["schema", "provenance", "oversize"])
def test_remote_output_failure_contract(defect):
    data = dict(empty=True, chunks=[])
    answer = dict(ok=True, data=data, error=None, provenance=[], duration_ms=1)
    if defect == "schema":
        data["chunks"] = "invalid"
    if defect == "provenance":
        answer["provenance"] = [{"fake": "reference"}]
    if defect == "oversize":
        answer["provenance"] = [{"oversize": "a" * 65537}]

    class Session:
        async def call_tool(self, *a):
            return SimpleNamespace(structuredContent=answer, isError=False)

    c = ManualMCPClient(config())
    c.session = Session()
    with pytest.raises(DomainError) as exc:
        asyncio.run(c.call("search_manuals", {}))
    assert exc.value.code == ("RESULT_TOO_LARGE" if defect == "oversize" else "OUTPUT_INVALID")


@pytest.mark.parametrize("envkey", ["PGHOST", "PGHOSTADDR", "PGSERVICE", "PGDATABASE"])
def test_mcp_target_rejects_environment_before_engine(monkeypatch, envkey):
    monkeypatch.setenv(envkey, "non-authorized")
    import app.mcp_server.config as module

    monkeypatch.setattr(
        module, "create_engine", lambda *a, **k: pytest.fail("Engine must not be created")
    )
    with pytest.raises(ValueError, match="PG environment"):
        Database(
            deployment="loopback",
            name="xiutu_test_wp08_contract",
            user="xiutu_mcp_contract",
            password="synthetic",
        ).engine()


@pytest.mark.parametrize(
    "url",
    [
        "https://external.invalid/mcp",
        "http://127.0.0.1:8031/mcp?token=x",
        "http://user:secret@127.0.0.1:8031/mcp",
        "http://127.0.0.1:8031/other",
    ],
)
def test_client_endpoint_is_trusted_configuration_only(url):
    cfg = config().model_dump()
    cfg["url"] = url
    with pytest.raises(ValueError):
        ClientConfig.model_validate(cfg)


def test_transport_retry_classification():
    assert classify(httpx.ConnectError("private text")).code == "TOOL_TRANSIENT"
    assert classify(httpx.ReadError("private text")).code == "TOOL_TRANSIENT"
    assert classify(TimeoutError()).code == "TOOL_TIMEOUT"
    request = httpx.Request("POST", "http://127.0.0.1:8031/mcp")
    for status in [401, 403, 400]:
        error = httpx.HTTPStatusError(
            "private text", request=request, response=httpx.Response(status, request=request)
        )
        safe = classify(error)
        assert safe.code != "TOOL_TRANSIENT" and "private" not in str(safe)
