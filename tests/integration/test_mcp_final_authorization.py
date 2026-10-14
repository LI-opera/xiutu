"""Final grant checks after actual PostgreSQL waits, using the real SDK service."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from app.infrastructure.orm import tool_calls, tool_executions
from app.services.evidence_scope import owner_lock
from sqlalchemy import select, text
from test_manual_mcp import call, docrig, indexed_rig, mcp_rig, record, wait  # noqa: F401

pytestmark = pytest.mark.database


@pytest.mark.parametrize(
    "window,change,expected",
    [
        ("owner_lock", "revoke", "MCP_UNAUTHORIZED"),
        ("owner_lock", "expire", "MCP_UNAUTHORIZED"),
        ("owner_lock", "allowlist", "CONTEXT_STALE"),
        ("owner_lock", "binding", "CONTEXT_STALE"),
        ("source_sql", "revoke", "MCP_UNAUTHORIZED"),
    ],
)
def test_final_grant_after_database_wait(mcp_rig, window, change, expected):  # noqa: F811
    m = mcp_rig
    from test_document_ingest import ROOT

    m["proc"].terminate()
    m["proc"].wait(timeout=10)
    gate = m["tmp"] / "gate"
    gate.mkdir()
    env = dict(
        m["r"].env,
        WP08_GATE=str(gate),
        WP08_WINDOW=window,
        MANUAL_MCP_CONFIG=str(m["serverfile"]),
        PYTHONPATH=str(ROOT / "tests") + os.pathsep + str(ROOT / "backend"),
    )
    logpath = m["tmp"] / "grant-server.log"
    log = logpath.open("x", encoding="utf8")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-m",
            "uvicorn",
            "wp08_mcp_process:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(m["port"]),
            "--no-access-log",
            "--log-level",
            "warning",
        ],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=log,
    )

    def ready():
        assert proc.poll() is None, "Owned test server exited"
        try:
            return (
                httpx.get(f"http://127.0.0.1:{m['port']}/health", trust_env=False).status_code
                == 200
            )
        except httpx.ConnectError:
            return False

    try:
        wait(ready)
        if change == "expire":
            expiry = datetime.now(timezone.utc) + timedelta(seconds=3)
            m["cfg"]["grants"][0]["expires_at"] = expiry.isoformat()
            m["save"]()
        name, args = m["requests"][1]
        key = "final-" + window + "-" + change
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(call, m["ex"], m["ctx"], name, args, key)
            wait(lambda: (gate / "ready").exists(), 8)
            lock = m["r"].store.engine.connect()
            tx = lock.begin()
            blocker = lock.execute(text("select pg_backend_pid()")).scalar_one()
            if window == "owner_lock":
                owner_lock(lock, m["r"].actor)
            else:
                lock.execute(text("LOCK TABLE chunks IN ACCESS EXCLUSIVE MODE"))
            try:
                (gate / "go").write_text("release", encoding="utf8")

                def waiting():
                    with m["r"].store.engine.connect() as c:
                        return (
                            c.execute(
                                text(
                                    "select pid,wait_event_type,wait_event,clock_timestamp() as observed_at,"
                                    "pg_blocking_pids(pid) as blockers,query from pg_stat_activity "
                                    "where usename=:role and wait_event_type='Lock'"
                                ),
                                {"role": m["db"]["user"]},
                            )
                            .mappings()
                            .all()
                        )

                observed = wait(waiting, 5)
                assert any(blocker in x["blockers"] for x in observed)
                if window == "source_sql":
                    assert any(
                        x["wait_event"] == "relation" and "chunks" in x["query"] for x in observed
                    )
                else:
                    assert any(x["wait_event"] == "advisory" for x in observed)
                if change == "revoke":
                    m["cfg"]["grants"] = m["cfg"]["grants"][1:]
                    m["save"]()
                elif change == "allowlist":
                    m["cfg"]["grants"][0]["allowlist"] = [
                        tool for tool in m["cfg"]["grants"][0]["allowlist"] if tool != name
                    ]
                    m["save"]()
                elif change == "binding":
                    m["cfg"]["grants"][0]["revision"] += 1
                    m["save"]()
                else:
                    assert all(x["observed_at"] < expiry for x in observed)
                    # The MCP service uses its process wall clock, while the
                    # lock evidence uses PostgreSQL clock_timestamp(). These
                    # clocks can drift in either direction, so keep the lock
                    # held until both have passed the grant deadline.
                    def expired_in_both_clocks():
                        with m["r"].store.engine.connect() as probe:
                            database_now = probe.execute(text("select clock_timestamp()")) \
                                .scalar_one()
                        return database_now >= expiry and datetime.now(timezone.utc) >= expiry

                    wait(expired_in_both_clocks, 5)
                with m["r"].store.engine.connect() as c:
                    changed_at = c.execute(text("select clock_timestamp()")).scalar_one()
                if change == "expire":
                    assert changed_at >= expiry
            finally:
                tx.rollback()
                lock.close()
            answer = future.result(timeout=15)
        assert not answer["ok"] and answer["data"] is None and not answer["provenance"]
        assert answer["error"]["code"] == expected and not answer["error"]["retryable"]
        with m["r"].store.engine.connect() as c:
            row = (
                c.execute(
                    select(tool_calls).where(
                        tool_calls.c.execution_id == m["ctx"].execution_id,
                        tool_calls.c.call_key == key,
                    )
                )
                .mappings()
                .one()
            )
            usage = c.execute(
                select(tool_executions.c.used, tool_executions.c.search_used).where(
                    tool_executions.c.id == m["ctx"].execution_id
                )
            ).one()
        assert row["status"] == "failed" and row["attempts"] == 1 and row["result_summary"] == {}
        assert tuple(usage) == (1, 0)
        # Failed identity stays failed without contacting MCP or adding another attempt.
        replay = call(m["ex"], m["ctx"], name, args, key)
        assert replay["error"]["code"] == expected
        # Switch to independently valid credential and a NEW logical key; no failed-call rewrite.
        cfg = json.loads(m["files"][0].read_text(encoding="utf8"))
        cfg["token"] = m["tokens"][1]
        m["files"][0].write_text(json.dumps(cfg), encoding="utf8")
        success = call(m["ex"], m["ctx"], name, args, key + "-fresh")
        assert success["ok"] and not success["data"]["empty"]
        with m["r"].store.engine.connect() as c:
            final_used = c.execute(
                select(tool_executions.c.used).where(tool_executions.c.id == m["ctx"].execution_id)
            ).scalar_one()
            attempts = c.execute(
                select(tool_calls.c.attempts).where(tool_calls.c.id == row["id"])
            ).scalar_one()
        assert final_used == 2 and attempts == 1
        record(
            "final-grant-" + window + "-" + change,
            dict(
                observed=[dict(x) for x in observed],
                blocker_pid=blocker,
                changed_at=changed_at,
                expiry=expiry if change == "expire" else None,
                answer=answer,
                failed_status=row["status"],
                failed_receipt=row["result_summary"],
                failed_attempts=attempts,
                used_before_fresh=list(usage),
                used_after_fresh=final_used,
                fresh=success,
                server_pid=proc.pid,
            ),
        )
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
        log.close()
        raw = logpath.read_text(encoding="utf8")
        assert all(
            s not in raw
            for s in [*m["tokens"], m["db"]["password"], m["ctx"].cookie, m["ctx"].capability]
        )
