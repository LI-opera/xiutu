"""Run the reference-ingest database tests in a throwaway database, then drop it.

Never touches the workspace database: creates xiutu_test_ingest_<random> on the local
PostgreSQL (:5433), migrates it, installs the workbench templates, runs
tests/integration/test_reference_ingest.py against it and drops it again. No model calls.

    uv run python -B scripts/run_reference_ingest_db_tests.py
"""
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

import psycopg  # noqa: E402
from psycopg import sql  # noqa: E402

from app.infrastructure.db_target import validate_target  # noqa: E402


def main():
    password = json.loads((ROOT / ".local-data/wp01-postgres.json").read_text(encoding="utf-8"))["password"]
    base = f"postgresql://xiutu:{quote(password, safe='')}@127.0.0.1:5433/"
    admin = validate_target(base + "xiutu_dev?connect_timeout=2", "development")
    name = "xiutu_test_ingest_" + uuid.uuid4().hex[:10]
    url = base + name + "?connect_timeout=2"
    validate_target(url, "test")
    with psycopg.connect(**admin.connect_kwargs(), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    print("临时测试库：", name, flush=True)
    env = {key: value for key, value in os.environ.items() if not key.startswith(("PG", "XIUTU_"))}
    env.update(DATABASE_URL=url, TEST_DATABASE_URL=url, APP_MODE="test", PYTHONPATH=str(ROOT / "backend"),
               PYTHONIOENCODING="utf-8", DEEPSEEK_API_KEY="")
    code = 1
    try:
        steps = [
            [sys.executable, "-B", "-m", "alembic", "upgrade", "head"],
            [sys.executable, "-B", "-c", "import os, sys; sys.path[:0] = ['.', 'backend']\n"
             "from sqlalchemy import create_engine\n"
             "from app.infrastructure.db_target import validate_target\n"
             "from scripts.seed_workbench_templates import seed\n"
             "t = validate_target(os.environ['DATABASE_URL'], 'test')\n"
             "e = create_engine(t.sqlalchemy_url(), connect_args=t.connect_kwargs())\n"
             "with e.begin() as c: print('templates:', len(seed(c)))\n"
             "e.dispose()"],
            [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "-q",
             "tests/integration/test_reference_ingest.py", "--basetemp", f".test-runs/{name}"],
        ]
        for step in steps:
            code = subprocess.run(step, cwd=ROOT, env=env, check=False).returncode
            if code:
                break
    finally:
        with psycopg.connect(**admin.connect_kwargs(), autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
        print("已删除临时测试库：", name, flush=True)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
