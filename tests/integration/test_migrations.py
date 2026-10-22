import os
import subprocess
import sys
from uuid import uuid4

import psycopg
import pytest
from app.infrastructure.db import Database
from app.infrastructure.db_target import validate_target
from app.infrastructure.schema_version import EXPECTED_REVISION
from psycopg import sql
from psycopg.types.json import Jsonb

pytestmark = pytest.mark.database

TABLES = sorted([
    "alembic_version", "cases", "observations", "runs", "jobs", "run_events", "idempotency_keys",
    "case_area_rankings", "template_repair_rounds", "area_analysis_attempts",
    "workbench_templates", "workbench_template_matches",
    "area_reference_documents", "area_reference_chunks", "area_reference_chunk_vectors",
])


@pytest.fixture
def fresh_database(database_url):
    """A new, empty xiutu_test_* database for this test; dropped afterwards."""
    source = validate_target(database_url)
    admin = (source.sqlalchemy_url().set(drivername="postgresql", database="xiutu_dev")
             .render_as_string(hide_password=False))
    admin_kwargs = validate_target(admin, "development").connect_kwargs()
    name = "xiutu_test_mig_" + uuid4().hex[:24]
    with psycopg.connect(**admin_kwargs, autocommit=True) as c:
        c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = (source.sqlalchemy_url().set(drivername="postgresql", database=name)
           .render_as_string(hide_password=False))
    try:
        yield url
    finally:
        with psycopg.connect(**admin_kwargs, autocommit=True) as c:
            c.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


def migrate(url, *args, allow_delete=False):
    env = dict(os.environ, DATABASE_URL=url)
    env.pop("XIUTU_ALLOW_LEGACY_DELETE", None)
    if allow_delete:
        env["XIUTU_ALLOW_LEGACY_DELETE"] = "1"
    return subprocess.run([sys.executable, "-B", "-m", "alembic", *args],
                          env=env, capture_output=True, text=True, timeout=60).returncode


def ready(url):
    db = Database(url)
    db.open()
    try:
        return db.ready()
    finally:
        db.close()


def test_empty_database_to_head_has_only_current_tables(fresh_database):
    url = fresh_database
    assert not ready(url)
    assert migrate(url, "upgrade", "head") == 0
    assert ready(url)
    with psycopg.connect(**validate_target(url).connect_kwargs()) as c:
        assert c.execute("SELECT version_num FROM alembic_version").fetchone()[0] == EXPECTED_REVISION
        tables = sorted(row[0] for row in c.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall())
        assert tables == TABLES
        assert c.execute("SELECT count(*) FROM pg_namespace WHERE nspname='wp01_wp11'").fetchone()[0] == 0
    # Retiring old data cannot be undone by a downgrade: the backup is the way back.
    assert migrate(url, "downgrade", "0025_reference_vehicle") != 0


def test_0026_keeps_template_cases_and_deletes_old_ones_only_when_allowed(fresh_database):
    url = fresh_database
    assert migrate(url, "upgrade", "0025_reference_vehicle") == 0
    owner = uuid4()
    with psycopg.connect(**validate_target(url).connect_kwargs(), autocommit=True) as c:
        def case(snapshot):
            return c.execute(
                "INSERT INTO cases (owner_id, vehicle_json, fault_description, intake_snapshot, revision)"
                " VALUES (%s, %s, '迁移测试', %s, 1) RETURNING id",
                (owner, Jsonb({"model": "x"}), Jsonb(snapshot))).fetchone()[0]
        kept = case({"workbench_flow": "template-match-v1", "template_binding": {"version": "2"}})
        old_template = case({"workbench_flow": "template-match-v1", "template_binding": {"version": "1"}})
        old_demo = case({"topic_binding": {"version": "2.2.1-b02"}})
        for case_id in (kept, old_template, old_demo):
            c.execute("INSERT INTO observations (case_id, kind, payload, created_revision, actor_id)"
                      " VALUES (%s, 'choice', %s, 1, %s)", (case_id, Jsonb({"question_id": "Q"}), owner))
    assert migrate(url, "upgrade", "head") != 0  # refuses: there are old cases to delete
    assert not ready(url)
    assert migrate(url, "upgrade", "head", allow_delete=True) == 0
    assert ready(url)
    with psycopg.connect(**validate_target(url).connect_kwargs()) as c:
        assert [row[0] for row in c.execute("SELECT id FROM cases").fetchall()] == [kept]
        assert [row[0] for row in c.execute("SELECT case_id FROM observations").fetchall()] == [kept]
        columns = {row[0] for row in c.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='cases'").fetchall()}
        assert not columns & {"graph_epoch", "corpus_manifest", "diagnosis_mode", "policy_version"}
    with psycopg.connect(**validate_target(url).connect_kwargs(), autocommit=True) as c:
        # Observations are still append-only after the one-off delete.
        with pytest.raises(psycopg.Error):
            c.execute("DELETE FROM observations")
