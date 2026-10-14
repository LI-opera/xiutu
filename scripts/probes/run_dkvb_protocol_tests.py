"""Create and test one isolated protocol database without printing credentials."""
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import psycopg
from psycopg import sql

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))
from app.infrastructure.db_target import validate_target  # noqa: E402

name = os.environ.get("PROTOCOL_TEST_DB", "xiutu_test_protocol_r1b")
password = __import__("json").loads((Path(ROOT) / ".local-data/wp01-postgres.json").read_text(encoding="utf-8"))["password"]
admin_url = f"postgresql://xiutu:{quote(password, safe='')}@127.0.0.1:5433/xiutu_dev?connect_timeout=2"
admin = validate_target(admin_url, "development")
with psycopg.connect(**admin.connect_kwargs(), autocommit=True) as conn:
    conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
test_url = f"postgresql://xiutu:{quote(password, safe='')}@127.0.0.1:5433/{name}?connect_timeout=2"
env = dict(os.environ, DATABASE_URL=test_url, TEST_DATABASE_URL=test_url)
commands = [
    [os.path.join(ROOT, ".venv", "Scripts", "alembic.exe"), "upgrade", "head"],
    [os.path.join(ROOT, ".venv", "Scripts", "python.exe"), "scripts/setup_graph_checkpoint.py"],
    [os.path.join(ROOT, ".venv", "Scripts", "python.exe"), "-m", "pytest", "-p", "no:cacheprovider",
     "tests/integration/test_dkvb_trusted_protocol.py", "-x", "-vv", "-s", "--basetemp", f".test-runs/{name}"],
]
print("Created isolated database:", name)
for command in commands:
    result = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
