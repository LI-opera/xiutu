"""Create a NEW least-privilege role; never alter an existing role/password."""

import argparse
import json
import os
import secrets
from pathlib import Path
from uuid import uuid4

import psycopg
from app.infrastructure.db_target import validate_target
from app.mcp_server.config import TABLES
from psycopg import sql


def provision(url, output):
    target = validate_target(url, "migration")
    role = "xiutu_mcp_" + uuid4().hex
    password = secrets.token_urlsafe(36)
    path = Path(output)
    if path.exists() or not path.parent.is_dir():
        raise ValueError("New output in a protected existing directory required")
    for p in (path.parent, *path.parent.parents):
        if p.is_symlink() or p.is_junction():
            raise ValueError("Reparse output path forbidden")
    # Reserve output first; no overwriting old secret, no secret in stdout/arguments.
    with path.open("x", encoding="utf8") as f:
        with psycopg.connect(**target.connect_kwargs()) as c:
            c.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                ).format(sql.Identifier(role), sql.Literal(password))
            )
            c.execute(
                sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(
                    sql.Identifier(role)
                )
            )
            c.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(target.database), sql.Identifier(role)
                )
            )
            c.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
            for table in TABLES:
                c.execute(
                    sql.SQL("GRANT SELECT ON TABLE public.{} TO {}").format(
                        sql.Identifier(table), sql.Identifier(role)
                    )
                )
        json.dump(
            dict(deployment="loopback", name=target.database, user=role, password=password), f
        )
    if os.name != "nt":
        path.chmod(0o600)
    return role


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    a = p.parse_args()
    try:
        provision(os.environ["DATABASE_URL"], a.output)
        print("New readonly role created; credentials saved in protected output")
    except Exception:
        print(
            "Readonly role provisioning failed; inspect target and permissions without logging secrets"
        )
        raise SystemExit(1)
