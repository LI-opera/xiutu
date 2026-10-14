"""One local demonstration: synthetic task -> HTTP/SSE -> cancellation.
Requires DATABASE_URL pointing to a migrated, isolated xiutu_test_* database.
Never changes credentials, existing services or databases.
"""

import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import httpx
from app.infrastructure.db_target import validate_target
from app.infrastructure.uow import make_engine
from app.services.run_service import RunService


def main():
    url = os.environ["DATABASE_URL"]
    validate_target(url, "test")
    root = Path(__file__).resolve().parents[1]
    owner, token = uuid4(), secrets.token_urlsafe(32)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    env = dict(
        os.environ,
        PYTHONPATH=str(root / "backend"),
        PYTHONDONTWRITEBYTECODE="1",
        OPERATOR_TOKEN=token,
        OPERATOR_ID=str(owner),
        APP_ORIGIN=origin,
    )
    engine = make_engine(url)
    children = []
    try:
        temp = tempfile.mkdtemp(prefix="xiutu-wp03-demo-")
        with (Path(temp) / "process.log").open("w", encoding="utf-8") as log:
            api = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=root,
                env=env,
                stdout=log,
                stderr=log,
            )
            children.append(api)
            with httpx.Client(base_url=origin, timeout=25) as client:
                deadline = time.monotonic() + 15
                while True:
                    if api.poll() is not None:
                        raise RuntimeError("Own demonstration API exited")
                    try:
                        if client.get("/api/v2/health/ready").status_code == 200:
                            break
                    except (httpx.ConnectError, httpx.ConnectTimeout):
                        pass
                    if time.monotonic() > deadline:
                        raise RuntimeError("Demonstration API not ready")
                    time.sleep(0.1)
                auth = client.post(
                    "/api/v2/auth/login", headers={"Origin": origin}, json={"token": token}
                )
                auth.raise_for_status()
                headers = {
                    "Origin": origin,
                    "X-CSRF-Token": auth.json()["csrf_token"],
                    "Idempotency-Key": uuid4().hex,
                }
                _, body = RunService(engine).submit_no_op(owner, {"seconds": 20}, uuid4().hex)
                run_id = body["run_id"]
                print("Synthetic no_op only; run_id:", run_id, flush=True)
                print("Initial:", client.get(f"/api/v2/runs/{run_id}").json()["status"], flush=True)
                command = "import os; from uuid import UUID; from app.infrastructure.job_store import JobStore; from app.worker import Worker; s=JobStore(os.environ['DATABASE_URL']); Worker(s).once(run_id=UUID(os.environ['DEMO_RUN_ID'])); s.close()"
                worker = subprocess.Popen(
                    [sys.executable, "-B", "-c", command],
                    cwd=root,
                    env=dict(env, DEMO_RUN_ID=run_id),
                    stdout=log,
                    stderr=log,
                )
                children.append(worker)
                deadline = time.monotonic() + 10
                while client.get(f"/api/v2/runs/{run_id}").json()["status"] != "running":
                    if worker.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("Demonstration worker did not start")
                    time.sleep(0.1)
                cancel = client.post(f"/api/v2/runs/{run_id}/cancel", headers=headers)
                cancel.raise_for_status()
                print("Cancel:", cancel.json()["status"], flush=True)
                with client.stream("GET", f"/api/v2/runs/{run_id}/events") as stream:
                    stream.raise_for_status()
                    for line in stream.iter_lines():
                        if line.startswith(("id:", "event:")):
                            print(line, flush=True)
                worker.wait(timeout=10)
                final = client.get(f"/api/v2/runs/{run_id}").json()["status"]
                assert final == "cancelled"
                print("Final:", final, "(not diagnosis or ingestion)", flush=True)
    finally:
        for proc in children:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=10)
        engine.dispose()


if __name__ == "__main__":
    main()
