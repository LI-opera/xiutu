import json
import os
import uuid

import psycopg
import pytest
from app.infrastructure.db_target import validate_target
from psycopg import sql


class RedactedURL(str):
    def __repr__(self):
        return "<TEST_DATABASE_URL redacted>"


def isolated_database_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is required; no fallback")
    try:
        validate_target(url, "test")
    except ValueError:
        pytest.fail("TEST_DATABASE_URL rejected by shared isolated target policy")
    return RedactedURL(url)


@pytest.fixture
def database_url():
    return isolated_database_url()


@pytest.fixture
def probe_schema(database_url):
    target = validate_target(database_url, "test")
    name = "wp01_" + uuid.uuid4().hex
    with psycopg.connect(**target.connect_kwargs(), autocommit=True) as conn:
        before = conn.execute("SELECT nspname FROM pg_namespace ORDER BY nspname").fetchall()
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
    try:
        yield name
    finally:
        with psycopg.connect(**target.connect_kwargs(), autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))
            after = conn.execute("SELECT nspname FROM pg_namespace ORDER BY nspname").fetchall()
            assert before == after, "Probe schema cleanup changed unrelated schema inventory"
            print(
                json.dumps(
                    {"schema": name, "created_and_removed": True, "other_schemas_unchanged": True}
                )
            )
