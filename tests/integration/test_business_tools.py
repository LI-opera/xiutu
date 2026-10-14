"""WP07 synthetic data with real DB/services/worker; no paid model calls."""

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier, Event
from uuid import UUID, uuid4

import pytest
from app.api.dependencies import AuthStore
from app.config import Settings
from app.domain.policies import DomainError
from app.infrastructure.orm import (
    cases,
    measurement_comparisons,
    observations,
    tool_calls,
    tool_executions,
)
from app.tools.executor import ToolExecutor
from app.tools.registry import export_schemas, langchain_tool
from sqlalchemy import func, select, text, update
from test_document_ingest import docrig  # noqa: F401
from test_evidence_measurement import (
    approve,
    archived_bind,
    archived_case,
    archived_citation,
    document,
    review,
    spec,
)  # noqa: F401

pytestmark = pytest.mark.database


@pytest.fixture
def indexed_rig(monkeypatch, request):
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.setenv("RETRIEVAL_PROFILE", "synthetic")
    return request.getfixturevalue("docrig")


def record(name, data):
    if os.environ.get("WP07_EVIDENCE"):
        p = Path(os.environ["WP07_EVIDENCE"]) / (name + "-" + uuid4().hex[:8] + ".json")
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def application(r, case, **budget):
    settings = Settings(
        tool_mode="local",
        database_url=r.env["DATABASE_URL"],
        app_mode="test",
        retrieval_profile="synthetic",
        operator_id=r.actor,
        operator_token="synthetic-wp07-operator-token-only-0000",
    )
    auth = AuthStore(settings)
    cookie, _ = auth.login("synthetic-wp07-operator-token-only-0000")
    ex = ToolExecutor(r.store.engine, settings)
    ctx = ex.contexts.open(auth, cookie, UUID(case["id"]), **budget)
    return ex, ctx


def call(ex, ctx, name, args, key=None):
    return ex.execute(ctx, name, args, key or uuid4().hex)


def count(r, table):
    with r.store.engine.connect() as c:
        return c.execute(select(func.count()).select_from(table)).scalar_one()


def test_five_tools_demo(indexed_rig):
    r = indexed_rig
    body = document(r)
    case = archived_case(r)
    quote = archived_citation(r, case)
    ev = archived_bind(r, case, quote)
    sid = spec(r, ev)["spec"]["id"]
    assert approve(r, sid).status_code == 200
    ex, ctx = application(r, case, call_limit=12)
    requests = [
        ("search_manuals", dict(query="voltage", vehicle_scope={}, top_k=3)),
        (
            "get_evidence_context",
            dict(
                chunk_id=quote["chunk_id"],
                document_version_id=quote["document_version_id"],
                neighbors=2,
            ),
        ),
        (
            "get_measurement_spec",
            dict(component_key="SYNTHETIC-COMPONENT", quantity="voltage", vehicle_scope={}),
        ),
        (
            "compare_measurement",
            dict(spec_id=sid, value="1000", unit="mV", conditions={"engine": "off"}),
        ),
        ("get_case_observations", dict(at_revision=0)),
    ]
    results = {}
    for name, args in requests:
        result = langchain_tool(ex, ctx, name, name).invoke(args)
        assert result["ok"], (name, result)
        results[name] = result
    assert results["get_case_observations"]["data"]["empty"]
    assert results["compare_measurement"]["data"]["outcome"] == "within_range"
    assert results["get_measurement_spec"]["data"]["candidates"][0]["spec_id"] == sid
    before = count(r, measurement_comparisons)
    again = call(
        ToolExecutor(r.store.engine, ex.settings),
        ctx,
        "compare_measurement",
        requests[3][1],
        "compare_measurement",
    )
    assert again == results["compare_measurement"]
    assert count(r, measurement_comparisons) == before
    # Replay hydrates original chunk references without reinference or counting an attempt.
    assert (
        call(ex, ctx, "search_manuals", requests[0][1], "search_manuals")
        == results["search_manuals"]
    )
    assert (
        call(ex, ctx, "search_manuals", dict(query="different"), "search_manuals")["error"]["code"]
        == "CALL_CONFLICT"
    )
    assert (
        call(ex, replace(ctx, capability="forged"), "get_case_observations", dict(at_revision=0))[
            "error"
        ]["code"]
        == "CONTEXT_INVALID"
    )
    assert (
        call(ex, ctx, "search_manuals", dict(query="x", vehicle_scope={"engine_code": "OTHER"}))[
            "error"
        ]["code"]
        == "SCOPE_CONFLICT"
    )
    assert (
        call(ex, ctx, "search_manuals", dict(query="x", case_id=case["id"]))["error"]["code"]
        == "PARAM_INVALID"
    )
    other = archived_case(r)
    ev2 = archived_bind(r, other, archived_citation(r, other))
    sid2 = spec(r, ev2)["spec"]["id"]
    assert approve(r, sid2).status_code == 200
    assert (
        call(
            ex,
            ctx,
            "compare_measurement",
            dict(spec_id=sid2, value="1", unit="V", conditions={"engine": "off"}),
        )["error"]["code"]
        == "NOT_FOUND"
    )
    with r.store.engine.connect() as c:
        audit = (
            c.execute(select(tool_calls).where(tool_calls.c.execution_id == ctx.execution_id))
            .mappings()
            .all()
        )
        assert all("SYNTHETIC ONLY: voltage" not in json.dumps(x["result_summary"]) for x in audit)
    from test_indexes import reindex

    rebuilt = reindex(r, body).json()
    worker, _ = r.worker(dict(body, run_id=rebuilt["run_id"]), lease=10)
    assert worker.wait(timeout=30) == 0
    pinned = call(ex, ctx, "search_manuals", requests[0][1], "pinned-again")
    assert (
        pinned["ok"]
        and pinned["data"]["chunks"][0]["index_id"] == quote["index_id"] != rebuilt["index_id"]
    )
    limited, capped = application(r, case, call_limit=1)
    empty = call(limited, capped, "get_case_observations", dict(at_revision=0), "first")
    exhausted = call(limited, capped, "get_case_observations", dict(at_revision=0), "second")
    assert empty["data"]["empty"] and exhausted["error"]["code"] == "BUDGET_EXHAUSTED"
    sdk = langchain_tool(ex, ctx, "get_case_observations", "sdk-fixed")
    msg = sdk.invoke(
        dict(
            type="tool_call",
            name="get_case_observations",
            args={"at_revision": 0},
            id="provider-id-1",
        )
    )
    assert msg.tool_call_id == "provider-id-1" and json.loads(msg.content)["ok"]
    invalid = sdk.invoke(dict(at_revision=0, owner="forged"))
    assert json.loads(invalid)["error"]["code"] == "PARAM_INVALID"
    record(
        "demo-limits",
        dict(
            empty=empty,
            exhausted=exhausted,
            frozen_index=pinned["data"]["chunks"][0]["index_id"],
            langchain_tool_message_id=msg.tool_call_id,
        ),
    )
    review(r, body, "revoked")
    assert (
        call(ex, ctx, "compare_measurement", requests[3][1], "compare_measurement")["error"]["code"]
        == "SOURCE_INVALID"
    )
    record(
        "five-tools",
        dict(
            results=results,
            execution_id=ctx.execution_id,
            comparison_replay_preserved=True,
            revoked_call_blocked=True,
            schemas=export_schemas(),
        ),
    )


def test_real_observation_revision_filter(indexed_rig):
    r = indexed_rig
    case = archived_case(r)
    cid = UUID(case["id"])
    area = uuid4()
    step = uuid4()
    a, b, other = uuid4(), uuid4(), uuid4()
    with r.store.engine.begin() as c:
        c.execute(update(cases).where(cases.c.id == cid).values(revision=2))
        c.execute(
            observations.insert().values(
                id=a,
                case_id=cid,
                area_id=area,
                step_id=step,
                kind="measurement",
                payload={"synthetic": True, "value": "1.1", "unit": "V"},
                created_revision=1,
                actor_id=r.actor,
            )
        )
        c.execute(
            observations.insert().values(
                id=b,
                case_id=cid,
                area_id=area,
                step_id=step,
                kind="measurement",
                payload={"synthetic": True, "value": "1.2", "unit": "V"},
                created_revision=2,
                supersedes_id=a,
                actor_id=r.actor,
            )
        )
        c.execute(
            observations.insert().values(
                id=other,
                case_id=cid,
                area_id=uuid4(),
                kind="unavailable",
                payload={"synthetic": True},
                created_revision=2,
                actor_id=r.actor,
            )
        )
    ex, ctx = application(r, case)
    old = call(ex, ctx, "get_case_observations", dict(at_revision=1, area_id=str(area)))
    new = call(ex, ctx, "get_case_observations", dict(at_revision=2, area_id=str(area)))
    assert [x["id"] for x in old["data"]["observations"]] == [str(a)]
    assert [x["id"] for x in new["data"]["observations"]] == [str(b)]
    assert (
        call(ex, ctx, "get_case_observations", dict(at_revision=3))["error"]["code"]
        == "REVISION_INVALID"
    )
    assert call(ex, ctx, "get_case_observations", dict(at_revision=0))["data"]["empty"]
    with r.store.engine.begin() as c:
        c.execute(update(cases).where(cases.c.id == cid).values(revision=3))
    assert (
        call(ex, ctx, "get_case_observations", dict(at_revision=1))["error"]["code"]
        == "REVISION_CONFLICT"
    )
    record("observations", dict(old=old, new=new))


@pytest.mark.parametrize("same_key", [False, True])
def test_atomic_budget_and_logical_concurrency(indexed_rig, monkeypatch, same_key):
    r = indexed_rig
    case = archived_case(r)
    ex, ctx = application(r, case, call_limit=1)
    barrier = Barrier(3)
    entered = Event()
    release = Event()
    real = ex.tools.execute

    def delayed(*a, **k):
        entered.set()
        assert release.wait(5)
        return real(*a, **k)

    monkeypatch.setattr(ex.tools, "execute", delayed)

    def invoke(key):
        barrier.wait()
        return call(ex, ctx, "get_case_observations", dict(at_revision=0), key)

    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(invoke, "one")
        b = pool.submit(invoke, "one" if same_key else "two")
        barrier.wait()
        assert entered.wait(5)
        until = time.monotonic() + 5
        while not (a.done() or b.done()) and time.monotonic() < until:
            time.sleep(0.01)
        assert a.done() or b.done()
        release.set()
        answers = [a.result(), b.result()]
    assert sum(x["ok"] for x in answers) == 1
    failure = next(x for x in answers if not x["ok"])
    assert failure["error"]["code"] == ("CALL_IN_PROGRESS" if same_key else "BUDGET_EXHAUSTED")
    with r.store.engine.connect() as c:
        used = c.execute(
            select(tool_executions.c.used).where(tool_executions.c.id == ctx.execution_id)
        ).scalar_one()
        attempts = (
            c.execute(
                select(tool_calls.c.attempts).where(tool_calls.c.execution_id == ctx.execution_id)
            )
            .scalars()
            .all()
        )
    assert used == 1 and attempts == [1]
    record("budget-race", dict(same_key=same_key, used=used, attempts=attempts, answers=answers))


@pytest.mark.parametrize("failure", ["TOOL_TRANSIENT", "EMBEDDING_UNAVAILABLE", "OUTPUT_INVALID"])
def test_failure_distinction_retry_and_schema(indexed_rig, monkeypatch, failure):
    r = indexed_rig
    case = archived_case(r)
    ex, ctx = application(r, case)
    real = ex.tools.execute
    n = 0

    def injected(*a, **k):
        nonlocal n
        n += 1
        if failure == "OUTPUT_INVALID":
            return {"made_up": True}
        if n == 1 or failure != "TOOL_TRANSIENT":
            raise DomainError(
                failure, "Synthetic error", 503, retryable=failure == "TOOL_TRANSIENT"
            )
        return real(*a, **k)

    monkeypatch.setattr(ex.tools, "execute", injected)
    answer = call(ex, ctx, "get_case_observations", dict(at_revision=0))
    assert answer["ok"] == (failure == "TOOL_TRANSIENT")
    assert n == (2 if failure == "TOOL_TRANSIENT" else 1)
    if not answer["ok"]:
        assert answer["error"]["code"] == failure
    with r.store.engine.connect() as c:
        assert (
            c.execute(
                select(tool_executions.c.used).where(tool_executions.c.id == ctx.execution_id)
            ).scalar_one()
            == n
        )


@pytest.mark.parametrize("mode", ["timeout", "cancel", "late_receipt"])
def test_comparison_publication_is_atomic(indexed_rig, monkeypatch, probe_schema, mode):
    r = indexed_rig
    document(r)
    case = archived_case(r)
    ev = archived_bind(r, case, archived_citation(r, case))
    sid = spec(r, ev)["spec"]["id"]
    assert approve(r, sid).status_code == 200
    ex, ctx = application(r, case, timeout_ms=100 if mode != "cancel" else 3000)
    real = ex.tools.execute
    inserted = Event()
    go = Event()
    before = count(r, measurement_comparisons)

    def delayed(*a, **k):
        result = real(*a, **k)
        inserted.set()
        if mode == "timeout":
            time.sleep(0.15)
        if mode == "cancel":
            assert go.wait(5)
        return result

    monkeypatch.setattr(ex.tools, "execute", delayed)
    trigger = "audit_" + uuid4().hex
    if mode == "late_receipt":
        with r.store.engine.begin() as c:
            c.exec_driver_sql(
                f"CREATE FUNCTION {probe_schema}.delay() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.execution_id='{ctx.execution_id}'::uuid AND NEW.status='succeeded' THEN PERFORM pg_sleep(0.2); END IF; RETURN NEW; END $$"
            )
            c.exec_driver_sql(
                f"CREATE TRIGGER {trigger} AFTER UPDATE ON tool_calls FOR EACH ROW EXECUTE FUNCTION {probe_schema}.delay()"
            )
    try:
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(
                call,
                ex,
                ctx,
                "compare_measurement",
                dict(spec_id=sid, value="1", unit="V", conditions={"engine": "off"}),
                "same",
            )
            if mode == "cancel":
                assert inserted.wait(5)
                assert ex.cancel(ctx, "same")
                go.set()
            answer = future.result(timeout=15)
        assert answer["error"]["code"] == (
            "TOOL_CANCELLED" if mode == "cancel" else "TOOL_TIMEOUT"
        ), answer
        assert count(r, measurement_comparisons) == before
        with r.store.engine.connect() as c:
            row = (
                c.execute(select(tool_calls).where(tool_calls.c.execution_id == ctx.execution_id))
                .mappings()
                .one()
            )
            assert row["status"] == "failed"
            assert (
                c.execute(
                    text("select count(*) from idempotency_keys where key=:key"),
                    {"key": "tool-" + str(row["id"])},
                ).scalar_one()
                == 0
            )
        replayed = call(
            ex,
            ctx,
            "compare_measurement",
            dict(spec_id=sid, value="1", unit="V", conditions={"engine": "off"}),
            "same",
        )
        assert not replayed["ok"] and replayed["error"]["code"] == answer["error"]["code"]
        assert count(r, measurement_comparisons) == before
        record(
            "publication", dict(mode=mode, answer=answer, status=row["status"], comparison_delta=0)
        )
    finally:
        if mode == "late_receipt":
            with r.store.engine.begin() as c:
                c.exec_driver_sql(f"DROP TRIGGER {trigger} ON tool_calls")


@pytest.mark.parametrize("budget", [1, 3])
def test_search_retry_budget_is_persistent(indexed_rig, monkeypatch, budget):
    r = indexed_rig
    case = archived_case(r)
    ex, ctx = application(r, case, call_limit=budget, search_limit=budget)
    attempts = 0

    def transient(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        raise DomainError("TOOL_TRANSIENT", "Synthetic transient", 503, retryable=True)

    monkeypatch.setattr(ex.tools, "execute", transient)
    result = call(ex, ctx, "search_manuals", dict(query="synthetic"), "retry-key")
    assert attempts == min(2, budget)
    assert result["error"]["code"] == ("BUDGET_EXHAUSTED" if budget == 1 else "TOOL_TRANSIENT")
    with r.store.engine.connect() as c:
        row = (
            c.execute(select(tool_executions).where(tool_executions.c.id == ctx.execution_id))
            .mappings()
            .one()
        )
        assert row["used"] == row["search_used"] == attempts
    second = call(ex, ctx, "search_manuals", dict(query="synthetic"), "retry-key")
    assert not second["ok"] and attempts == min(2, budget)
    record("retry-budget", dict(limit=budget, attempts=attempts, result=result))


def test_process_restart_never_repeats_uncertain_call(indexed_rig):
    r = indexed_rig
    case = archived_case(r)
    ex, ctx = application(r, case, timeout_ms=100)
    env = dict(
        r.env,
        WP07_EXECUTION=str(ctx.execution_id),
        WP07_CAPABILITY=ctx.capability,
        WP07_ACTOR=str(r.actor),
    )
    process = subprocess.run(
        [sys.executable, "-B", "tests/wp07_reserve_process.py"],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert process.returncode == 0, "Isolated reservation child failed; do not print credentials"
    time.sleep(0.15)
    restarted = ToolExecutor(r.store.engine, ex.settings)
    answer = call(restarted, ctx, "get_case_observations", dict(at_revision=0), "crashed")
    assert answer["error"]["code"] == "CALL_UNCERTAIN"
    with r.store.engine.connect() as c:
        row = (
            c.execute(select(tool_calls).where(tool_calls.c.execution_id == ctx.execution_id))
            .mappings()
            .one()
        )
        assert row["status"] == "uncertain" and row["attempts"] == 1
    record(
        "process-restart",
        dict(
            child_exit=process.returncode,
            child_pid=int(process.stdout.strip()),
            answer=answer,
            status=row["status"],
        ),
    )


@pytest.mark.parametrize(
    "value,unit,expected",
    [
        ("999.999999999999999999999999", "mV", "out_of_range"),
        ("1000", "mV", "within_range"),
        ("2000.00000000000000000000001", "mV", "out_of_range"),
    ],
)
def test_tool_comparison_matches_wp06(indexed_rig, value, unit, expected):
    r = indexed_rig
    document(r)
    case = archived_case(r)
    ev = archived_bind(r, case, archived_citation(r, case))
    sid = spec(r, ev)["spec"]["id"]
    assert approve(r, sid).status_code == 200
    ex, ctx = application(r, case)
    args = dict(spec_id=sid, value=value, unit=unit, conditions={"engine": "off"})
    via = call(ex, ctx, "compare_measurement", args)
    assert via["ok"] and via["data"]["outcome"] == expected
    from test_evidence_measurement import compare

    direct = compare(r, sid, value=value, unit=unit)
    assert (
        via["data"]["outcome"] == direct["result"]["outcome"]
        and via["data"]["converted"] == direct["result"]["converted"]
    )


def test_real_missing_model_configuration(indexed_rig, tmp_path):
    r = indexed_rig
    document(r)
    case = archived_case(r)
    ex, ctx = application(r, case)
    ex.settings.embedding_path = tmp_path / "missing-local-model"
    result = call(ex, ctx, "search_manuals", dict(query="voltage"))
    assert not result["ok"] and result["error"]["code"] == "EMBEDDING_UNAVAILABLE"
    record("real-config-error", result)


def test_last_budget_slot_pg_wait(indexed_rig):
    from app.services.evidence_scope import owner_lock
    from test_document_ingest import wait

    r = indexed_rig
    case = archived_case(r)
    ex, ctx = application(r, case, call_limit=1)
    blocker = r.store.engine.connect()
    tx = blocker.begin()
    owner_lock(blocker, r.actor)
    pid = blocker.execute(text("select pg_backend_pid()")).scalar_one()
    barrier = Barrier(3)

    def invoke(key):
        barrier.wait()
        return call(ex, ctx, "get_case_observations", dict(at_revision=0), key)

    def waiting():
        with r.store.engine.connect() as c:
            rows = (
                c.execute(
                    text(
                        "select pid,wait_event,clock_timestamp() as at from pg_stat_activity where :pid=ANY(pg_blocking_pids(pid))"
                    ),
                    {"pid": pid},
                )
                .mappings()
                .all()
            )
            return [dict(x) for x in rows] if len(rows) == 2 else None

    try:
        with ThreadPoolExecutor(2) as pool:
            a = pool.submit(invoke, "last-a")
            b = pool.submit(invoke, "last-b")
            barrier.wait()
            observed = wait(waiting)
            tx.commit()
            answers = [a.result(), b.result()]
        assert sum(x["ok"] for x in answers) == 1
        assert next(x for x in answers if not x["ok"])["error"]["code"] == "BUDGET_EXHAUSTED"
        with r.store.engine.connect() as c:
            assert (
                c.execute(
                    select(tool_executions.c.used).where(tool_executions.c.id == ctx.execution_id)
                ).scalar_one()
                == 1
            )
        record("pg-budget-wait", dict(blocker_pid=pid, waits=observed, results=answers))
    finally:
        if tx.is_active:
            tx.rollback()
        blocker.close()


def test_context_allowlist_owner_and_spec_gates(indexed_rig):
    r = indexed_rig
    document(r)
    case = archived_case(r)
    quote = archived_citation(r, case)
    ev = archived_bind(r, case, quote)
    sid = spec(r, ev)["spec"]["id"]
    ex, ctx = application(r, case)
    args = dict(spec_id=sid, value="1", unit="V", conditions={"engine": "off"})
    assert call(ex, ctx, "compare_measurement", args)["error"]["code"] == "SPEC_NOT_APPROVED"
    assert (
        call(
            ex,
            ctx,
            "get_evidence_context",
            dict(chunk_id=str(uuid4()), document_version_id=quote["document_version_id"]),
        )["error"]["code"]
        == "NOT_FOUND"
    )
    assert (
        call(
            ex,
            ctx,
            "get_evidence_context",
            dict(chunk_id=quote["chunk_id"], document_version_id=str(uuid4())),
        )["error"]["code"]
        == "CORPUS_NOT_ALLOWED"
    )
    _, limited = application(r, case, allowlist=["get_case_observations"])
    assert (
        call(ex, limited, "search_manuals", dict(query="voltage"))["error"]["code"]
        == "TOOL_FORBIDDEN"
    )
    assert call(ex, ctx, "not_a_tool", {})["error"]["code"] == "TOOL_UNKNOWN"
    other_settings = ex.settings.model_copy(update={"operator_id": uuid4()})
    other_auth = AuthStore(other_settings)
    cookie, _ = other_auth.login("synthetic-wp07-operator-token-only-0000")
    with pytest.raises(DomainError) as e:
        ex.contexts.open(other_auth, cookie, UUID(case["id"]))
    assert e.value.code == "NOT_FOUND"
    assert (
        call(
            ex,
            replace(ctx, auth=other_auth, cookie=cookie),
            "get_case_observations",
            dict(at_revision=0),
        )["error"]["code"]
        == "CONTEXT_INVALID"
    )
    ctx.auth.revoke(ctx.cookie)
    assert (
        call(ex, ctx, "get_case_observations", dict(at_revision=0))["error"]["code"]
        == "UNAUTHORIZED"
    )
    with r.store.engine.connect() as c:
        assert (
            c.execute(
                select(tool_executions.c.used).where(tool_executions.c.id == ctx.execution_id)
            ).scalar_one()
            == 2
        )


def test_concurrent_comparison_identity(indexed_rig, monkeypatch):
    r = indexed_rig
    document(r)
    case = archived_case(r)
    ev = archived_bind(r, case, archived_citation(r, case))
    sid = spec(r, ev)["spec"]["id"]
    assert approve(r, sid).status_code == 200
    ex, ctx = application(r, case)
    entered, release = Event(), Event()
    real = ex.tools.execute

    def before_transaction(*a, **k):
        entered.set()
        assert release.wait(5)
        return real(*a, **k)

    # Delay before the business side effect, after the durable reservation.
    # Second same-key reserve waits on the owner lock held by the first comparison,
    # then replays its committed receipt; at most one comparison is inserted.
    monkeypatch.setattr(ex.tools, "execute", before_transaction)
    args = dict(spec_id=sid, value="1", unit="V", conditions={"engine": "off"})
    before = count(r, measurement_comparisons)
    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(call, ex, ctx, "compare_measurement", args, "same")
        assert entered.wait(5)
        b = pool.submit(call, ex, ctx, "compare_measurement", args, "same")
        from test_document_ingest import wait

        def blocked():
            with r.store.engine.connect() as c:
                return (
                    c.execute(
                        text(
                            "select count(*) from pg_stat_activity where datname=current_database() and wait_event='advisory' and cardinality(pg_blocking_pids(pid))>0"
                        )
                    ).scalar_one()
                    > 0
                )

        try:
            assert wait(blocked)
        finally:
            release.set()
        answers = [a.result(), b.result()]
    assert all(x["ok"] for x in answers) and answers[0] == answers[1]
    assert count(r, measurement_comparisons) == before + 1
    with r.store.engine.connect() as c:
        assert (
            c.execute(
                select(tool_executions.c.used).where(tool_executions.c.id == ctx.execution_id)
            ).scalar_one()
            == 1
        )
    record("comparison-race", dict(answers=answers, comparison_delta=1, actual_pg_lock_wait=True))
