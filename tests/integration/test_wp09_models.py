"""Real local BGE, immutable E5 generations, HTTP and independent workers."""

import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from app.config import Settings
from app.domain.retrieval import ReindexInput
from app.domain.schemas import CreateCase
from app.infrastructure.orm import jobs, run_events
from app.legacy_case_creation import LegacyCaseService as CaseService
from app.services.index_service import IndexService
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from test_document_ingest import docrig, wait  # noqa: F401
from test_indexes import build, indexed_rig  # noqa: F401

BGE = Path(
    "E:/AI_Cache/huggingface/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181"
)
pytestmark = pytest.mark.database


def record(name, data):
    e = os.environ.get("WP09_EVIDENCE")
    if e:
        (Path(e) / (name + "-" + uuid4().hex[:8] + ".json")).write_text(
            json.dumps(data, indent=2, default=str), encoding="utf8"
        )


def schedule_bge(r, body):
    settings = Settings(
        app_mode="test",
        database_url=r.env["DATABASE_URL"],
        retrieval_profile="synthetic",
        embedding_provider="local_bge_m3",
        embedding_model_path=BGE,
    )
    status, value = IndexService(r.store.engine, settings).reindex(
        r.actor, UUID(body["document_id"]), UUID(body["version_id"]), ReindexInput(), uuid4().hex
    )
    assert status == 202
    r.env["EMBEDDING_MODEL_PATH"] = str(BGE)
    return dict(body, run_id=value["run_id"]), value


def archived_case(r):
    """Freeze a synthetic historical manifest without reopening the retired public write API."""
    _, case = CaseService(r.store.engine, b"synthetic", profile="synthetic").create(
        r.actor,
        CreateCase(vehicle={"model": "Synthetic"}, fault_description="SYNTHETIC index history"),
        uuid4().hex,
    )
    return case


@pytest.mark.parametrize("fault", ["normal", "kill", "lease", "cancel"])
def test_e5_to_bge_atomic_generations(indexed_rig, fault):  # noqa: F811 - imported pytest fixture
    r = indexed_rig
    body, old = build(r)
    case = archived_case(r)
    frozen = case["corpus_manifest"]
    assert len(frozen) == 1 and frozen[0]["index_id"] == old
    run, value = schedule_bge(r, body)
    # Model load and embedding time vary under a full suite. Give the lease
    # enough time to stage real vectors; for the lease fault, shorten the DB
    # deadline only after the before_finish barrier proves staging completed.
    p, gate = r.worker(
        run, barrier="before_finish", lease=60 if fault == "lease" else 6,
        heartbeat=120 if fault == "lease" else 0.3,
    )
    wait(lambda: gate.with_suffix(".before_finish").exists(), 30)
    assert r.state(body)["active_index_id"] == old
    with r.store.engine.connect() as c:
        dims = (
            c.execute(
                text("select vector_dims(embedding) from chunk_embeddings where index_id=:i"),
                {"i": UUID(value["index_id"])},
            )
            .scalars()
            .all()
        )
        assert dims and set(dims) == {1024}
    if fault == "lease":
        with r.store.engine.begin() as c:
            changed = c.execute(
                text("update jobs set lease_until=clock_timestamp()+interval '2 seconds' "
                     "where run_id=:run_id and status='running'"),
                {"run_id": UUID(run["run_id"])},
            )
            assert changed.rowcount == 1
    if fault == "cancel":
        assert r.cancel(run).status_code == 202
    if fault == "kill":
        p.terminate()
        p.wait(timeout=10)
    if fault in ["kill", "lease"]:

        def expired():
            with r.store.engine.connect() as c:
                return c.execute(
                    select(jobs.c.lease_until < text("clock_timestamp()")).where(
                        jobs.c.run_id == UUID(run["run_id"])
                    )
                ).scalar_one()

        wait(expired, 12)
    if fault != "kill":
        gate.with_suffix(".release").touch()
        assert p.wait(timeout=20) == 0
    if fault != "normal":
        assert r.state(body)["active_index_id"] == old
        with r.store.engine.connect() as c:
            assert not c.execute(
                select(run_events.c.id).where(
                    run_events.c.run_id == UUID(run["run_id"]), run_events.c.type == "run.succeeded"
                )
            ).first()
    if fault in ["kill", "lease"]:
        q, _ = r.worker(run, lease=10)
        assert q.wait(timeout=30) == 0
    expected = old if fault == "cancel" else value["index_id"]
    assert r.state(body)["active_index_id"] == expected
    # API process started with E5; it must still route a BGE index by fingerprint with an explicit available path.
    r.env["EMBEDDING_MODEL_PATH"] = str(BGE)
    from app.domain.retrieval import SearchInput
    from app.retrieval.service import RetrievalService

    settings = Settings(
        app_mode="test",
        database_url=r.env["DATABASE_URL"],
        retrieval_profile="synthetic",
        embedding_model_path=BGE,
    )
    result = RetrievalService(r.store.engine, settings).search(r.actor, SearchInput(query="P0301"))
    assert result["chunks"][0]["index_id"] == expected
    # A historical case keeps its frozen E5 index despite the active BGE switch.
    saved = r.client.get(f"/api/v2/cases/{case['id']}")
    assert saved.status_code == 200
    assert saved.json()["corpus_manifest"] == frozen
    with r.store.engine.begin() as c:
        with pytest.raises(DBAPIError):
            with c.begin_nested():
                c.execute(
                    text(
                        "update chunk_embeddings set embedding=CAST(:v AS vector) where index_id=:i"
                    ),
                    {"v": "[1,2]", "i": UUID(old)},
                )
    record(
        "bge-generations",
        dict(
            fault=fault,
            old=old,
            new=value["index_id"],
            active=expected,
            dimension=1024,
            worker_pid=p.pid,
            old_frozen=frozen[0]["index_id"],
        ),
    )


def test_bge_activation_sql_rollback(indexed_rig):  # noqa: F811 - imported pytest fixture
    r = indexed_rig
    body, old = build(r)
    run, value = schedule_bge(r, body)
    worker, gate = r.worker(run, barrier="before_finish", lease=30)
    wait(lambda: gate.with_suffix(".before_finish").exists(), 30)
    name = "wp09_fail_" + uuid4().hex
    with r.store.engine.begin() as c:
        c.execute(
            text(
                f"CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.active_index_id = '{value['index_id']}'::uuid THEN RAISE EXCEPTION 'synthetic activation failure'; END IF; RETURN NEW; END $$"
            )
        )
        c.execute(
            text(
                f"CREATE TRIGGER {name} BEFORE UPDATE ON document_versions FOR EACH ROW EXECUTE FUNCTION {name}()"
            )
        )
    try:
        gate.with_suffix(".release").touch()
        exit_code = worker.wait(timeout=30)
        assert r.state(body)["active_index_id"] == old
        with r.store.engine.connect() as c:
            assert (
                c.execute(
                    text("select status from index_versions where id=:i"),
                    {"i": UUID(value["index_id"])},
                ).scalar_one()
                != "ready"
            )
            assert not c.execute(
                select(run_events.c.id).where(
                    run_events.c.run_id == UUID(run["run_id"]), run_events.c.type == "run.succeeded"
                )
            ).first()
        frozen = archived_case(r)["corpus_manifest"]
        assert len(frozen) == 1 and frozen[0]["index_id"] == old
        record(
            "bge-sql-rollback",
            dict(
                old=old, attempted=value["index_id"], worker_exit=exit_code, active_preserved=True
            ),
        )
    finally:
        with r.store.engine.begin() as c:
            c.execute(text(f"DROP TRIGGER {name} ON document_versions"))
            c.execute(text(f"DROP FUNCTION {name}()"))
