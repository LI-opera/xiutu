"""WP-04: actual HTTP, isolated PostgreSQL, separately running workers and barriers."""

import json
import os
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import httpx
import pytest
from app.infrastructure.job_store import JobStore
from app.infrastructure.orm import chunks, documents, jobs, runs
from app.infrastructure.orm import document_versions as versions
from sqlalchemy import func, select, text, update

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wp04_fixtures import MARKDOWN, metadata, pdf_bytes

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.database


def wait(fn, seconds=15):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        result = fn()
        if result:
            return result
        time.sleep(0.03)
    raise AssertionError("Bounded WP04 wait expired")


@pytest.fixture
def docrig(database_url, tmp_path):
    class Rig:
        def __init__(self):
            self.store = JobStore(database_url, lease_seconds=2)
            self.processes = []
            self.clients = []
            self.env = dict(
                os.environ,
                DATABASE_URL=str(database_url),
                TEST_DATABASE_URL=str(database_url),
                DATA_PATH=str(tmp_path / "storage"),
                PYTHONPATH=str(ROOT / "backend"),
                PYTHONDONTWRITEBYTECODE="1",
                PYTHONIOENCODING="utf-8",
                UPLOAD_MAX_BYTES="200000",
            )
            self.client, self.headers, self.actor = self.api()

        def api(self):
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            origin = f"http://127.0.0.1:{port}"
            actor = uuid4()
            token = "synthetic-wp04-" + uuid4().hex
            self.operator_token = token  # Private to the isolated test rig; never emit in evidence.
            env = dict(self.env, OPERATOR_TOKEN=token, OPERATOR_ID=str(actor), APP_ORIGIN=origin)
            log = (tmp_path / (str(actor) + ".api.log")).open("x", encoding="utf-8")
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
                    "--log-level",
                    "warning",
                ],
                env=env,
                cwd=ROOT,
                stdout=log,
                stderr=log,
            )
            self.processes.append((proc, log))
            client = httpx.Client(base_url=origin, trust_env=False, timeout=20)
            self.clients.append(client)

            def started():
                assert proc.poll() is None, "Owned API child exited"
                try:
                    return client.get("/api/v2/health/live").status_code == 200
                except (httpx.ConnectError, httpx.ConnectTimeout):
                    return False

            wait(started)
            response = client.post(
                "/api/v2/auth/login", headers={"Origin": origin}, json={"token": token}
            )
            assert response.status_code == 200
            headers = {"Origin": origin, "X-CSRF-Token": response.json()["csrf_token"]}
            assert client.get("/api/v2/health/ready").status_code == 200
            return client, headers, actor

        def upload(
            self,
            data=b"# synthetic\n\nLocal test only.\n",
            name="s.md",
            meta=None,
            key=None,
            client=None,
            headers=None,
        ):
            return (client or self.client).post(
                "/api/v2/documents",
                headers=dict(headers or self.headers, **{"Idempotency-Key": key or uuid4().hex}),
                files={
                    "file": (name, data, "application/octet-stream"),
                    "metadata": (
                        None,
                        json.dumps(meta or metadata(), ensure_ascii=False),
                        "application/json",
                    ),
                },
            )

        def path(self, body):
            return "/api/v2/documents/" + body["document_id"] + "/versions/" + body["version_id"]

        def state(self, body):
            response = self.client.get(self.path(body))
            assert response.status_code == 200
            return response.json()

        def count(self, body):
            with self.store.engine.connect() as c:
                return c.execute(
                    select(func.count())
                    .select_from(chunks)
                    .where(chunks.c.document_version_id == UUID(body["version_id"]))
                ).scalar_one()

        def worker(self, body, **config):
            base = tmp_path / uuid4().hex
            base.with_suffix(".json").write_text(
                json.dumps(dict(run_id=body["run_id"], **config)), encoding="utf-8"
            )
            log = base.with_suffix(".log").open("x", encoding="utf-8")
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    "tests/wp03_worker_process.py",
                    str(base.with_suffix(".json")),
                ],
                env=self.env,
                cwd=ROOT,
                stdout=log,
                stderr=log,
            )
            self.processes.append((proc, log))
            wait(lambda: base.with_suffix(".ready").exists() or proc.poll() is not None)
            assert proc.poll() is None
            return proc, base

        def complete(self, body):
            p, b = self.worker(body)
            assert p.wait(timeout=20) == 0
            assert self.client.get("/api/v2/runs/" + body["run_id"]).json()["status"] == "succeeded"
            return self.state(body)

        def cancel(self, body):
            return self.client.post(
                "/api/v2/runs/" + body["run_id"] + "/cancel",
                headers=dict(self.headers, **{"Idempotency-Key": uuid4().hex}),
            )

    rig = Rig()
    yield rig
    for c in rig.clients:
        c.close()
    for proc, log in rig.processes:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
        log.close()
    rig.store.close()
    # Never print sensitive input; assert it is absent from service output.
    for log in tmp_path.glob("*.api.log"):
        raw = log.read_text(encoding="utf-8")
        assert "synthetic-wp04-" not in raw and "X-CSRF" not in raw


def test_real_http_versions_review_and_locators(docrig):
    r = docrig
    key = uuid4().hex
    response = r.upload(MARKDOWN.encode(), key=key)
    assert response.status_code == 202, response.text
    body = response.json()
    state = r.complete(body)
    assert state["parse_status"] == "review_pending" and state["review_status"] == "pending"
    assert not state["formal_usable"] and state["index_implemented"]
    assert r.client.get(r.path(body) + "/content").content == MARKDOWN.encode()
    output = r.client.get(r.path(body) + "/chunks", params={"limit": 100}).json()
    assert output["items"] and all(c["token_count"] <= 900 for c in output["items"])
    with r.client.stream("GET", "/api/v2/runs/" + body["run_id"] + "/events") as events:
        lines = list(events.iter_lines())
    assert any("run.succeeded" in x for x in lines)
    review = dict(
        decision="approved",
        scope={"model": "合成车型"},
        source_status="unknown",
        license_status="unknown",
        review_note="合成演示人审记录；非真实资料专业审核",
    )
    reviewkey = uuid4().hex
    a = r.client.post(
        r.path(body) + "/review",
        headers=dict(r.headers, **{"Idempotency-Key": reviewkey}),
        json=review,
    )
    assert (
        a.status_code == 200
        and a.json()["index_status"] == "blocked"
        and not a.json()["formal_usable"]
    )
    assert (
        r.client.post(
            r.path(body) + "/review",
            headers=dict(r.headers, **{"Idempotency-Key": reviewkey}),
            json=review,
        ).json()
        == a.json()
    )
    assert len(r.state(body)["review_history"]) == 1
    replay = r.upload(MARKDOWN.encode(), key=key)
    assert replay.status_code == 202 and replay.json() == body
    same = metadata(document_id=body["document_id"])
    duplicate = r.upload(MARKDOWN.encode(), meta=same)
    assert duplicate.status_code == 200 and duplicate.json()["reused"]
    assert r.state(body)["review_status"] == "approved"
    rejected = dict(review, decision="rejected", review_note="Synthetic rejection check")
    reject_response = r.client.post(
        r.path(body) + "/review",
        headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
        json=rejected,
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["index_status"] == "blocked"
    assert r.state(body)["formal_usable"] is False
    assert r.upload(MARKDOWN.encode(), meta=same).status_code == 200
    assert r.state(body)["review_status"] == "rejected"
    changed = dict(same, title="changed metadata")
    assert r.upload(MARKDOWN.encode(), meta=changed).status_code == 409
    second = r.upload(b"# different version\n", meta=same).json()
    assert second["version_id"] != body["version_id"]
    r.complete(second)
    assert r.client.get(r.path(body) + "/content").content == MARKDOWN.encode()
    assert r.upload(b"# other bytes", key=key).status_code == 409
    for kinds, expected in [
        (("text", "text"), "review_pending"),
        (("scan",), "needs_ocr"),
        (("text", "scan"), "needs_ocr"),
    ]:
        raw = pdf_bytes(kinds)
        response = r.upload(raw, "s.pdf")
        assert response.status_code == 202, response.text
        item = response.json()
        snapshot = r.complete(item)
        assert snapshot["parse_status"] == expected
        assert r.client.get(r.path(item) + "/content", params={"page": 1}).content == raw
        if expected == "needs_ocr":
            assert snapshot["page_issues"]
            assert (
                r.client.post(
                    r.path(item) + "/review",
                    headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
                    json=review,
                ).status_code
                == 409
            )
    print(
        json.dumps(
            {
                "check": "HTTP ingest/source/chunks/review/SSE",
                "document": body["document_id"],
                "chunks": r.count(body),
                "no_index": True,
            }
        )
    )


def test_upload_rejections_and_owner(docrig):
    r = docrig
    for value, name, code in [
        (b"x" * 200001, "s.md", 413),
        (b"not a PDF", "fake.pdf", 415),
        (pdf_bytes(encrypted=True), "e.pdf", 415),
        (b"\xff\xfe", "bad.md", 415),
        (b"# x", "../escape.md", 422),
        (b"# x", "s.exe", 415),
    ]:
        assert r.upload(value, name).status_code == code
    first = r.upload().json()
    other, h, actor = r.api()
    assert actor != r.actor
    assert other.get(r.path(first)).status_code == 404
    assert other.get(r.path(first) + "/content").status_code == 404
    assert other.get(r.path(first) + "/chunks").status_code == 404
    assert (
        other.post(
            r.path(first) + "/review",
            headers=dict(h, **{"Idempotency-Key": uuid4().hex}),
            json=dict(
                decision="rejected",
                scope={},
                source_status="unknown",
                license_status="unknown",
                review_note="cross-owner test",
            ),
        ).status_code
        == 404
    )
    assert (
        r.client.get(
            "/api/v2/documents/" + str(uuid4()) + "/versions/" + first["version_id"]
        ).status_code
        == 404
    )
    assert other.get("/api/v2/runs/" + first["run_id"]).status_code == 404
    assert (
        r.upload(
            meta=metadata(document_id=first["document_id"]), client=other, headers=h
        ).status_code
        == 404
    )
    assert other.get("/api/v2/documents").json()["items"] == []
    own2 = r.upload(client=other, headers=h).json()
    assert own2["version_id"] != first["version_id"]
    bad = dict(r.headers, **{"X-CSRF-Token": "wrong"})
    assert r.upload(headers=bad).status_code == 403
    bad = dict(r.headers, Origin="null")
    assert r.upload(headers=bad).status_code == 403
    r.cancel(first)
    assert r.state(first)["parse_status"] == "cancelled" and r.count(first) == 0
    # Cancel the other owner's own task through its authenticated cookie.
    assert (
        other.post(
            "/api/v2/runs/" + own2["run_id"] + "/cancel",
            headers=dict(h, **{"Idempotency-Key": uuid4().hex}),
        ).status_code
        == 202
    )
    with r.store.engine.connect() as c:
        referenced = set(c.execute(select(versions.c.storage_key)).scalars())
    local = set(p.name for p in Path(r.env["DATA_PATH"]).joinpath("documents").glob("*.bin"))
    assert local <= referenced, "Rejected uploads left unreferenced candidates despite healthy DB"


def test_same_hash_real_lock_wait(docrig):
    r = docrig
    original = r.upload().json()
    r.complete(original)
    body = metadata(document_id=original["document_id"])
    barrier = Barrier(3)
    c = r.store.engine.connect()
    transaction = c.begin()
    c.execute(
        select(documents).where(documents.c.id == UUID(original["document_id"])).with_for_update()
    ).one()

    def upload():
        barrier.wait()
        return r.upload(b"# new shared source\n", meta=body)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(upload) for _ in range(2)]
            barrier.wait()

            def blocked():
                with r.store.engine.connect() as inspect:
                    return (
                        inspect.execute(
                            text(
                                "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND pid<>pg_backend_pid()"
                            )
                        ).scalar_one()
                        >= 2
                    )

            wait(blocked)
            transaction.commit()
            results = [f.result(timeout=20) for f in futures]
    finally:
        if transaction.is_active:
            transaction.rollback()
        c.close()
    assert sorted(x.status_code for x in results) == [200, 202]
    assert len({x.json()["version_id"] for x in results}) == 1
    winner = results[0].json()
    r.complete(winner)
    with r.store.engine.connect() as c:
        assert (
            c.execute(
                select(func.count())
                .select_from(versions)
                .where(versions.c.document_id == UUID(original["document_id"]))
            ).scalar_one()
            == 2
        )
        assert (
            c.execute(
                select(func.count())
                .select_from(jobs)
                .where(jobs.c.run_id == UUID(winner["run_id"]))
            ).scalar_one()
            == 1
        )
    print(
        "two HTTP uploads observed simultaneously waiting on same document row lock; one version/job"
    )


@pytest.mark.parametrize("mode", ["cancel", "expired", "crash", "exhausted"])
def test_ingest_fenced_publication_recovery(docrig, mode):
    r = docrig
    body = r.upload(MARKDOWN.encode()).json()
    if mode == "exhausted":
        with r.store.engine.begin() as c:
            c.execute(update(jobs).where(jobs.c.run_id == UUID(body["run_id"])).values(attempt=2))
    proc, base = r.worker(
        body, barrier="before_finish", lease=1, heartbeat=100 if mode == "expired" else 0.15
    )
    wait(lambda: base.with_suffix(".before_finish").exists())
    assert r.state(body)["parse_status"] == "parsing" and r.count(body) == 0
    if mode == "cancel":
        assert r.cancel(body).status_code == 202
        base.with_suffix(".release").write_text("go")
        assert proc.wait(timeout=10) == 0
        assert r.state(body)["parse_status"] == "cancelled" and r.count(body) == 0
        response = r.client.post(
            "/api/v2/runs/" + body["run_id"] + "/retry",
            headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
            json={},
        )
        assert response.status_code == 202, response.text
        body["run_id"] = response.json()["run_id"]
        r.complete(body)
    elif mode == "expired":
        time.sleep(1.2)
        other, b = r.worker(body)
        assert other.wait(timeout=10) == 0
        assert b.with_suffix(".idle").exists() and r.count(body) == 0
        base.with_suffix(".release").write_text("go")
        assert proc.wait(timeout=10) == 0
        assert r.count(body) == 0
        r.complete(body)
    else:
        proc.terminate()
        proc.wait(timeout=10)
        time.sleep(1.2)
        if mode == "exhausted":
            other, b = r.worker(body)
            assert other.wait(timeout=10) == 0
            assert r.state(body)["parse_status"] == "failed" and r.count(body) == 0
            assert (
                r.client.get("/api/v2/runs/" + body["run_id"]).json()["error"]["code"]
                == "ATTEMPTS_EXHAUSTED"
            )
        else:
            r.complete(body)
    if mode != "exhausted":
        total = r.count(body)
        assert total > 0
        again, b = r.worker(body)
        assert again.wait(timeout=10) == 0 and r.count(body) == total
    print(
        json.dumps(
            {
                "mode": mode,
                "worker_pid": proc.pid,
                "chunks": r.count(body),
                "parse_status": r.state(body)["parse_status"],
            }
        )
    )


def test_source_integrity_failure_and_no_partial(docrig):
    r = docrig
    body = r.upload().json()
    with r.store.engine.connect() as c:
        key = c.execute(
            select(versions.c.storage_key).where(versions.c.id == UUID(body["version_id"]))
        ).scalar_one()
    source = Path(r.env["DATA_PATH"]) / "documents" / key
    source.write_bytes(b"synthetic corrupt source")  # only this test-owned fixture
    proc, b = r.worker(body)
    assert proc.wait(timeout=10) == 0
    state = r.state(body)
    assert (
        state["parse_status"] == "failed" and state["parse_error"]["code"] == "SOURCE_UNAVAILABLE"
    )
    assert r.count(body) == 0
    assert r.client.get(r.path(body) + "/content").status_code == 500


def test_upload_transaction_failure_cleans_only_candidate(docrig, probe_schema):
    r = docrig
    title = "synthetic-reject-" + uuid4().hex
    function = probe_schema + ".reject_upload"
    trigger = "wp04_reject_" + uuid4().hex
    with r.store.engine.begin() as c:
        c.execute(
            text(
                f"CREATE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION USING ERRCODE='22000', MESSAGE='synthetic test error'; END $$"
            )
        )
        c.execute(
            text(
                f"CREATE TRIGGER {trigger} BEFORE INSERT ON document_versions FOR EACH ROW WHEN (NEW.metadata_json->>'title'='{title}') EXECUTE FUNCTION {function}()"
            )
        )
    try:
        body = metadata()
        body["title"] = title
        response = r.upload(meta=body)
        assert response.status_code == 500 and response.json()["error"]["retryable"] is False
        assert r.client.get("/api/v2/documents").json()["items"] == []
        with r.store.engine.connect() as c:
            assert (
                c.execute(
                    select(func.count()).select_from(runs).where(runs.c.owner_id == r.actor)
                ).scalar_one()
                == 0
            )
        assert list(Path(r.env["DATA_PATH"]).joinpath("documents").glob("*.bin")) == []
    finally:
        with r.store.engine.begin() as c:
            c.execute(text(f"DROP TRIGGER {trigger} ON document_versions"))


def test_publish_transaction_rollback_no_partial_chunks(docrig, probe_schema):
    r = docrig
    body = r.upload(MARKDOWN.encode()).json()
    function = probe_schema + ".reject_chunk"
    trigger = "wp04_reject_" + uuid4().hex
    with r.store.engine.begin() as c:
        c.execute(
            text(
                f"CREATE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION USING ERRCODE='22000', MESSAGE='synthetic test error'; END $$"
            )
        )
        c.execute(
            text(
                f"CREATE TRIGGER {trigger} BEFORE INSERT ON chunks FOR EACH ROW WHEN (NEW.document_version_id='{body['version_id']}'::uuid AND NEW.ordinal=1) EXECUTE FUNCTION {function}()"
            )
        )
    try:
        proc, b = r.worker(body, lease=1, heartbeat=0.15)
        assert proc.wait(timeout=15) == 0
        assert r.count(body) == 0 and r.state(body)["parse_status"] == "parsing"
        assert r.client.get("/api/v2/runs/" + body["run_id"]).json()["status"] == "running"
    finally:
        with r.store.engine.begin() as c:
            c.execute(text(f"DROP TRIGGER {trigger} ON chunks"))
    time.sleep(1.2)
    r.complete(body)
    assert r.count(body) > 1
    print(
        "real SQL exception on second chunk rolled back all chunks and success; recovery published once"
    )


@pytest.mark.parametrize("stage", ["version_lock", "chunk_sql", "success_event_sql"])
def test_publication_deadline_after_blocking_sql(docrig, probe_schema, stage):
    """Real row/SQL waits must roll back, even after terminal SQL clears the lease."""
    r = docrig
    body = r.upload(b"# Synthetic deadline boundary\n\nRecovery must publish once.\n").json()
    run_id, vid = UUID(body["run_id"]), UUID(body["version_id"])
    proc, base = r.worker(body, barrier="before_finish", lease=2, heartbeat=0.15)
    wait(lambda: base.with_suffix(".before_finish").exists())
    blocker = r.store.engine.connect()
    transaction = blocker.begin()
    blocker_pid = blocker.execute(text("SELECT pg_backend_pid()")).scalar_one()
    trigger = "wp04_deadline_" + uuid4().hex
    table = "chunks" if stage == "chunk_sql" else "run_events"
    installed = False
    evidence = dict(stage=stage, worker_pid=proc.pid, blocker_pid=blocker_pid)
    try:
        if stage == "version_lock":
            blocker.execute(select(versions).where(versions.c.id == vid).with_for_update()).one()
        else:
            # Test-only trigger blocks a real publishing statement, not a mocked clock.
            gate = uuid4().int % (2**63 - 1)
            blocker.execute(text("SELECT pg_advisory_xact_lock(:gate)"), {"gate": gate})
            condition = (
                f"NEW.document_version_id='{vid}'::uuid AND NEW.ordinal=0"
                if stage == "chunk_sql"
                else f"NEW.run_id='{run_id}'::uuid AND NEW.type='run.succeeded'"
            )
            with r.store.engine.begin() as c:
                c.execute(
                    text(
                        f"CREATE FUNCTION {probe_schema}.delay_publication() RETURNS trigger "
                        f"LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_advisory_xact_lock({gate}); "
                        "RETURN NEW; END $$"
                    )
                )
                c.execute(
                    text(
                        f"CREATE TRIGGER {trigger} BEFORE INSERT ON {table} FOR EACH ROW "
                        f"WHEN ({condition}) EXECUTE FUNCTION {probe_schema}.delay_publication()"
                    )
                )
            installed = True
        base.with_suffix(".release").write_text("go", encoding="utf-8")

        def blocked():
            with r.store.engine.connect() as c:
                return (
                    c.execute(
                        text(
                            "SELECT pid,wait_event_type,wait_event,query_start FROM pg_stat_activity "
                            "WHERE :blocker=ANY(pg_blocking_pids(pid))"
                        ),
                        {"blocker": blocker_pid},
                    )
                    .mappings()
                    .first()
                )

        observed = wait(blocked)
        evidence["observed_wait"] = dict(observed)

        def expired():
            with r.store.engine.connect() as c:
                row = (
                    c.execute(
                        text(
                            "SELECT clock_timestamp() AS observed_at,lease_until,lease_token,attempt "
                            "FROM jobs WHERE run_id=:id"
                        ),
                        {"id": run_id},
                    )
                    .mappings()
                    .one()
                )
                return (
                    dict(row)
                    if (row["observed_at"] - row["lease_until"]).total_seconds() > 0.3
                    else None
                )

        before = wait(expired, seconds=6)
        evidence["before_unlock"] = before
        assert r.count(body) == 0  # No uncommitted chunks are visible to another connection.
        transaction.commit()
        assert proc.wait(timeout=10) == 0
        assert r.count(body) == 0
        state = r.state(body)
        assert state["parse_status"] == "parsing" and state["parser_version"] is None
        assert r.client.get("/api/v2/runs/" + str(run_id)).json()["status"] == "running"
        with r.store.engine.connect() as c:
            job = c.execute(select(jobs).where(jobs.c.run_id == run_id)).mappings().one()
            assert job["status"] == "running" and job["lease_until"] == before["lease_until"]
            assert (
                job["lease_token"] == before["lease_token"] and job["attempt"] == before["attempt"]
            )
            assert (
                c.execute(
                    text(
                        "SELECT count(*) FROM run_events WHERE run_id=:id AND type='run.succeeded'"
                    ),
                    {"id": run_id},
                ).scalar_one()
                == 0
            )
        evidence["expired_publication"] = dict(
            chunks=0, parse_status=state["parse_status"], success_events=0
        )
    finally:
        if transaction.is_active:
            transaction.rollback()
        blocker.close()
        if installed:
            with r.store.engine.begin() as c:
                c.execute(text(f"DROP TRIGGER {trigger} ON {table}"))
    # A new real process acquires the released lock and resumes within the same budget.
    r.complete(body)
    total = r.count(body)
    assert total > 0
    with r.store.engine.connect() as c:
        job = c.execute(select(jobs).where(jobs.c.run_id == run_id)).mappings().one()
        assert job["attempt"] == before["attempt"] + 1
        assert job["lease_token"] == before["lease_token"] + 1
        assert (
            c.execute(
                text("SELECT count(*) FROM run_events WHERE run_id=:id AND type='run.succeeded'"),
                {"id": run_id},
            ).scalar_one()
            == 1
        )
    again, _ = r.worker(body)
    assert again.wait(timeout=10) == 0 and r.count(body) == total
    evidence["recovered"] = dict(
        chunks=total, attempt=job["attempt"], token=job["lease_token"], success_events=1
    )
    print(json.dumps(evidence, default=str))
