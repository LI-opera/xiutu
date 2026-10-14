"""Historical one-step graph fixture using synthetic test data only.

The test owns its API/worker/database rows and prints the actual publish and
resume state. It exercises the retired diagnosis path, not the current
template workbench or a DeepSeek diagnosis.
"""

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
        raise SystemExit("Free fixture demo refuses the paid model switch")
    run_dir = root / ".test-runs" / ("wp11-demo-" + uuid4().hex)
    run_dir.mkdir(parents=True, exist_ok=False)
    print("HISTORICAL SYNTHETIC FIXTURE: retired diagnosis path; no model inference")
    command = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "tests/integration/legacy_wp11_graph.py",
        "-k",
        "graph_interrupt_and_saved_observation_resume",
        "-q",
        "-s",
        "--basetemp",
        str(run_dir / "temp"),
        "--junitxml",
        str(run_dir / "result.xml"),
    ]
    return subprocess.run(command, cwd=root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
