"""SYNTHETIC ONLY: executable HTTP demonstration via the shipped integration harness."""

import os
import subprocess
import sys
import uuid
from pathlib import Path

from app.infrastructure.db_target import validate_target

ROOT = Path(__file__).resolve().parents[1]


def main():
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Set an isolated TEST_DATABASE_URL; no fallback database")
    validate_target(url, "test")
    # No cleanup of pre-existing output and no reparse traversal.
    parent = ROOT / ".test-runs"
    for p in [parent, *parent.parents]:
        if p.exists() and (p.is_symlink() or p.is_junction() or not p.is_dir()):
            raise SystemExit("Refuse non-plain output path")
    parent.mkdir(exist_ok=True)
    out = parent / ("wp07-demo-" + uuid.uuid4().hex)
    out.mkdir()
    env = dict(
        os.environ,
        TEST_DATABASE_URL=url,
        DATABASE_URL=url,
        PYTHONPATH=str(ROOT / "backend"),
        PYTHONDONTWRITEBYTECODE="1",
        WP06_EVIDENCE=str(out),
        WP07_EVIDENCE=str(out),
    )
    print(
        "SYNTHETIC ONLY: fabricated 1..2 V / engine=off, NOT a repair specification. Test dependencies required.",
        flush=True,
    )
    command = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "tests/integration/test_business_tools.py::test_five_tools_demo",
        "-q",
        "-s",
        "-p",
        "no:cacheprovider",
        "--basetemp",
        str(out / "tmp"),
        "--junitxml=" + str(out / "demo.xml").replace("\\", "/"),
    ]
    result = subprocess.run(command, cwd=ROOT, env=env)
    print("Demo artifacts:", out)
    print(
        "Five real tools plus empty observations, refusal, budget exhaustion, pinned index and revocation; no LLM/MCP/Agent or production observation writing"
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
