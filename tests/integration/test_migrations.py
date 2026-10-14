import json
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

pytestmark = pytest.mark.database


def test_migration_upgrade_downgrade(database_url):
    source = validate_target(database_url)
    admin = (
        source.sqlalchemy_url()
        .set(drivername="postgresql", database="xiutu_dev")
        .render_as_string(hide_password=False)
    )
    name = "xiutu_test_wp02mig_" + uuid4().hex[:24]
    with psycopg.connect(
        **validate_target(admin, "development").connect_kwargs(), autocommit=True
    ) as c:
        c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = (
        source.sqlalchemy_url()
        .set(drivername="postgresql", database=name)
        .render_as_string(hide_password=False)
    )
    kwargs = validate_target(url).connect_kwargs()
    env = dict(os.environ, DATABASE_URL=url)

    def migrate(*args):
        p = subprocess.run(
            [sys.executable, "-B", "-m", "alembic", *args],
            env=env,
            capture_output=True,
            text=True,
            timeout=40,
        )
        assert p.returncode == 0, "Migration command failed (connection redacted)"

    def ready():
        db = Database(url)
        db.open()
        try:
            return db.ready()
        finally:
            db.close()

    assert not ready()
    # Empty database to head, then downgrade and explicit WP-01 to WP-02 path.
    migrate("upgrade", "head")
    assert ready()
    with psycopg.connect(**kwargs, autocommit=True) as c:
        c.execute("CREATE SCHEMA wp02_sentinel")
        c.execute("CREATE TABLE wp02_sentinel.marker (value int)")
        c.execute("INSERT INTO wp02_sentinel.marker VALUES (7)")
    migrate("downgrade", "0001_environment")
    assert not ready()
    with psycopg.connect(**kwargs) as c:
        assert (
            c.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0]
            == "0.8.2"
        )
        assert c.execute("SELECT value FROM wp02_sentinel.marker").fetchone() == (7,)
        assert c.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        ).fetchall() == [("alembic_version",)]
    migrate("upgrade", "0002_core")
    assert not ready()
    migrate("upgrade", "head")
    assert ready()
    migrate("downgrade", "0002_core")
    assert not ready()
    migrate("upgrade", "head")
    assert ready()
    migrate("downgrade", "0006_evidence_specs")
    assert not ready()
    migrate("upgrade", "head")
    assert ready()
    migrate("downgrade", "0005_indexes")
    assert not ready()
    migrate("upgrade", "head")
    assert ready()
    migrate("downgrade", "0004_documents")
    assert not ready()
    migrate("upgrade", "head")
    assert ready()
    migrate("downgrade", "0003_jobs")
    assert not ready()
    migrate("upgrade", "head")
    assert ready()
    with psycopg.connect(**kwargs, autocommit=True) as c:
        assert (
            c.execute("SELECT version_num FROM alembic_version").fetchone()[0] == EXPECTED_REVISION
        )
        tables = sorted(
            x[0]
            for x in c.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            ).fetchall()
        )
        assert tables == sorted(
            [
                "tool_executions",
                "tool_calls",
                "observations",
                "case_evidence",
                "measurement_specs",
                "measurement_spec_reviews",
                "measurement_comparisons",
                "alembic_version",
                "index_versions",
                "chunk_embeddings",
                "cases",
                "documents",
                "document_versions",
                "document_reviews",
                "chunks",
                "runs",
                "reports",
                "jobs",
                "run_events",
                "idempotency_keys",
                "diagnosis_areas",
                "diagnosis_area_conclusions",
                "diagnosis_steps",
                "diagnosis_publications",
                "diagnosis_candidates",
                "graph_progress",
            ]
        )
        assert (
            c.execute(
                "SELECT count(*) FROM information_schema.columns WHERE table_name='document_versions' AND column_name='active_index_id'"
            ).fetchone()[0]
            == 1
        )
        c.execute("UPDATE alembic_version SET version_num='wrong'")
    assert not ready()
    with psycopg.connect(**kwargs, autocommit=True) as c:
        c.execute("UPDATE alembic_version SET version_num=%s", (EXPECTED_REVISION,))
        c.execute("DROP SCHEMA wp02_sentinel CASCADE")
    print(
        json.dumps(
            {
                "migration_database": name,
                "empty_to_head": True,
                "downgrade_to_environment": True,
                "old_revision_not_ready": True,
                "upgrade_again": True,
                "other_schema_preserved": True,
                "tables": tables,
            }
        )
    )
