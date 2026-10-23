import os
import runpy
import socket
import sys
from pathlib import Path
from unittest.mock import Mock

import psycopg
import pytest
import sqlalchemy
from app.infrastructure.db_target import validate_target
from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg

ROOT = Path(__file__).resolve().parents[2]
GOOD = "postgresql://review:synthetic@localhost:5433/xiutu_test_gate"
BAD = [
    "postgresql://review@localhost:5433/xiutu_dev?dbname=review_unrelated&host=192.0.2.10&port=5544",
    GOOD + "?hostaddr=192.0.2.10",
    GOOD + "?service=outside",
    GOOD + "?host=192.0.2.10",
    GOOD + "?dbname=other",
    GOOD + "?port=5544",
    GOOD + "?options=-c%20search_path=public",
    GOOD + "?connect_timeout=2&connect_timeout=3",
    "postgresql://review@localhost,192.0.2.10:5433/xiutu_test_gate",
    "postgresql://review@localhost/xiutu_test_gate",
    "postgresql://review@:5433/xiutu_test_gate",
    "postgresql://localhost:5433/xiutu_test_gate",
    "postgresql://review@localhost:5433/",
    "postgresql://review@localhost:5432/xiutu_test_gate",
    "postgresql://review@localhost:5433/other",
    GOOD + "?connect_timeout=0",
    GOOD + "#fragment",
    "service=outside",
]


@pytest.fixture(autouse=True)
def prohibit_connection(monkeypatch):
    for key in list(os.environ):
        if key.upper().startswith("PG"):
            monkeypatch.delenv(key)

    def forbidden(*args, **kwargs):
        raise AssertionError("Database-boundary test must not make any connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(psycopg, "connect", forbidden)


@pytest.mark.parametrize("url", BAD)
def test_bad_targets_before_driver(url):
    with pytest.raises(ValueError):
        validate_target(url, "migration")


@pytest.mark.parametrize(
    "key",
    [
        "PGHOSTADDR",
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGSYSCONFDIR",
        "PGHOST",
        "PGPORT",
        "PGDATABASE",
        "PGUSER",
        "PGOPTIONS",
        "PGPASSFILE",
    ],
)
def test_ambient_targets_rejected(monkeypatch, key):
    monkeypatch.setenv(key, "synthetic")
    with pytest.raises(ValueError, match="PG"):
        validate_target(GOOD)


def test_final_driver_parameters_and_scopes():
    target = validate_target(GOOD + "?connect_timeout=3")
    args, params = PGDialect_psycopg().create_connect_args(target.sqlalchemy_url())
    params.update(target.connect_kwargs())
    assert not args
    assert {k: params[k] for k in ["host", "hostaddr", "port", "dbname", "user"]} == {
        "host": "127.0.0.1",
        "hostaddr": "127.0.0.1",
        "port": 5433,
        "dbname": "xiutu_test_gate",
        "user": "review",
    }
    assert params["connect_timeout"] == 3 and params["passfile"] == os.devnull
    assert "synthetic" not in repr(target)
    validate_target(GOOD.replace("localhost", "127.0.0.1"))
    validate_target(GOOD.replace("xiutu_test_gate", "xiutu_dev"), "development")
    with pytest.raises(ValueError):
        validate_target(GOOD.replace("xiutu_test_gate", "xiutu_dev"), "test")
    with pytest.raises(ValueError):
        validate_target(GOOD, "development")


@pytest.mark.parametrize(
    "entry",
    ["migrations/env.py", "scripts/probes/prepare_database.py"],
)
@pytest.mark.parametrize(
    "query", ["?hostaddr=192.0.2.10", "?dbname=other&host=192.0.2.10&port=5544"]
)
def test_real_entrypoints_reject_before_engine(monkeypatch, entry, query):
    engine = Mock(side_effect=AssertionError("Engine must not be created"))
    monkeypatch.setattr(sqlalchemy, "create_engine", engine)
    db = "xiutu_dev"
    monkeypatch.setenv("DATABASE_URL", GOOD.replace("xiutu_test_gate", db) + query)
    monkeypatch.setenv("TEST_DATABASE_URL", GOOD + query)
    monkeypatch.setenv("DATA_PATH", str(ROOT / ".test-runs"))
    argv = [entry, "--name", "xiutu_test_gate"]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(ValueError):
        runpy.run_path(str(ROOT / entry), run_name="__main__")
    engine.assert_not_called()


CONTAINER = "postgresql://xiutu:synthetic@postgres:5432/xiutu_dev"


def test_container_service_needs_its_explicit_name(monkeypatch):
    monkeypatch.delenv("CONTAINER_DB_HOST", raising=False)
    with pytest.raises(ValueError):
        validate_target(CONTAINER, "migration")
    monkeypatch.setenv("CONTAINER_DB_HOST", "postgres")
    target = validate_target(CONTAINER, "migration")
    kwargs = target.connect_kwargs()
    assert (kwargs["host"], kwargs["port"], kwargs["dbname"]) == ("postgres", 5432, "xiutu_dev")
    assert "hostaddr" not in kwargs
    assert target.sqlalchemy_url().host == "postgres"
    # The loopback target is unchanged while the container name is set.
    assert validate_target(GOOD, "migration").connect_kwargs()["hostaddr"] == "127.0.0.1"


@pytest.mark.parametrize("url", [
    "postgresql://xiutu:synthetic@postgres:5433/xiutu_dev",            # wrong port for the service
    "postgresql://xiutu:synthetic@db:5432/xiutu_dev",                  # a different host
    "postgresql://xiutu:synthetic@192.0.2.10:5432/xiutu_dev",          # an address
    "postgresql://xiutu:synthetic@postgres:5432/other",                # not a xiutu database
    "postgresql://xiutu:synthetic@postgres:5432/xiutu_dev?host=192.0.2.10",
])
def test_container_name_allows_only_that_service(monkeypatch, url):
    monkeypatch.setenv("CONTAINER_DB_HOST", "postgres")
    with pytest.raises(ValueError):
        validate_target(url, "migration")


@pytest.mark.parametrize("name", ["192.0.2.10", "Postgres", "-x", "a" * 64, "postgres.example.com"])
def test_container_name_must_be_a_plain_service_name(monkeypatch, name):
    monkeypatch.setenv("CONTAINER_DB_HOST", name)
    with pytest.raises(ValueError):
        validate_target(f"postgresql://xiutu:synthetic@{name}:5432/xiutu_dev", "migration")
