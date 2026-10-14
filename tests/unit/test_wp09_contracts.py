import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from app.config import Settings, load_settings
from app.infrastructure.embedding_gateway import EmbeddingError
from app.infrastructure.model_budget import BudgetError, BudgetLedger
from app.infrastructure.model_factory import embedding_factory
from app.infrastructure.model_gateway import DeepSeekGateway, ModelError
from app.skills.registry import ROOT, SkillError, SkillRegistry
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ConfigDict


class Result(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str
    synthetic: bool


def rig(tmp_path, answers):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    ledger.initialize("offline synthetic only")
    seen = []

    def response(req):
        seen.append(json.loads(req.content))
        item = answers.pop(0)
        if isinstance(item, int):
            return httpx.Response(
                item,
                json={"error": {"message": "synthetic secret must not leak", "code": "synthetic"}},
            )
        return httpx.Response(
            200,
            json=dict(
                id="synthetic",
                object="chat.completion",
                created=0,
                model="deepseek-flash",
                choices=[dict(index=0, message=item, finish_reason=item.pop("_finish", "stop"))],
            ),
        )

    settings = Settings(deepseek_api_key="offline-placeholder", deepseek_model="deepseek-flash")
    g = DeepSeekGateway(settings, transport=httpx.MockTransport(response), ledger=ledger)
    return g, ledger, seen


def test_structured_repair_usage_unknown(tmp_path):
    g, ledger, seen = rig(
        tmp_path,
        [
            {"role": "assistant", "content": "bad-json"},
            {"role": "assistant", "content": '{"message":"test","synthetic":true}'},
        ],
    )
    assert g.generate_structured(Result, [HumanMessage(content="synthetic")]).synthetic
    assert len(seen) == 2 and all(
        x["usage_status"] == "unknown" and x["usage"] is None
        for x in ledger.read()["calls"].values()
    )
    assert float(ledger.read()["reserved_cny"]) > 0
    g.close()


@pytest.mark.parametrize(
    "message,code",
    [
        ({"role": "assistant", "content": ""}, "MODEL_EMPTY"),
        ({"role": "assistant", "content": "x", "_finish": "length"}, "MODEL_TRUNCATED"),
    ],
)
def test_response_errors(tmp_path, message, code):
    g, ledger, _ = rig(tmp_path, [message])
    with pytest.raises(ModelError, match=code):
        g.generate_structured(Result, [])
    assert len(ledger.read()["calls"]) == 1
    g.close()


@pytest.mark.parametrize("status,retries", [(429, 2), (503, 2), (401, 1)])
def test_retry_count_and_redaction(tmp_path, status, retries):
    g, ledger, _ = rig(tmp_path, [status, status])
    with pytest.raises(ModelError) as e:
        g.invoke_with_tools([], [])
    assert "secret" not in str(e.value)
    assert len(ledger.read()["calls"]) == retries
    g.close()


def test_no_paid_default_and_config(tmp_path, monkeypatch):
    with pytest.raises(ModelError, match="PAID_CALL_NOT_AUTHORIZED"):
        DeepSeekGateway(Settings(deepseek_api_key="x"))
    with pytest.raises(ValueError):
        Settings(embedding_provider="unknown")
    with pytest.raises(EmbeddingError):
        embedding_factory(
            Settings(embedding_provider="local_bge_m3", embedding_model_path=tmp_path / "missing")
        )
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert load_settings(project_env=True).deepseek_api_key is None
    monkeypatch.setenv("DEEPSEEK_MODEL", "environment")
    assert load_settings(project_env=True).deepseek_model == "environment"
    assert load_settings(project_env=True, deepseek_model="explicit").deepseek_model == "explicit"


def test_budget_atomic_restart_and_duplicate(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    ledger.initialize("offline")
    d = ledger.read()
    d["reserved_cny"] = "4.96"
    ledger.save(d)

    def attempt(i):
        try:
            ledger.reserve(str(i), "deepseek-flash", "x" * 1000, 2048)
            return True
        except BudgetError:
            return False

    with ThreadPoolExecutor(2) as p:
        results = list(p.map(attempt, [1, 2]))
    assert sum(results) == 2
    other = BudgetLedger(ledger.path)
    assert other.read()["reserved_cny"] == ledger.read()["reserved_cny"]
    with pytest.raises(BudgetError):
        other.reserve("1", "deepseek-flash", "x", 1)


def test_skills_hash_scope_and_reference(tmp_path):
    import shutil

    root = tmp_path / "skills"
    shutil.copytree(ROOT, root)
    r = SkillRegistry(root)
    m = r.select("cooling", {"vehicle": "synthetic"})[0]
    body = r.load_body(m["name"], m["version"])
    assert body["evidence"] == []
    assert r.load_references(m["name"], ["method.md"])
    for bad in ["../outside", "/outside"]:
        with pytest.raises(SkillError):
            r.path(bad)
    with pytest.raises(SkillError):
        r.load_references(m["name"], ["../secret"])
    (root / m["name"] / "SKILL.md").write_text("tampered")
    with pytest.raises(SkillError, match="HASH"):
        r.load_body(m["name"], m["version"])


def test_multicall_ids_and_skill_narrow(tmp_path):
    calls = [
        dict(
            id="a",
            type="function",
            function=dict(name="get_case_observations", arguments='{"at_revision":0}'),
        ),
        dict(
            id="b",
            type="function",
            function=dict(name="get_case_observations", arguments='{"at_revision":0}'),
        ),
    ]
    g, ledger, seen = rig(
        tmp_path,
        [
            dict(role="assistant", content="", tool_calls=calls),
            dict(role="assistant", content="done"),
            dict(role="assistant", content='{"message":"synthetic","synthetic":true}'),
        ],
    )

    class Executor:
        def execute(self, context, name, args, key):
            return dict(ok=True, data={"empty": True}, error=None, provenance=[], duration_ms=0)

    result, records = g.run_tools(
        [HumanMessage(content="synthetic")],
        Result,
        Executor(),
        object(),
        allowed_tools=["get_case_observations"],
    )
    assert result.synthetic
    assert [x["tool_call_id"] for x in records] == ["a", "b"]
    assert [x["tool_call_id"] for x in seen[1]["messages"] if x["role"] == "tool"] == ["a", "b"]
    g.close()


def test_tool_phase_direct_to_json(tmp_path):
    call = dict(
        id="native-a",
        type="function",
        function=dict(name="get_case_observations", arguments='{"at_revision":0}'),
    )
    g, ledger, seen = rig(
        tmp_path,
        [
            dict(role="assistant", content="", tool_calls=[call]),
            dict(role="assistant", content='{"message":"synthetic","synthetic":true}'),
        ],
    )

    class Executor:
        def execute(self, context, name, args, key):
            return dict(ok=True, data={"empty": True}, error=None, provenance=[], duration_ms=0)

    answer, records = g.run_tools(
        [],
        Result,
        Executor(),
        object(),
        allowed_tools=["get_case_observations"],
        tool_round_limit=1,
    )
    assert (
        answer.synthetic
        and len(seen) == 2
        and seen[1]["response_format"] == {"type": "json_object"}
    )
    assert [x["tool_call_id"] for x in seen[1]["messages"] if x["role"] == "tool"] == ["native-a"]
    g.close()


@pytest.mark.parametrize("bad", ["duplicate", "forbidden", "skill"])
def test_tool_gate_before_execution(tmp_path, bad):
    calls = [
        dict(
            id="a",
            type="function",
            function=dict(name="get_case_observations", arguments='{"at_revision":0}'),
        )
    ]
    if bad == "duplicate":
        calls += calls
    g, ledger, _ = rig(tmp_path, [dict(role="assistant", content="", tool_calls=calls)])
    executed = []

    class Executor:
        def execute(self, context, name, args, key):
            executed.append(key)
            return dict(ok=True, data={}, error=None, provenance=[], duration_ms=0)

    with pytest.raises(ModelError, match="TOOL_CALL_ID_INVALID|TOOL_FORBIDDEN"):
        g.run_tools(
            [],
            Result,
            Executor(),
            object(),
            allowed_tools=[] if bad == "forbidden" else ["get_case_observations"],
            skill={"allowed_tools": []} if bad == "skill" else None,
        )
    assert len(executed) == (1 if bad == "duplicate" else 0)
    g.close()


def test_invalid_json_bounded_and_turn_deadline(tmp_path):
    g, ledger, seen = rig(tmp_path, [dict(role="assistant", content="bad")] * 2)
    with pytest.raises(ModelError, match="MODEL_SCHEMA_INVALID"):
        g.generate_structured(Result, [])
    assert len(seen) == 2
    g.started -= 121
    with pytest.raises(ModelError, match="MODEL_TURN_BUDGET_EXHAUSTED"):
        g.invoke_with_tools([], [])
    assert len(ledger.read()["calls"]) == 2
    g.close()


def test_graph_mode_leaves_business_repair_to_persisted_turn(tmp_path):
    g, ledger, sent = rig(tmp_path, [
        dict(role="assistant", content="No tool needed"),
        dict(role="assistant", content="bad-json"),
    ])

    class UnusedExecutor:
        def execute(self, *_):
            raise AssertionError("No tool call expected")

    with pytest.raises(ModelError, match="MODEL_SCHEMA_INVALID"):
        g.run_tools([], Result, UnusedExecutor(), object(), allowed_tools=[],
                    structured_repair=False)
    assert len(sent) == 2 and len(ledger.read()["calls"]) == 2
    g.close()


def test_graph_mode_tool_round_limit_does_not_hide_json_repair(tmp_path):
    call = dict(id="bounded-tool", type="function", function=dict(
        name="get_case_observations", arguments='{"at_revision":0}'))
    g, ledger, sent = rig(tmp_path, [
        dict(role="assistant", content="", tool_calls=[call]),
        dict(role="assistant", content="bad-json"),
    ])

    class Executor:
        def execute(self, context, name, args, key):
            return dict(ok=True, data={"empty": True}, error=None,
                        provenance=[], duration_ms=0)

    with pytest.raises(ModelError, match="MODEL_SCHEMA_INVALID"):
        g.run_tools([], Result, Executor(), object(),
                    allowed_tools=["get_case_observations"], tool_round_limit=1,
                    structured_repair=False)
    assert len(sent) == 2 and len(ledger.read()["calls"]) == 2
    g.close()


def test_bge_fingerprint_and_values():
    from app.infrastructure.bge_gateway import CONFIG
    from app.infrastructure.embedding_gateway import validate_vectors
    from app.infrastructure.model_factory import check_fingerprint

    assert check_fingerprint(CONFIG)["dimension"] == 1024
    with pytest.raises(EmbeddingError):
        check_fingerprint(dict(CONFIG, dimension=384))
    for vector in [[0.0] * 1024, [float("nan")] * 1024, [float("inf")] * 1024, [1.0] * 384]:
        with pytest.raises(EmbeddingError):
            validate_vectors([vector], 1, 1024)


def test_budget_options_and_e5_conflict(tmp_path):
    from app.infrastructure.model_factory import selected_config

    with pytest.raises(EmbeddingError, match="CONFIG_MISMATCH"):
        selected_config(Settings(embedding_provider="local_e5", embedding_dimension=1024))
    g, ledger, seen = rig(tmp_path, [])
    with pytest.raises(ModelError, match="MODEL_OPTIONS_DENIED"):
        g.request([], max_tokens=999999)
    assert not seen and not ledger.read()["calls"]
    g.close()
