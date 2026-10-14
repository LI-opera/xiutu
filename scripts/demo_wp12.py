"""Free WP-12 HTTP transaction demo with synthetic, isolated fixtures only."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.infrastructure.db_target import validate_target


def main():
    root = Path(__file__).resolve().parents[1]
    if Path.cwd().resolve() != root:
        raise SystemExit("Run from xiutu-v5 project root")
    url = os.environ.get("TEST_DATABASE_URL", "")
    validate_target(url, "test")
    if os.environ.get("DATABASE_URL") != url:
        raise SystemExit("DATABASE_URL must equal isolated TEST_DATABASE_URL")
    if os.environ.get("XIUTU_WP11_PAID"):
        raise SystemExit("The WP-12 fixture demo refuses paid model calls")
    out = root / ".test-runs" / ("wp12-demo-" + uuid4().hex)
    out.mkdir(parents=True, exist_ok=False)
    evidence = out / "wp10-evidence"
    evidence.mkdir()
    env = dict(os.environ, WP10_EVIDENCE=str(evidence), PYTHONPATH="backend")
    print("SYNTHETIC HTTP TEST: observation, correction, area card, two saved-choice branches")
    cmd = [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider",
           "tests/integration/test_wp12_turns.py", "-k",
           "observation_atomic_idempotent or unavailable_correction_new_epoch or two_saved_choices_drive_distinct_source_backed_checks",
           "-q", "-s", "--basetemp", str(out / "tmp"),
           "--junitxml", str(out / "result.xml")]
    return subprocess.run(cmd, cwd=root, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
