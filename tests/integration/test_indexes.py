"""Real HTTP + real E5 ONNX + PostgreSQL + independent worker processes."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from app.infrastructure.job_store import JobStore
from app.infrastructure.orm import chunk_embeddings, index_versions, jobs, run_events
from app.infrastructure.orm import document_versions as versions
from app.worker import runtime_worker
from sqlalchemy import select, text
from test_document_ingest import docrig, wait  # noqa: F401

pytestmark = pytest.mark.database


@pytest.fixture
def indexed_rig(monkeypatch, request):
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.setenv("RETRIEVAL_PROFILE", "synthetic")
    return request.getfixturevalue("docrig")


def review(r, body, decision="approved", scope=None):
    return r.client.post(
        r.path(body) + "/review",
        headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
        json=dict(
            decision=decision,
            scope=scope or {},
            source_status="unknown",
            license_status="unknown",
            review_note="Synthetic technical fixture, not repair approval",
        ),
    )


def build(r):
    body = r.upload(
        """# 合成测试

P0301 第一缸失火，检查点火线圈。

## 冷却
冷却液不足可导致水温升高。
""".encode()
    ).json()
    r.complete(body)
    approved = review(r, body)
    assert approved.status_code == 202, approved.text
    run = dict(body, run_id=approved.json()["index_run_id"])
    p, b = r.worker(run, lease=10)
    assert p.wait(timeout=30) == 0
    state = r.state(body)
    assert state["index_status"] == "ready", state
    assert not state["formal_usable"] and state["active_index_id"]
    return body, state["active_index_id"]


def reindex(r, body, key=None):
    return r.client.post(
        r.path(body) + "/reindex",
        headers=dict(r.headers, **{"Idempotency-Key": key or uuid4().hex}),
        json={"config_version": "e5-small-onnx-v1"},
    )


def search(r, query="一缸点火不正常", scope=None, client=None, headers=None):
    return (client or r.client).post(
        "/api/v2/evidence/search",
        headers=headers or r.headers,
        json=dict(query=query, vehicle_scope=scope or {}, top_k=5),
    )


def report(name, body):
    directory = os.environ.get("WP05_EVIDENCE")
    if directory:
        p = Path(directory) / (name + "-" + uuid4().hex[:8] + ".json")
        p.write_text(json.dumps(body, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def test_runtime_worker_keeps_document_ingest_and_index(
    indexed_rig, database_url, tmp_path, monkeypatch
):
    r = indexed_rig
    monkeypatch.setenv("DATA_PATH", str(tmp_path / "storage"))
    uploaded = r.upload(b"# Synthetic reference\n\nP0301 ignition inspection.\n")
    assert uploaded.status_code == 202, uploaded.text
    body = uploaded.json()
    store = JobStore(database_url)
    try:
        worker = runtime_worker(store)
        assert worker.once(run_id=UUID(body["run_id"]))
        assert r.state(body)["parse_status"] == "review_pending"
        approved = review(r, body)
        assert approved.status_code == 202, approved.text
        assert worker.once(run_id=UUID(approved.json()["index_run_id"]))
        assert r.state(body)["index_status"] == "ready"
    finally:
        store.close()


def test_real_index_http_and_gates(indexed_rig):
    r = indexed_rig
    assert search(r).json()["chunks"] == []
    body, old = build(r)
    found = search(r, "P0301")
    assert found.status_code == 200, found.text
    result = found.json()
    assert result["chunks"] and all(x["index_id"] == old for x in result["chunks"])
    assert result["chunks"][0]["applicability"]["status"] == "unknown"
    assert r.client.get(r.path(body) + "/content").status_code == 200
    other, headers, _ = r.api()
    assert search(r, client=other, headers=headers).json()["chunks"] == []
    assert (
        other.post(
            r.path(body) + "/reindex",
            headers=dict(headers, **{"Idempotency-Key": uuid4().hex}),
            json={},
        ).status_code
        == 404
    )
    changed = review(r, body, scope={"engine_code": "AAA"})
    assert changed.status_code == 202
    assert search(r, scope={"engine_code": "BBB"}).json()["chunks"] == []
    assert search(r, scope={"engine_code": "AAA"}).json()["chunks"]
    assert review(r, body, "revoked").status_code == 200
    assert search(r).json()["chunks"] == []
    report("http-index-gates", result)


def test_formal_profile_excludes_synthetic(request):
    r = request.getfixturevalue("docrig")
    body = r.upload().json()
    r.complete(body)
    assert review(r, body).status_code == 200
    response = search(r)
    assert response.status_code == 200
    assert response.json()["chunks"] == []
    assert response.json()["excluded"][0]["reason"] == "synthetic"
    assert reindex(r, body).status_code == 409


def test_concurrent_reindex_has_single_generation(indexed_rig):
    r = indexed_rig
    body, old = build(r)
    blocker = r.store.engine.connect()
    tx = blocker.begin()
    blocker.execute(
        select(versions).where(versions.c.id == UUID(body["version_id"])).with_for_update()
    ).one()
    gate = Barrier(3)

    def call():
        gate.wait()
        return reindex(r, body)

    try:
        with ThreadPoolExecutor(2) as pool:
            a, b = pool.submit(call), pool.submit(call)
            gate.wait()

            def blocked():
                with r.store.engine.connect() as c:
                    return (
                        c.execute(
                            text(
                                "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock'"
                            )
                        ).scalar_one()
                        >= 2
                    )

            wait(blocked)
            tx.commit()
            results = [a.result(), b.result()]
    finally:
        if tx.is_active:
            tx.rollback()
        blocker.close()
    assert sorted(x.status_code for x in results) == [202, 409]
    assert r.state(body)["active_index_id"] == old
    report(
        "concurrent-reindex",
        dict(statuses=[x.status_code for x in results], observed_lock_wait=True),
    )


@pytest.mark.parametrize("fault", ["kill", "lease", "cancel", "revoke"])
def test_old_index_survives_fenced_build_and_recovery(indexed_rig, fault):
    r = indexed_rig
    body, old = build(r)
    response = reindex(r, body)
    assert response.status_code == 202
    created = response.json()
    run = dict(body, run_id=created["run_id"])
    p, base = r.worker(
        run, barrier="before_finish", lease=4, heartbeat=30 if fault == "lease" else 0.3
    )
    wait(lambda: base.with_suffix(".before_finish").exists(), 30)
    with r.store.engine.connect() as c:
        staged = c.execute(
            select(chunk_embeddings.c.chunk_id).where(
                chunk_embeddings.c.index_id == UUID(created["index_id"])
            )
        ).all()
    assert staged and r.state(body)["active_index_id"] == old
    assert search(r).json()["chunks"][0]["index_id"] == old
    if fault == "kill":
        p.terminate()
        p.wait(timeout=10)
    elif fault == "cancel":
        assert r.cancel(run).status_code == 202
    elif fault == "revoke":
        assert review(r, body, "revoked").status_code == 200

    def expired():
        with r.store.engine.connect() as c:
            return c.execute(
                select(jobs.c.lease_until < text("clock_timestamp()")).where(
                    jobs.c.run_id == UUID(run["run_id"])
                )
            ).scalar_one()

    if fault in {"kill", "lease"}:
        wait(expired, 10)
    if fault != "kill":
        base.with_suffix(".release").touch()
        assert p.wait(timeout=20) == 0
    assert r.state(body)["active_index_id"] == old
    with r.store.engine.connect() as c:
        assert not c.execute(
            select(run_events.c.id).where(
                run_events.c.run_id == UUID(run["run_id"]), run_events.c.type == "run.succeeded"
            )
        ).first()
    if fault in {"kill", "lease"}:
        recovered, b = r.worker(run, lease=10)
        assert recovered.wait(timeout=30) == 0
        assert r.state(body)["active_index_id"] == created["index_id"]
        with r.store.engine.connect() as c:
            idx = (
                c.execute(
                    select(index_versions).where(index_versions.c.id == UUID(created["index_id"]))
                )
                .mappings()
                .one()
            )
            vectors = c.execute(
                select(chunk_embeddings.c.chunk_id).where(chunk_embeddings.c.index_id == idx["id"])
            ).all()
            assert len(vectors) == idx["chunk_count"] == len(set(x[0] for x in vectors))
            assert (
                len(
                    c.execute(
                        select(run_events.c.id).where(
                            run_events.c.run_id == UUID(run["run_id"]),
                            run_events.c.type == "run.succeeded",
                        )
                    ).all()
                )
                == 1
            )
    else:
        with r.store.engine.connect() as c:
            assert (
                c.execute(
                    select(index_versions.c.status).where(
                        index_versions.c.id == UUID(created["index_id"])
                    )
                ).scalar_one()
                == "failed"
            )
    report(
        "index-recovery",
        dict(
            fault=fault,
            old_index=old,
            new_index=created["index_id"],
            staged_count=len(staged),
            worker_pid=p.pid,
            final_active=r.state(body)["active_index_id"],
        ),
    )


def test_partial_batch_interruption(indexed_rig):
    r = indexed_rig
    content = "\n\n".join(
        f"合成段落{i}：P0301 失火概念，内容仅用于索引恢复测试。" for i in range(20)
    ).encode()
    body = r.upload(content).json()
    r.complete(body)
    approved = review(r, body)
    assert approved.status_code == 202
    initial = dict(body, run_id=approved.json()["index_run_id"])
    p, _ = r.worker(initial, lease=10)
    assert p.wait(timeout=30) == 0
    old = r.state(body)["active_index_id"]
    new = reindex(r, body).json()
    run = dict(body, run_id=new["run_id"])
    p, b = r.worker(run, barrier="after_index_batch", lease=4)
    wait(lambda: b.with_suffix(".after_index_batch").exists(), 30)
    with r.store.engine.connect() as c:
        idx = (
            c.execute(select(index_versions).where(index_versions.c.id == UUID(new["index_id"])))
            .mappings()
            .one()
        )
        partial = len(
            c.execute(
                select(chunk_embeddings.c.chunk_id).where(chunk_embeddings.c.index_id == idx["id"])
            ).all()
        )
    assert partial == 8 < idx["chunk_count"]
    assert search(r).json()["chunks"][0]["index_id"] == old
    p.terminate()
    p.wait(timeout=10)

    def expired():
        with r.store.engine.connect() as c:
            return c.execute(
                select(jobs.c.lease_until < text("clock_timestamp()")).where(
                    jobs.c.run_id == UUID(run["run_id"])
                )
            ).scalar_one()

    wait(expired, 10)
    recovered, _ = r.worker(run, lease=10)
    assert recovered.wait(timeout=30) == 0
    assert r.state(body)["active_index_id"] == new["index_id"]
    with r.store.engine.connect() as c:
        complete = c.execute(
            select(chunk_embeddings.c.chunk_id).where(chunk_embeddings.c.index_id == idx["id"])
        ).all()
        assert len(complete) == idx["chunk_count"] == len(set(x[0] for x in complete))
    report(
        "partial-batch",
        dict(
            old=old,
            new=new,
            partial=partial,
            total=len(complete),
            killed_pid=p.pid,
            recovered_pid=recovered.pid,
        ),
    )


def test_index_activation_lock_window(indexed_rig):
    r = indexed_rig
    body, old = build(r)
    new = reindex(r, body).json()
    run = dict(body, run_id=new["run_id"])
    p, b = r.worker(run, barrier="before_finish", lease=4)
    wait(lambda: b.with_suffix(".before_finish").exists(), 30)
    blocker = r.store.engine.connect()
    tx = blocker.begin()
    blocker_pid = blocker.execute(text("SELECT pg_backend_pid()")).scalar_one()
    blocker.execute(
        select(versions).where(versions.c.id == UUID(body["version_id"])).with_for_update()
    ).one()
    b.with_suffix(".release").touch()
    try:

        def blocked():
            with r.store.engine.connect() as c:
                return (
                    c.execute(
                        text(
                            "SELECT pid,wait_event_type,wait_event FROM pg_stat_activity WHERE :p=ANY(pg_blocking_pids(pid))"
                        ),
                        {"p": blocker_pid},
                    )
                    .mappings()
                    .first()
                )

        observed = dict(wait(blocked))

        def expired():
            with r.store.engine.connect() as c:
                row = (
                    c.execute(
                        text(
                            "SELECT clock_timestamp() AS now,lease_until FROM jobs WHERE run_id=:r"
                        ),
                        {"r": UUID(run["run_id"])},
                    )
                    .mappings()
                    .one()
                )
                return dict(row) if row["now"] > row["lease_until"] else None

        deadline = wait(expired, 8)
        tx.commit()
        assert p.wait(timeout=15) == 0
        assert r.state(body)["active_index_id"] == old
        with r.store.engine.connect() as c:
            assert (
                c.execute(
                    select(index_versions.c.status).where(
                        index_versions.c.id == UUID(new["index_id"])
                    )
                ).scalar_one()
                == "building"
            )
            assert not c.execute(
                select(run_events.c.id).where(
                    run_events.c.run_id == UUID(run["run_id"]), run_events.c.type == "run.succeeded"
                )
            ).first()
    finally:
        if tx.is_active:
            tx.rollback()
        blocker.close()
    recovered, _ = r.worker(run, lease=10)
    assert recovered.wait(timeout=30) == 0
    assert r.state(body)["active_index_id"] == new["index_id"]
    report(
        "activation-lock-window",
        dict(
            observed_wait=observed,
            deadline=deadline,
            old=old,
            new=new,
            worker_pid=p.pid,
            recovered_pid=recovered.pid,
        ),
    )


def test_missing_model_is_503_not_baseline(indexed_rig, tmp_path, database_url):
    from app.config import Settings
    from app.main import create_app
    from fastapi.testclient import TestClient

    r = indexed_rig
    build(r)
    token = "synthetic-only-" + uuid4().hex
    settings = Settings(
        database_url=str(database_url),
        app_mode="test",
        retrieval_profile="synthetic",
        embedding_path=tmp_path / "missing-model",
        operator_id=r.actor,
        operator_token=token,
        app_origin="http://127.0.0.1:8020",
        data_path=tmp_path / "other-storage",
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v2/auth/login", headers={"Origin": settings.app_origin}, json={"token": token}
        )
        headers = {"Origin": settings.app_origin, "X-CSRF-Token": response.json()["csrf_token"]}
        response = client.post("/api/v2/evidence/search", headers=headers, json={"query": "P0301"})
        assert (
            response.status_code == 503
            and response.json()["error"]["code"] == "EMBEDDING_UNAVAILABLE"
        )
        assert token not in response.text and "missing-model" not in response.text


def test_queued_cancel_and_dimension_guard(indexed_rig):
    from sqlalchemy.exc import IntegrityError

    r = indexed_rig
    body, old = build(r)
    new = reindex(r, body).json()
    run = dict(body, run_id=new["run_id"])
    assert r.cancel(run).status_code == 202
    assert r.state(body)["active_index_id"] == old
    with r.store.engine.connect() as c:
        assert (
            c.execute(
                select(index_versions.c.status).where(index_versions.c.id == UUID(new["index_id"]))
            ).scalar_one()
            == "failed"
        )
        first = (
            c.execute(select(chunk_embeddings).where(chunk_embeddings.c.index_id == UUID(old)))
            .mappings()
            .first()
        )
    with pytest.raises(IntegrityError) as rejected:
        with r.store.engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO chunk_embeddings(index_id,chunk_id,embedding,text_hash) VALUES(:i,:c,CAST(:v AS vector),:h)"
                ),
                dict(
                    i=UUID(new["index_id"]), c=first["chunk_id"], v="[1,2,3]", h=first["text_hash"]
                ),
            )
    assert rejected.value.orig.sqlstate == "23514"  # 0008 per-index dimension CHECK trigger
    assert search(r).json()["chunks"][0]["index_id"] == old


def test_cancel_between_inference_and_batch_finishes_cleanly(indexed_rig):
    from app.domain.documents import IngestError

    r = indexed_rig
    body, old = build(r)
    new = reindex(r, body).json()
    run = dict(body, run_id=new["run_id"])
    lease = r.store.claim("batch-cancel-test", run_id=UUID(run["run_id"]))
    assert lease is not None
    try:
        assert r.cancel(run).status_code == 202
        with pytest.raises(IngestError):
            r.store.stage_index(lease, None)
        assert not lease.lost
        r.store.finish(lease, error="INDEX_INTERRUPTED")
    finally:
        lease.close()
    assert r.client.get("/api/v2/runs/" + run["run_id"]).json()["status"] == "cancelled"
    assert r.state(body)["active_index_id"] == old


def test_failed_build_visible_and_explicit_rebuild(indexed_rig, tmp_path):
    r = indexed_rig
    body = r.upload().json()
    r.complete(body)
    approved = review(r, body)
    assert approved.status_code == 202
    run = dict(body, run_id=approved.json()["index_run_id"])
    r.env["EMBEDDING_PATH"] = str(tmp_path / "missing-model")
    failed, _ = r.worker(run, lease=10)
    assert failed.wait(timeout=30) == 0
    state = r.state(body)
    assert state["index_status"] == state["last_index_status"] == "failed"
    assert state["index_error"]["code"] == "EMBEDDING_UNAVAILABLE"
    assert state["active_index_id"] is None and not state["formal_usable"]
    assert search(r).status_code == 503
    r.env.pop("EMBEDDING_PATH")
    rebuilt = reindex(r, body)
    assert rebuilt.status_code == 202
    recovery, _ = r.worker(dict(body, run_id=rebuilt.json()["run_id"]), lease=10)
    assert recovery.wait(timeout=30) == 0
    assert r.state(body)["index_status"] == "ready"


def test_index_orm_defaults_match_migration(database_url):
    from app.infrastructure.uow import make_engine
    from sqlalchemy import inspect

    engine = make_engine(database_url)
    try:
        columns = {x["name"]: x for x in inspect(engine).get_columns("index_versions")}
        for name in [
            "id",
            "config_json",
            "run_id",
            "dimension",
            "chunk_count",
            "status",
            "profile",
        ]:
            assert columns[name]["default"] is None
            assert index_versions.c[name].server_default is None
        assert set(columns) == set(index_versions.c.keys())
    finally:
        engine.dispose()
