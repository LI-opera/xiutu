"""WP-03 real PostgreSQL, owned subprocesses and observable barriers."""

import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from app.domain.policies import DomainError
from app.domain.schemas import CreateCase
from app.domain.tasks import RetryInput
from app.infrastructure.job_store import JobStore, LeaseLost
from app.infrastructure.orm import jobs, run_events, runs
from app.legacy_case_creation import LegacyCaseService as CaseService
from app.services.run_service import RunService
from app.worker import Worker, runtime_worker
from sqlalchemy import select, text, update

pytestmark = pytest.mark.database
ROOT = Path(__file__).resolve().parents[2]


def wait_for(fn, seconds=12):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = fn()
        if result:
            return result
        time.sleep(0.03)
    raise AssertionError("Bounded test wait expired")


@pytest.fixture
def rig(database_url, tmp_path):
    class Rig:
        def __init__(self):
            self.store = JobStore(database_url, lease_seconds=2)
            self.service = RunService(self.store.engine)
            self.actor = uuid4()
            self.processes = []
            self.ids = []
            self.env = dict(
                os.environ,
                TEST_DATABASE_URL=str(database_url),
                DATABASE_URL=str(database_url),
                PYTHONPATH=str(ROOT / "backend"),
                PYTHONDONTWRITEBYTECODE="1",
                PYTHONIOENCODING="utf-8",
            )

        def submit(self, seconds=0, case_id=None):
            _, body = self.service.submit_no_op(
                self.actor, {"seconds": seconds}, uuid4().hex, case_id, 0 if case_id else None
            )
            identifier = UUID(body["run_id"])
            self.ids.append(identifier)
            return identifier

        def state(self, identifier):
            return self.service.get(self.actor, identifier)

        def job(self, identifier):
            with self.store.engine.connect() as c:
                return dict(
                    c.execute(select(jobs).where(jobs.c.run_id == identifier)).mappings().one()
                )

        def events(self, identifier):
            return self.service.events(self.actor, identifier, 0)[0]

        def start(self, identifier, **config):
            base = tmp_path / uuid4().hex
            control = base.with_suffix(".json")
            control.write_text(json.dumps(dict(run_id=str(identifier), **config)))
            log = base.with_suffix(".log").open("w", encoding="utf-8")
            proc = subprocess.Popen(
                [sys.executable, "-B", str(ROOT / "tests/wp03_worker_process.py"), str(control)],
                env=self.env,
                cwd=ROOT,
                stdout=log,
                stderr=log,
            )
            self.processes.append((proc, log))
            wait_for(lambda: base.with_suffix(".ready").exists() or proc.poll() is not None)
            assert proc.poll() is None, "Worker failed before barrier; inspect isolated log"
            return proc, base

        def stage(self, base, name):
            return wait_for(lambda: base.with_suffix("." + name).exists())

        def done(self, proc):
            assert proc.wait(timeout=15) == 0

    r = Rig()
    yield r
    for proc, log in r.processes:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
        log.close()
    for identifier in r.ids:
        if r.state(identifier)["status"] in {"queued", "running", "cancel_requested"}:
            r.service.cancel(r.actor, identifier, uuid4().hex)
    r.store.close()


def test_runtime_worker_leaves_retired_jobs_untouched(rig, monkeypatch):
    retired = []
    for kind in ("diagnosis", "report", "case_analysis"):
        identifier = rig.submit()
        with rig.store.engine.begin() as c:
            c.execute(
                update(jobs).where(jobs.c.run_id == identifier).values(
                    kind=kind, available_at=text("clock_timestamp() - interval '1 day'")
                )
            )
            c.execute(update(runs).where(runs.c.id == identifier).values(kind=kind))
        retired.append((identifier, rig.job(identifier), rig.events(identifier)))

    # A caller bypassing Worker must still leave the retired queue untouched.
    for identifier, _, _ in retired:
        assert rig.store.claim("direct-default", run_id=identifier) is None
    with pytest.raises(ValueError, match="explicit isolated legacy"):
        rig.store.claim("direct-override", allowed_kinds={"diagnosis"})

    allowed = rig.submit()
    monkeypatch.setattr(
        rig.store, "reconcile_pending",
        lambda: pytest.fail("runtime worker entered legacy checkpoint reconciliation"),
    )
    worker = runtime_worker(rig.store)
    assert worker.once(run_id=retired[0][0]) is False
    assert worker.once() is True
    assert rig.state(allowed)["status"] == "succeeded"
    assert worker.once() is False
    launched = subprocess.run(
        [sys.executable, "-B", "-m", "app.worker", "--once"],
        env=rig.env, cwd=ROOT, capture_output=True, timeout=10, check=False,
    )
    assert launched.returncode == 0, "Launched worker failed in isolated database"
    for identifier, before_job, before_events in retired:
        assert rig.job(identifier) == before_job
        assert rig.events(identifier) == before_events
        assert rig.state(identifier)["status"] == "queued"


def test_two_workers_exact_barrier(rig, tmp_path):
    identifier = rig.submit(1)
    gate = tmp_path / "go"
    a, ba = rig.start(identifier, gate=str(gate), barrier="after_claim")
    b, bb = rig.start(identifier, gate=str(gate), barrier="after_claim")
    gate.write_text("go")
    winner = wait_for(
        lambda: (
            ba
            if ba.with_suffix(".after_claim").exists()
            else bb
            if bb.with_suffix(".after_claim").exists()
            else None
        )
    )
    loser = bb if winner == ba else ba
    rig.stage(loser, "idle")
    assert rig.job(identifier)["attempt"] == 1
    winner.with_suffix(".release").write_text("go")
    rig.done(a)
    rig.done(b)
    types = [x["type"] for x in rig.events(identifier)]
    assert types == ["run.queued", "run.started", "run.succeeded"]
    print(
        json.dumps(dict(check="two_workers", pids=[a.pid, b.pid], winner=winner.name, events=types))
    )


def test_independent_heartbeat_during_long_handler(rig):
    identifier = rig.submit(2.5)
    proc, base = rig.start(identifier, lease=1, heartbeat=0.15)
    rig.stage(base, "executing")
    before = rig.job(identifier)["lease_until"]
    wait_for(lambda: rig.job(identifier)["lease_until"] > before)
    time.sleep(1.2)
    other, _ = rig.start(identifier)
    rig.done(other)
    rig.done(proc)
    assert rig.state(identifier)["status"] == "succeeded"
    assert rig.job(identifier)["attempt"] == 1
    print(json.dumps(dict(check="heartbeat_during_handler", pid=proc.pid, attempt=1)))


@pytest.mark.parametrize("stage,attempt", [("before_claim_commit", 1), ("after_claim", 2)])
def test_process_crash_commit_boundary(rig, stage, attempt):
    identifier = rig.submit()
    proc, base = rig.start(identifier, barrier=stage, lease=1, heartbeat=100)
    rig.stage(base, stage)
    proc.terminate()
    proc.wait(timeout=10)
    time.sleep(1.1)
    fresh, _ = rig.start(identifier)
    rig.done(fresh)
    assert rig.state(identifier)["status"] == "succeeded"
    assert rig.job(identifier)["attempt"] == attempt
    types = [x["type"] for x in rig.events(identifier)]
    assert types.count("run.started") == attempt and types.count("run.succeeded") == 1
    print(
        json.dumps(
            dict(
                check=stage,
                killed_pid=proc.pid,
                recovery_pid=fresh.pid,
                attempt=attempt,
                events=types,
            )
        )
    )


def test_expired_lease_old_session_lock_and_fencing(rig):
    identifier = rig.submit()
    old, base = rig.start(identifier, barrier="before_finish", lease=1, heartbeat=100)
    rig.stage(base, "before_finish")
    old_job = rig.job(identifier)
    time.sleep(1.1)
    contender, cb = rig.start(identifier)
    rig.done(contender)
    rig.stage(cb, "idle")
    assert rig.job(identifier)["attempt"] == 1
    base.with_suffix(".release").write_text("late result")
    rig.done(old)
    assert rig.state(identifier)["status"] == "running"
    assert not any(x["type"] == "run.succeeded" for x in rig.events(identifier))
    current = rig.store.claim("fresh", run_id=identifier)
    assert current.job["lease_token"] > old_job["lease_token"]
    stale = replace(current, job=old_job, worker=old_job["lease_owner"])
    with pytest.raises(LeaseLost):
        rig.store.finish(stale)
    rig.store.finish(current)
    current.close()
    assert rig.state(identifier)["status"] == "succeeded"
    print(
        json.dumps(
            dict(
                check="old_lock_and_fence",
                old_pid=old.pid,
                contender_pid=contender.pid,
                old_token=old_job["lease_token"],
                new_token=current.job["lease_token"],
            )
        )
    )


def test_queued_running_cancel_and_success_order(rig):
    identifier = rig.submit()
    first = rig.service.cancel(rig.actor, identifier, "cancel")
    assert first == rig.service.cancel(rig.actor, identifier, "cancel")
    assert rig.service.cancel(rig.actor, identifier, "again")[0] == 200
    assert rig.store.claim("none", run_id=identifier) is None
    assert [e["type"] for e in rig.events(identifier)] == ["run.queued", "run.cancelled"]
    for mode in ["cancel_first", "finish_first"]:
        identifier = rig.submit()
        proc, base = rig.start(identifier, barrier="before_finish")
        rig.stage(base, "before_finish")
        if mode == "cancel_first":
            assert (
                rig.service.cancel(rig.actor, identifier, uuid4().hex)[1]["status"]
                == "cancel_requested"
            )
        base.with_suffix(".release").write_text("go")
        rig.done(proc)
        expected = "cancelled" if mode == "cancel_first" else "succeeded"
        assert rig.state(identifier)["status"] == expected
        assert rig.service.cancel(rig.actor, identifier, uuid4().hex)[0] == 200
        assert [e["type"] for e in rig.events(identifier)][-1] == "run." + expected
    print("cancel_vs_finish: both serialized commit orders checked")


def test_transient_budget_and_explicit_retry(rig):
    identifier = rig.submit()
    for attempt in range(1, 4):
        p, _ = rig.start(identifier, failure="transient")
        rig.done(p)
        job = rig.job(identifier)
        assert job["attempt"] == attempt
        if attempt < 3:
            assert job["status"] == "queued"
            with rig.store.engine.connect() as c:
                remaining = c.execute(
                    text(
                        "SELECT EXTRACT(EPOCH FROM available_at-clock_timestamp()) FROM jobs WHERE run_id=:id"
                    ),
                    {"id": identifier},
                ).scalar_one()
            assert remaining > (1 if attempt == 1 else 6)
            assert rig.store.claim("too_soon", run_id=identifier) is None
            time.sleep(float(remaining) + 0.05)
    assert rig.state(identifier)["status"] == "failed"
    with pytest.raises(DomainError, match="remaining"):
        rig.service.retry(rig.actor, identifier, RetryInput(), uuid4().hex)
    identifier = rig.submit()
    lease = rig.store.claim("cancel", run_id=identifier)
    rig.service.cancel(rig.actor, identifier, uuid4().hex)
    rig.store.finish(lease)
    lease.close()
    response = rig.service.retry(rig.actor, identifier, RetryInput(), "retry")
    assert response == rig.service.retry(rig.actor, identifier, RetryInput(), "retry")
    child = UUID(response[1]["run_id"])
    rig.ids.append(child)
    assert rig.job(child)["attempt"] == 1
    assert rig.state(child)["parent_run_id"] == str(identifier)
    with pytest.raises(DomainError):
        rig.service.retry(rig.actor, identifier, RetryInput(), "other-key")
    lease = rig.store.claim("child", run_id=child)
    assert lease.job["attempt"] == 2
    rig.store.finish(lease)
    lease.close()
    print("retry: 2/8 second persisted backoff, total 3; explicit child inherited attempt=1")


def test_legacy_worker_rejects_invalid_ingest_and_unknown_kind(rig):
    for kind in ["ingest", "unknown"]:
        identifier = rig.submit()
        with rig.store.engine.begin() as c:
            c.execute(update(jobs).where(jobs.c.run_id == identifier).values(kind=kind))
            c.execute(update(runs).where(runs.c.id == identifier).values(kind=kind))
        assert Worker(rig.store, legacy_execution=True).once(run_id=identifier)
        state = rig.state(identifier)
        assert state["status"] == "failed" and state["error"]["code"] == (
            "INVALID_INGEST_INPUT" if kind == "ingest" else "HANDLER_NOT_IMPLEMENTED"
        )
        assert rig.job(identifier)["attempt"] == 1
        with pytest.raises(DomainError):
            rig.service.retry(rig.actor, identifier, RetryInput(), uuid4().hex)


def test_no_op_atomic_enqueue_and_run_lookup(rig):
    service = CaseService(rig.store.engine, b"synthetic")
    _, case = service.create(
        rig.actor, CreateCase(vehicle={"model": "synthetic"}, fault_description="test"), uuid4().hex
    )
    case_id = UUID(case["id"])
    identifier = rig.submit(case_id=case_id)
    assert service.get(rig.actor, case_id)["active_run"]["id"] == str(identifier)
    with pytest.raises(DomainError):
        rig.submit(case_id=case_id)
    with pytest.raises(DomainError):
        rig.service.submit_no_op(rig.actor, {}, uuid4().hex, case_id, 1)
    rig.service.cancel(rig.actor, identifier, uuid4().hex)
    assert service.get(rig.actor, case_id)["active_run"] is None
    assert service.get(rig.actor, case_id)["revision"] == 0
    with pytest.raises(DomainError) as denied:
        rig.service.get(uuid4(), identifier)
    assert denied.value.status == 404
    with rig.store.engine.begin() as c:
        orphan = c.execute(runs.insert().values(kind="legacy").returning(runs.c.id)).scalar_one()
    with pytest.raises(DomainError) as denied:
        rig.service.get(rig.actor, orphan)
    assert denied.value.status == 404


def test_actual_http_sse_replay_auth_cancel(rig, tmp_path):
    identifier = rig.submit()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    origin = f"http://127.0.0.1:{port}"
    token = "synthetic-" + uuid4().hex
    env = dict(
        rig.env,
        APP_ORIGIN=origin,
        OPERATOR_TOKEN=token,
        OPERATOR_ID=str(rig.actor),
        AUTH_SESSION_SECONDS="20",
    )
    log = (tmp_path / "api.log").open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=log,
    )
    rig.processes.append((proc, log))
    with httpx.Client(base_url=origin, timeout=8) as client:

        def ready():
            assert proc.poll() is None, "Own API process exited"
            try:
                return client.get("/api/v2/health/ready").status_code == 200
            except (httpx.ConnectError, httpx.ConnectTimeout):
                return False

        wait_for(ready)
        assert client.get(f"/api/v2/runs/{identifier}").status_code == 401
        login = client.post("/api/v2/auth/login", headers={"Origin": origin}, json={"token": token})
        assert login.status_code == 200
        headers = {
            "Origin": origin,
            "X-CSRF-Token": login.json()["csrf_token"],
            "Idempotency-Key": uuid4().hex,
        }
        assert client.get(f"/api/v2/runs/{identifier}").json()["status"] == "queued"
        assert (
            client.get(
                f"/api/v2/runs/{identifier}/events", headers={"Last-Event-ID": "bad"}
            ).status_code
            == 400
        )
        assert (
            client.get(
                f"/api/v2/runs/{identifier}/events", headers={"Origin": "https://evil.invalid"}
            ).status_code
            == 403
        )
        url = f"/api/v2/runs/{identifier}/events"
        with client.stream("GET", url) as stream:
            assert stream.status_code == 200
            first = next(line for line in stream.iter_lines() if line.startswith("id: "))
        cursor = int(first[4:])
        p, _ = rig.start(identifier)
        rig.done(p)
        response = client.get(url, headers={"Last-Event-ID": str(cursor)})
        replay = [int(x[4:]) for x in response.text.splitlines() if x.startswith("id: ")]
        assert replay == [e["id"] for e in rig.events(identifier) if e["id"] > cursor]
        assert "run.succeeded" in response.text
        assert client.get(url, headers={"Last-Event-ID": str(replay[-1])}).text == ""
        other = rig.submit()
        assert (
            client.get(
                f"/api/v2/runs/{other}/events", headers={"Last-Event-ID": str(cursor)}
            ).status_code
            == 400
        )
        assert (
            client.post(f"/api/v2/runs/{other}/cancel", headers={"Origin": origin}).status_code
            == 403
        )
        assert (
            client.post(f"/api/v2/runs/{other}/cancel", headers=headers).json()["status"]
            == "cancelled"
        )
        child = client.post(
            f"/api/v2/runs/{other}/retry", headers=headers, json={"expected_revision": None}
        )
        assert child.status_code == 202
        rig.ids.append(UUID(child.json()["run_id"]))
        # An open, idle stream closes after the same cookie is revoked by logout.
        with client.stream("GET", f"/api/v2/runs/{child.json()['run_id']}/events") as stream:
            iterator = stream.iter_lines()
            next(iterator)
            assert client.post("/api/v2/auth/logout", headers=headers).status_code == 200
            list(iterator)
        assert client.get(url).status_code == 401
        assert token not in response.text
    print(
        json.dumps(
            dict(
                check="real_http_sse",
                pid=proc.pid,
                port=port,
                first_id=cursor,
                replay=replay,
                terminal_closed=True,
                revoked_closed=True,
            )
        )
    )


def test_enqueue_event_failure_rolls_back_all(rig, monkeypatch):
    import app.services.run_service as module
    from sqlalchemy import func

    with rig.store.engine.connect() as c:
        before = [c.scalar(select(func.count()).select_from(t)) for t in (runs, jobs, run_events)]

    def fail(*args):
        raise RuntimeError("synthetic precommit fault")

    monkeypatch.setattr(module, "append_event", fail)
    with pytest.raises(RuntimeError):
        rig.submit()
    with rig.store.engine.connect() as c:
        after = [c.scalar(select(func.count()).select_from(t)) for t in (runs, jobs, run_events)]
    assert before == after


def test_event_commit_order_serialized(rig):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from app.infrastructure.event_store import append_event

    identifier = rig.submit()
    first = rig.store.engine.connect()
    tx = first.begin()
    first_id = append_event(first, identifier, "test.first", {})
    entered = threading.Event()

    def second():
        with rig.store.engine.begin() as c:
            pid = c.execute(text("SELECT pg_backend_pid()")).scalar_one()
            second.pid = pid
            entered.set()
            return append_event(c, identifier, "test.second", {})

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(second)
        assert entered.wait(5)

        def blocked():
            with rig.store.engine.connect() as c:
                return c.execute(
                    text("SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=:pid"),
                    {"pid": second.pid},
                ).scalar_one()

        try:
            wait_for(blocked)
            assert not future.done()
            # First event is still invisible to independent readers.
            assert first_id not in [e["id"] for e in rig.events(identifier)]
        finally:
            tx.commit()
            first.close()
        second_id = future.result(timeout=5)
    assert second_id > first_id
    assert [e["id"] for e in rig.events(identifier)][-2:] == [first_id, second_id]
    print(
        json.dumps(
            dict(
                check="event_commit_order",
                first=first_id,
                second=second_id,
                observed_lock_wait=True,
            )
        )
    )


def test_cancel_recovered_after_crash_and_attempts_exhausted(rig):
    identifier = rig.submit()
    p, b = rig.start(identifier, barrier="before_finish", lease=1, heartbeat=100)
    rig.stage(b, "before_finish")
    rig.service.cancel(rig.actor, identifier, uuid4().hex)
    p.terminate()
    p.wait(timeout=10)
    time.sleep(1.1)
    recover, _ = rig.start(identifier)
    rig.done(recover)
    assert rig.state(identifier)["status"] == "cancelled"
    identifier = rig.submit()
    for i in range(3):
        lease = rig.store.claim("crash", run_id=identifier)
        assert lease.job["attempt"] == i + 1
        # Fault fixture expires only this new task, simulating a dead worker lease.
        lease.close()
        with rig.store.engine.begin() as c:
            c.execute(
                update(jobs)
                .where(jobs.c.run_id == identifier)
                .values(lease_until=text("clock_timestamp()-interval '1 second'"))
            )
    assert rig.store.claim("fourth", run_id=identifier) is None
    assert rig.state(identifier)["error"]["code"] == "ATTEMPTS_EXHAUSTED"
    assert rig.job(identifier)["attempt"] == 3


def test_sse_heartbeat_expiry_and_cross_owner(rig, tmp_path):
    identifier = rig.submit()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    origin = f"http://127.0.0.1:{port}"
    token = "synthetic-" + uuid4().hex
    env = dict(
        rig.env,
        APP_ORIGIN=origin,
        OPERATOR_TOKEN=token,
        OPERATOR_ID=str(rig.actor),
        AUTH_SESSION_SECONDS="17",
    )
    log = (tmp_path / "expiry-api.log").open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=log,
    )
    rig.processes.append((proc, log))
    with httpx.Client(base_url=origin, timeout=20) as client:

        def ready():
            assert proc.poll() is None
            try:
                return client.get("/api/v2/health/ready").status_code == 200
            except (httpx.ConnectError, httpx.ConnectTimeout):
                return False

        wait_for(ready)
        login = client.post("/api/v2/auth/login", headers={"Origin": origin}, json={"token": token})
        assert login.status_code == 200
        alien = uuid4()
        _, body = rig.service.submit_no_op(alien, {}, uuid4().hex)
        alien_id = UUID(body["run_id"])
        headers = {
            "Origin": origin,
            "X-CSRF-Token": login.json()["csrf_token"],
            "Idempotency-Key": uuid4().hex,
        }
        for suffix, method in [
            ("", "get"),
            ("/events", "get"),
            ("/cancel", "post"),
            ("/retry", "post"),
        ]:
            args = {"headers": headers}
            if suffix == "/retry":
                args["json"] = {}
            assert (
                getattr(client, method)(f"/api/v2/runs/{alien_id}" + suffix, **args).status_code
                == 404
            )
        rig.service.cancel(alien, alien_id, uuid4().hex)
        started = time.monotonic()
        with client.stream("GET", f"/api/v2/runs/{identifier}/events") as response:
            lines = list(response.iter_lines())
        elapsed = time.monotonic() - started
        assert ": heartbeat" in lines and 15 <= elapsed < 20
        assert client.get(f"/api/v2/runs/{identifier}").status_code == 401
        assert token not in "\n".join(lines)
        print(
            json.dumps(
                dict(
                    check="SSE_15s_heartbeat_and_expiry",
                    elapsed=elapsed,
                    pid=proc.pid,
                    cross_owner_404=True,
                )
            )
        )


def test_disconnected_lock_session_cannot_publish(rig):
    from sqlalchemy.exc import SQLAlchemyError

    identifier = rig.submit()
    lease = rig.store.claim("own-lock-session", run_id=identifier)
    # Close ONLY the physical connection created by this test, not the database service.
    lease.connection.connection.driver_connection.close()
    with pytest.raises((SQLAlchemyError, LeaseLost)):
        rig.store.heartbeat(lease)
    assert lease.lost
    with pytest.raises((SQLAlchemyError, LeaseLost)):
        rig.store.finish(lease)
    lease.close()
    assert rig.state(identifier)["status"] == "running"
    assert not any(e["type"] == "run.succeeded" for e in rig.events(identifier))
    time.sleep(2.1)
    fresh, _ = rig.start(identifier)
    rig.done(fresh)
    assert rig.state(identifier)["status"] == "succeeded"
    assert rig.job(identifier)["attempt"] == 2
    print("own lock connection closed: no reconnect/publish; recovered with new token")
