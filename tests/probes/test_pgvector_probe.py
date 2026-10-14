import json
import os
import subprocess
import sys

import psycopg
from app.config import Settings
from app.infrastructure.db_target import validate_target
from app.infrastructure.schema_version import EXPECTED_REVISION
from app.main import create_app
from fastapi.testclient import TestClient
from psycopg import sql


def test_real_vector_and_health(database_url, probe_schema, tmp_path):
    env = dict(os.environ, DATABASE_URL=database_url)
    run = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        capture_output=True,
        text=True,
        timeout=40,
    )
    assert run.returncode == 0, "Migration failed; inspect local environment (URL redacted)"
    with psycopg.connect(
        **validate_target(database_url, "test").connect_kwargs(), autocommit=True
    ) as conn:
        version = conn.execute(
            "SELECT extversion FROM pg_extension WHERE extname='vector'"
        ).fetchone()[0]
        table = sql.Identifier(probe_schema, "vectors")
        conn.execute(
            sql.SQL("CREATE TABLE {} (id integer PRIMARY KEY, embedding vector(3))").format(table)
        )
        conn.execute(
            sql.SQL("INSERT INTO {} VALUES (1,'[1,0,0]'),(2,'[0,1,0]'),(3,'[-1,0,0]')").format(
                table
            )
        )
        rows = conn.execute(
            sql.SQL("SELECT id, embedding <-> '[1,0,0]'::vector AS d FROM {} ORDER BY d").format(
                table
            )
        ).fetchall()
        assert [x[0] for x in rows] == [1, 2, 3]
        assert rows[0][1] == 0
    with TestClient(create_app(Settings(database_url=database_url, data_path=tmp_path))) as client:
        assert client.get("/api/v2/health/live").status_code == 200
        response = client.get("/api/v2/health/ready")
        assert response.status_code == 200
        assert response.json()["model_verified"] is False
    print(json.dumps({"vector_version": version, "order": [x[0] for x in rows], "ready": 200}))


def test_database_down_health(tmp_path):
    with TestClient(
        create_app(
            Settings(
                database_url="postgresql://nobody@127.0.0.1:5433/xiutu_test_unavailable",
                data_path=tmp_path,
            )
        )
    ) as client:
        assert client.get("/api/v2/health/live").status_code == 200
        response = client.get("/api/v2/health/ready")
        assert response.status_code == 503
        assert "nobody" not in response.text


def test_missing_migration_health(database_url, probe_schema, tmp_path):
    # An isolated search_path with extension visible but no migration version is not ready.
    from app.infrastructure.db import Database

    db = Database(database_url, schema=probe_schema)
    db.open()
    try:
        assert db.ready() is False
    finally:
        db.close()


def test_wrong_migration_health(database_url, probe_schema):
    from app.infrastructure.db import Database

    target = validate_target(database_url, "test")
    with psycopg.connect(**target.connect_kwargs(schema=probe_schema), autocommit=True) as conn:
        conn.execute("CREATE TABLE alembic_version (version_num varchar(32) NOT NULL)")
        conn.execute("INSERT INTO alembic_version VALUES ('unexpected_revision')")
    db = Database(database_url, schema=probe_schema)
    db.open()
    try:
        assert db.ready() is False
    finally:
        db.close()


def test_prepare_database_refuses_existing(database_url):
    target = validate_target(database_url, "test")
    admin = target.sqlalchemy_url().set(drivername="postgresql", database="xiutu_dev")
    env = dict(os.environ, DATABASE_URL=admin.render_as_string(hide_password=False))
    result = subprocess.run(
        [sys.executable, "-B", "scripts/probes/prepare_database.py", "--name", target.database],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0 and "DuplicateDatabase" in result.stderr
    with psycopg.connect(**target.connect_kwargs()) as conn:
        assert (
            conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == EXPECTED_REVISION
        )
    print(json.dumps({"existing_database_refused": True, "migration_preserved": True}))
