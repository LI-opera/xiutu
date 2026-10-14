"""WP08: synthetic corpus, real PostgreSQL/E5, separate SDK server and CLI."""

import asyncio
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from app.domain.policies import DomainError
from app.infrastructure.mcp_client import ClientConfig, ManualMCPClient
from app.infrastructure.orm import cases, tool_calls, tool_executions
from app.mcp_server.config import TOOLS, Database, read_config
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError
from test_business_tools import application, call, indexed_rig  # noqa: F401
from test_document_ingest import ROOT, docrig, wait  # noqa: F401
from test_evidence_measurement import (
    approve,
    archived_bind,
    archived_case,
    archived_citation,
    document,
    review,
    spec,
)

sys.path.insert(0, str(ROOT / "scripts"))
from provision_mcp_role import provision

pytestmark = pytest.mark.database


def record(name, data):
    if os.environ.get("WP08_EVIDENCE"):
        (Path(os.environ["WP08_EVIDENCE"]) / (name + "-" + uuid4().hex[:8] + ".json")).write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf8"
        )


@pytest.fixture
def mcp_rig(indexed_rig, tmp_path):  # noqa: F811
    r = indexed_rig
    doc = document(r)
    case = archived_case(r)
    quote = archived_citation(r, case)
    ev = archived_bind(r, case, quote)
    sid = spec(r, ev)["spec"]["id"]
    assert approve(r, sid).status_code == 200
    ex, ctx = application(r, case, call_limit=20, search_limit=10)
    secret = tmp_path / "db-secret.json"
    provision(r.env["DATABASE_URL"], secret)
    db = json.loads(secret.read_text())
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with r.store.engine.connect() as c:
        row = c.execute(select(cases).where(cases.c.id == UUID(case["id"]))).mappings().one()
        binding = dict(
            actor_id=str(r.actor),
            case_id=case["id"],
            revision=row["revision"],
            manifest=row["corpus_manifest"],
            profile="synthetic",
            allowlist=list(TOOLS),
        )
    tokens = ["synthetic-wp08-" + uuid4().hex for _ in range(2)]
    cfg = dict(
        database=db,
        grants=[
            dict(
                binding,
                token_hash=hashlib.sha256(t.encode()).hexdigest(),
                expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            )
            for t in tokens
        ],
        hosts=[f"127.0.0.1:{port}"],
        origins=["http://127.0.0.1:8020"],
        embedding_path=str(ex.settings.embedding_path.absolute()),
        embedding_model_path=str(ex.settings.embedding_model_path)
        if ex.settings.embedding_model_path
        else None,
        data_path=r.env["DATA_PATH"],
        retrieval_profile="synthetic",
    )
    serverfile = tmp_path / "server-secret.json"

    def save():
        serverfile.write_text(json.dumps(cfg), encoding="utf8")

    save()
    files = []
    for i, t in enumerate(tokens):
        f = tmp_path / f"client-{i}-secret.json"
        f.write_text(
            json.dumps(dict(url=f"http://127.0.0.1:{port}/mcp", token=t, binding=binding)),
            encoding="utf8",
        )
        files.append(f)
    env = dict(r.env, MANUAL_MCP_CONFIG=str(serverfile))
    logpath = tmp_path / "mcp-server.log"
    logs = []
    processes = []

    def start():
        log = logpath.open("a", encoding="utf8")
        logs.append(log)
        proc = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                "uvicorn",
                "app.mcp_server.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
                "--log-level",
                "warning",
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=log,
        )
        processes.append(proc)

        def ready():
            assert proc.poll() is None, "Owned MCP server exited"
            try:
                return (
                    httpx.get(f"http://127.0.0.1:{port}/health", trust_env=False).status_code == 200
                )
            except httpx.ConnectError:
                return False

        wait(ready)
        return proc

    proc = start()
    ex.settings.tool_mode = "remote_mcp"
    ex.settings.mcp_client_config = files[0]
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
    ]
    rig = dict(
        r=r,
        doc=doc,
        case=case,
        quote=quote,
        sid=sid,
        ex=ex,
        ctx=ctx,
        db=db,
        cfg=cfg,
        save=save,
        files=files,
        tokens=tokens,
        port=port,
        proc=proc,
        start=start,
        requests=requests,
        tmp=tmp_path,
        log=logpath,
        serverfile=serverfile,
        binding=binding,
    )
    yield rig
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
    for log in logs:
        log.close()
    raw = logpath.read_text(encoding="utf8")
    assert (
        all(t not in raw for t in tokens)
        and db["password"] not in raw
        and ctx.capability not in raw
        and ctx.cookie not in raw
    )
    if os.environ.get("WP08_EVIDENCE"):
        (Path(os.environ["WP08_EVIDENCE"]) / ("server-" + uuid4().hex[:8] + ".log")).write_text(
            raw, encoding="utf8"
        )


def client(m):
    return ManualMCPClient(read_config(m["files"][1], ClientConfig))


def test_real_dual_clients_and_readonly(mcp_rig):
    m = mcp_rig
    results = {}
    for name, args in m["requests"]:
        app = call(m["ex"], m["ctx"], name, args, name)
        assert app["ok"], app
        argfile = m["tmp"] / (name + ".json")
        argfile.write_text(json.dumps(args), encoding="utf8")
        output = m["tmp"] / (name + "-cli.json")
        cli = subprocess.run(
            [
                sys.executable,
                "-B",
                "scripts/probes/manual_mcp_client.py",
                "--config",
                str(m["files"][1]),
                "--tool",
                name,
                "--arguments",
                str(argfile),
                "--output",
                str(output),
            ],
            cwd=ROOT,
            env=m["r"].env,
            capture_output=True,
            text=True,
        )
        assert cli.returncode == 0, cli.stdout + cli.stderr
        other = json.loads(output.read_text(encoding="utf8"))["answer"]
        assert other["data"] == app["data"] and other["provenance"] == app["provenance"]
        assert call(m["ex"], m["ctx"], name, args, name) == app
        results[name] = dict(application=app, cli=other, cli_exit=cli.returncode)

    async def inspect():
        c = client(m)
        await c.connect()
        try:
            names = list(await c.discover())
            rejected = await c.session.call_tool("compare_measurement", {})
            assert (
                rejected.isError and rejected.structuredContent["error"]["code"] == "TOOL_FORBIDDEN"
            )
            return names, c.protocol
        finally:
            await c.close()

    names, protocol = asyncio.run(inspect())
    assert set(names) == set(TOOLS)
    engine = Database.model_validate(m["db"]).engine()
    denied = []
    for query in [
        "DELETE FROM chunks WHERE false",
        "UPDATE cases SET revision=revision WHERE false",
        "CREATE TABLE mcp_must_not_create(x int)",
        "SELECT * FROM tool_calls LIMIT 1",
    ]:
        with pytest.raises(DBAPIError) as exc:
            with engine.begin() as c:
                # Prove actual GRANT restrictions independently of default read-only setting.
                c.execute(text("SET LOCAL transaction_read_only=off"))
                c.execute(text(query))
        denied.append(exc.value.orig.sqlstate)
        assert exc.value.orig.sqlstate == "42501"
    engine.dispose()
    with m["r"].store.engine.connect() as c:
        used = c.execute(
            select(tool_executions.c.used).where(tool_executions.c.id == m["ctx"].execution_id)
        ).scalar_one()
    assert used == 3
    record(
        "dual-clients",
        dict(
            server_pid=m["proc"].pid,
            client_pid=os.getpid(),
            protocol=protocol,
            names=names,
            results=results,
            write_denials=denied,
            used=used,
        ),
    )


def test_auth_scope_and_revocation(mcp_rig):
    m = mcp_rig
    url = f"http://127.0.0.1:{m['port']}/mcp"
    header = {"Authorization": "Bearer " + m["tokens"][1]}
    checks = []
    for extra, status in [
        ({"Authorization": "Bearer wrong"}, 401),
        ({"Origin": "http://evil.invalid"}, 403),
        ({"Origin": "null"}, 403),
        ({"Host": "evil.invalid"}, 403),
        ({"Mcp-Session-Id": "forged"}, 400),
    ]:
        response = httpx.post(url, headers=dict(header, **extra), json={}, trust_env=False)
        assert response.status_code == status
        checks.append([list(extra), status])
    name, args = m["requests"][0]
    for forged in [dict(args, owner=str(uuid4())), dict(args, profile="synthetic")]:
        result = call(m["ex"], m["ctx"], name, forged)
        assert result["error"]["code"] == "PARAM_INVALID"
    result = call(m["ex"], m["ctx"], name, dict(args, vehicle_scope={"engine_code": "OTHER"}))
    assert result["error"]["code"] == "SCOPE_CONFLICT", result
    foreign_client, foreign_headers, _ = m["r"].api()
    foreign = m["r"].upload(client=foreign_client, headers=foreign_headers).json()
    result = call(
        m["ex"],
        m["ctx"],
        "get_evidence_context",
        dict(chunk_id=str(uuid4()), document_version_id=foreign["version_id"], neighbors=0),
    )
    assert result["error"]["code"] == "CORPUS_NOT_ALLOWED"
    # Server binding cannot be overwritten from a model or by a forged client binding.
    original = json.loads(m["files"][0].read_text())
    forged = json.loads(json.dumps(original))
    forged["binding"]["case_id"] = str(uuid4())
    m["files"][0].write_text(json.dumps(forged), encoding="utf8")
    result = call(m["ex"], m["ctx"], name, args)
    assert result["error"]["code"] == "CONTEXT_INVALID"
    m["files"][0].write_text(json.dumps(original), encoding="utf8")
    success = call(m["ex"], m["ctx"], name, args, "before-revoke")
    assert success["ok"]
    assert review(m["r"], m["doc"], "rejected").status_code == 200
    result = call(m["ex"], m["ctx"], name, args, "before-revoke")
    assert not result["ok"]
    with pytest.raises(DomainError) as rejected:
        asyncio.run(client(m).exchange(name, args))
    assert rejected.value.code in ("SOURCE_INVALID", "CORPUS_NOT_ALLOWED")
    m["cfg"]["grants"][1]["expires_at"] = "2000-01-01T00:00:00+00:00"
    m["save"]()
    assert httpx.post(url, headers=header, json={}, trust_env=False).status_code == 401
    record(
        "authorization", dict(checks=checks, revoked_code=rejected.value.code, application=result)
    )


def test_disconnect_retry_budget_and_reinitialize(mcp_rig):
    m = mcp_rig
    name, args = m["requests"][0]
    assert call(m["ex"], m["ctx"], name, args, "initial")["ok"]
    m["proc"].terminate()
    m["proc"].wait(timeout=10)
    failed = call(m["ex"], m["ctx"], name, args, "offline")
    assert not failed["ok"], failed
    with m["r"].store.engine.connect() as c:
        row = (
            c.execute(
                select(tool_calls).where(
                    tool_calls.c.execution_id == m["ctx"].execution_id,
                    tool_calls.c.call_key == "offline",
                )
            )
            .mappings()
            .one()
        )
        used = c.execute(
            select(tool_executions.c.used, tool_executions.c.search_used).where(
                tool_executions.c.id == m["ctx"].execution_id
            )
        ).one()
    assert row["attempts"] == 2 and tuple(used) == (3, 3), (failed, row["attempts"], used)
    restarted = m["start"]()
    assert restarted.pid != m["proc"].pid
    after = call(m["ex"], m["ctx"], name, args, "after-reconnect")
    assert after["ok"], after
    record(
        "reconnect",
        dict(
            error=failed,
            attempts=row["attempts"],
            used=list(used),
            old_pid=m["proc"].pid,
            new_pid=restarted.pid,
            after=after,
        ),
    )


def test_remote_timeout_cancel_and_late_response(mcp_rig):
    m = mcp_rig
    name, args = m["requests"][1]
    # Hold the real shared owner advisory lock AFTER executor reservation, at MCP entry.
    import app.infrastructure.mcp_client as module
    from app.services.evidence_scope import owner_lock

    original = module.remote_call
    from threading import Event

    reserved = Event()
    release = Event()

    def barrier(*a, **kw):
        reserved.set()
        assert release.wait(8)
        return original(*a, **kw)

    from unittest.mock import patch

    with patch.object(module, "remote_call", barrier):
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(call, m["ex"], m["ctx"], name, args, "cancelled")
            assert reserved.wait(5)
            assert m["ex"].cancel(m["ctx"], "cancelled")
            release.set()
            result = future.result(timeout=20)
    assert result["error"]["code"] == "TOOL_CANCELLED", result
    # Real transport timeout via actual DB owner lock while server handles SDK call.
    conn = m["r"].store.engine.connect()
    tx = conn.begin()
    owner_lock(conn, m["r"].actor)
    try:
        with pytest.raises(DomainError) as exc:
            asyncio.run(
                ManualMCPClient(read_config(m["files"][1], ClientConfig), timeout=0.3).exchange(
                    name, args
                )
            )
        assert exc.value.code == "TOOL_TIMEOUT", exc.value.code
    finally:
        tx.rollback()
        conn.close()
    with m["r"].store.engine.connect() as c:
        row = (
            c.execute(
                select(tool_calls).where(
                    tool_calls.c.execution_id == m["ctx"].execution_id,
                    tool_calls.c.call_key == "cancelled",
                )
            )
            .mappings()
            .one()
        )
    assert row["status"] == "failed" and not row["result_summary"]
    record(
        "timeout-cancel",
        dict(cancel=result, transport_timeout=exc.value.code, receipt=row["result_summary"]),
    )


def test_remote_output_is_revalidated_and_frozen(mcp_rig, monkeypatch):
    m = mcp_rig
    name, args = m["requests"][0]
    original = call(m["ex"], m["ctx"], name, args, "original")
    assert original["ok"]
    from test_indexes import reindex

    rebuilt_response = reindex(m["r"], m["doc"])
    assert rebuilt_response.status_code == 202
    rebuilt = rebuilt_response.json()
    # Existing helper returns response body; complete only this test's new worker.
    p, _ = m["r"].worker(dict(m["doc"], run_id=rebuilt["run_id"]), lease=10)
    assert p.wait(timeout=30) == 0
    frozen = call(m["ex"], m["ctx"], name, args, "frozen")
    assert frozen["ok"], frozen
    assert frozen["data"] == original["data"]
    from copy import deepcopy

    import app.infrastructure.mcp_client as module

    bad = deepcopy(original["data"])
    bad["chunks"][0]["text"] = "FORGED REMOTE BODY"
    monkeypatch.setattr(module, "remote_call", lambda *a, **k: bad)
    rejected = call(m["ex"], m["ctx"], name, args, "forged")
    assert rejected["error"]["code"] == "SOURCE_INVALID"
    monkeypatch.setattr(module, "remote_call", lambda *a, **k: dict(empty=False, chunks="bad"))
    invalid = call(m["ex"], m["ctx"], name, args, "schema")
    assert invalid["error"]["code"] == "OUTPUT_INVALID"
    m["ctx"].auth.revoke(m["ctx"].cookie)
    revoked = call(m["ex"], m["ctx"], name, args, "original")
    assert not revoked["ok"]
    record(
        "frozen-and-output", dict(frozen=frozen, forged=rejected, schema=invalid, logout=revoked)
    )


def test_application_deadline_wait_and_no_late_receipt(mcp_rig, monkeypatch):
    m = mcp_rig
    name, args = m["requests"][1]
    from threading import Event

    import app.infrastructure.mcp_client as module
    from app.services.evidence_scope import owner_lock

    original = module.remote_call
    reserved = Event()
    release = Event()

    def barrier(*a, **kw):
        reserved.set()
        assert release.wait(5)
        return original(*a, **kw)

    monkeypatch.setattr(module, "remote_call", barrier)
    with m["r"].store.engine.begin() as c:
        c.execute(
            update(tool_executions)
            .where(tool_executions.c.id == m["ctx"].execution_id)
            .values(timeout_ms=700)
        )
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(call, m["ex"], m["ctx"], name, args, "deadline")
        assert reserved.wait(5)
        lock = m["r"].store.engine.connect()
        tx = lock.begin()
        owner_lock(lock, m["r"].actor)
        try:
            release.set()

            def waiting():
                with m["r"].store.engine.connect() as c:
                    return c.execute(
                        text(
                            "select pid,wait_event_type,wait_event from pg_stat_activity where usename=:role and wait_event_type='Lock'"
                        ),
                        {"role": m["db"]["user"]},
                    ).all()

            observed = wait(waiting, 5)
            time.sleep(0.85)
        finally:
            tx.rollback()
            lock.close()
        answer = future.result(timeout=15)
    assert answer["error"]["code"] == "TOOL_TIMEOUT", answer
    time.sleep(0.2)
    with m["r"].store.engine.connect() as c:
        row = (
            c.execute(
                select(tool_calls).where(
                    tool_calls.c.execution_id == m["ctx"].execution_id,
                    tool_calls.c.call_key == "deadline",
                )
            )
            .mappings()
            .one()
        )
        used = c.execute(
            select(tool_executions.c.used).where(tool_executions.c.id == m["ctx"].execution_id)
        ).scalar_one()
    assert (
        row["attempts"] == 1
        and used == 1
        and row["status"] == "failed"
        and row["result_summary"] == {}
    )
    record(
        "deadline-pg-wait",
        dict(
            observed=[list(x) for x in observed],
            answer=answer,
            status=row["status"],
            attempts=row["attempts"],
            used=used,
            receipt=row["result_summary"],
        ),
    )
