import json
import os
import subprocess
import sys
import uuid


def test_checkpoint_cross_process(database_url, probe_schema):
    workflow = "wp01-" + uuid.uuid4().hex
    env = dict(os.environ, TEST_DATABASE_URL=database_url)

    def run(mode, workflow_id):
        return subprocess.run(
            [sys.executable, "scripts/probes/graph_worker.py", mode, workflow_id, probe_schema],
            env=env,
            capture_output=True,
            text=True,
            timeout=40,
        )

    first = run("start", workflow)
    assert first.returncode == 0, first.stderr
    a = json.loads(first.stdout)
    assert a["values"]["count"] == 1 and a["next"] == ["pause"]
    second = run("resume", workflow)
    assert second.returncode == 0, second.stderr
    b = json.loads(second.stdout)
    assert a["pid"] != b["pid"]
    assert b["values"] == {"count": 1, "approval": "approved"} and b["next"] == []
    wrong = run("resume", workflow + "-unknown")
    assert wrong.returncode == 4
    assert json.loads(wrong.stdout)["error"] == "unknown_workflow"
    print(json.dumps({"first": a, "second": b, "wrong_id_exit": wrong.returncode}))
