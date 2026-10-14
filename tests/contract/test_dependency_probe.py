import importlib
import socket

import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_deepseek import ChatDeepSeek
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError


@pytest.mark.parametrize(
    "module",
    [
        "fastapi",
        "pydantic",
        "sqlalchemy",
        "psycopg",
        "alembic",
        "pgvector",
        "langgraph",
        "langgraph.checkpoint.postgres",
        "mcp",
    ],
)
def test_import(module):
    assert importlib.import_module(module)


def test_live_ready_no_network(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("Health must not call a model or any network without DB URL")

    with TestClient(
        create_app(
            Settings(
                database_url=None,
                data_path=tmp_path,
                deepseek_api_key=SecretStr("offline-placeholder"),
            )
        )
    ) as client:
        monkeypatch.setattr(socket.socket, "connect", forbidden)
        assert client.get("/api/v2/health/live").json() == {"status": "live"}
        response = client.get("/api/v2/health/ready")
        assert response.status_code == 503
        assert response.json()["model_configured"] is True
        assert response.json()["model_verified"] is False
        assert "offline-placeholder" not in response.text


def test_settings_redaction(tmp_path):
    settings = Settings(
        database_url="postgresql://user:private-marker@localhost/test",
        deepseek_api_key="private-marker",
        data_path=tmp_path,
    )
    assert "private-marker" not in repr(settings)
    assert "private-marker" not in settings.model_dump_json()
    with pytest.raises(ValidationError) as error:
        Settings(database_url="invalid-private-marker")
    assert "private-marker" not in str(error.value)


@pytest.mark.parametrize(
    "kwargs", [{"app_mode": "unknown"}, {"data_path": r"E:\Work\v4-double\data"}]
)
def test_settings_reject_invalid(kwargs):
    with pytest.raises(ValidationError):
        Settings(**kwargs)


class EchoContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: str
    success: bool


def test_offline_model_contract(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline model contract must not contact a provider")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    model = ChatDeepSeek(model="deepseek-chat", api_key="offline-placeholder", max_retries=0)
    bound = model.bind_tools([EchoContract])
    assert bound.kwargs["tools"][0] == convert_to_openai_tool(EchoContract)
    structured = model.with_structured_output(EchoContract)
    tool_parser = structured.steps[-1]
    parsed = tool_parser.invoke(
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "EchoContract",
                    "args": {"message": "offline", "success": True},
                    "id": "probe-1",
                }
            ],
        )
    )
    assert parsed == EchoContract(message="offline", success=True)
    with pytest.raises(ValidationError):
        tool_parser.invoke(
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "EchoContract", "args": {"message": 1}, "id": "probe-invalid"}
                ],
            )
        )
    parser = PydanticOutputParser(pydantic_object=EchoContract)
    assert parser.invoke(AIMessage(content='{"message":"probe","success":true}')).success
    for content in [
        '{"message":"probe"}',
        '{"message":1,"success":true}',
        '{"message":"probe","success":"yes"}',
        "not-json",
    ]:
        with pytest.raises(Exception):
            parser.invoke(AIMessage(content=content))


@pytest.mark.parametrize(
    "url",
    [
        None,
        "postgresql://user@localhost:5433/xiutu_dev",
        "postgresql://user@localhost:5432/xiutu_test_probe",
        "postgresql://user@example.com:5433/xiutu_test_probe",
    ],
)
def test_database_guard_rejects_unsafe(monkeypatch, url):
    from conftest import isolated_database_url

    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    if url:
        monkeypatch.setenv("TEST_DATABASE_URL", url)
    with pytest.raises(pytest.fail.Exception):
        isolated_database_url()


def test_offline_adapter_tool_roundtrip(monkeypatch):
    import json

    import httpx
    from langchain_core.messages import HumanMessage, ToolMessage

    def forbidden(*args, **kwargs):
        raise AssertionError("Offline adapter must not open a real socket")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        message = {"role": "assistant", "content": "offline complete"}
        if len(requests) == 1:
            message = {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "offline-call-1",
                        "type": "function",
                        "function": {
                            "name": "EchoContract",
                            "arguments": '{"message":"offline","success":true}',
                        },
                    }
                ],
            }
        return httpx.Response(
            200,
            json={
                "id": "offline-response",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-chat",
                "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = ChatDeepSeek(
            model="deepseek-chat", api_key="offline-placeholder", http_client=client, max_retries=0
        ).bind_tools([EchoContract])
        history = [HumanMessage(content="offline contract probe")]
        answer = model.invoke(history)
        assert answer.tool_calls[0]["id"] == "offline-call-1"
        args = EchoContract.model_validate(answer.tool_calls[0]["args"])
        result = ToolMessage(
            content=args.model_dump_json(), tool_call_id=answer.tool_calls[0]["id"]
        )
        final = model.invoke(history + [answer, result])
        assert final.content == "offline complete"
        assert requests[1]["messages"][-1]["tool_call_id"] == "offline-call-1"
        assert requests[1]["messages"][-1]["role"] == "tool"


def test_offline_adapter_timeout(monkeypatch):
    import httpx
    from openai import APITimeoutError

    def forbidden(*args, **kwargs):
        raise AssertionError("Offline adapter must not open a real socket")

    monkeypatch.setattr(socket.socket, "connect", forbidden)

    def timeout(request):
        raise httpx.ReadTimeout("synthetic offline timeout", request=request)

    with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
        model = ChatDeepSeek(
            model="deepseek-chat", api_key="offline-placeholder", http_client=client, max_retries=0
        )
        with pytest.raises(APITimeoutError):
            model.invoke("offline timeout branch")
