"""Explicit, one-time pinned LangGraph saver setup after 0009 migration."""

import os

import psycopg
from app.infrastructure.db_target import validate_target
from langgraph.checkpoint.postgres import PostgresSaver


def main():
    target = validate_target(os.environ["DATABASE_URL"], "migration")
    kwargs = target.connect_kwargs()
    kwargs["options"] = "-c search_path=wp01_wp11,public"
    with psycopg.connect(**kwargs, autocommit=True, prepare_threshold=0) as c:
        if c.execute("SELECT current_schema()").fetchone()[0] != "wp01_wp11":
            raise RuntimeError("0009 checkpoint schema is missing")
        PostgresSaver(c).setup()
        if c.execute("SELECT to_regclass('wp01_wp11.checkpoints')").fetchone()[0] is None:
            raise RuntimeError("Checkpoint setup incomplete")
    print("LangGraph checkpoint schema ready (no credentials printed)")


if __name__ == "__main__":
    main()
