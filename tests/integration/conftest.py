"""Shared fixture: the real API in its own process, logged in, on the isolated test database."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from app.infrastructure.job_store import JobStore

ROOT = Path(__file__).resolve().parents[2]


def wait(fn, seconds=15):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        result = fn()
        if result:
            return result
        time.sleep(0.03)
    raise AssertionError("Bounded wait expired")


@pytest.fixture
def api_rig(database_url, tmp_path):
    class Rig:
        def __init__(self):
            self.store = JobStore(database_url, lease_seconds=2)
            self.processes = []
            self.clients = []
            self.env = dict(
                os.environ,
                DATABASE_URL=str(database_url),
                TEST_DATABASE_URL=str(database_url),
                DATA_PATH=str(tmp_path / "storage"),
                PYTHONPATH=str(ROOT / "backend"),
                PYTHONDONTWRITEBYTECODE="1",
                PYTHONIOENCODING="utf-8",
            )
            self.client, self.headers, self.actor = self.api()

        def api(self):
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            origin = f"http://127.0.0.1:{port}"
            actor = uuid4()
            token = "synthetic-api-rig-" + uuid4().hex
            env = dict(self.env, OPERATOR_TOKEN=token, OPERATOR_ID=str(actor), APP_ORIGIN=origin)
            log = (tmp_path / (str(actor) + ".api.log")).open("x", encoding="utf-8")
            proc = subprocess.Popen(
                [sys.executable, "-B", "-m", "uvicorn", "app.main:app",
                 "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
                env=env, cwd=ROOT, stdout=log, stderr=log,
            )
            self.processes.append((proc, log))
            client = httpx.Client(base_url=origin, trust_env=False, timeout=20)
            self.clients.append(client)

            def started():
                assert proc.poll() is None, "Owned API child exited"
                try:
                    return client.get("/api/v2/health/live").status_code == 200
                except (httpx.ConnectError, httpx.ConnectTimeout):
                    return False

            wait(started)
            response = client.post(
                "/api/v2/auth/login", headers={"Origin": origin}, json={"token": token}
            )
            assert response.status_code == 200
            headers = {"Origin": origin, "X-CSRF-Token": response.json()["csrf_token"]}
            assert client.get("/api/v2/health/ready").status_code == 200
            return client, headers, actor

    rig = Rig()
    yield rig
    for c in rig.clients:
        c.close()
    for proc, log in rig.processes:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
        log.close()
    rig.store.close()
    # Never print sensitive input; assert it is absent from service output.
    for log in tmp_path.glob("*.api.log"):
        raw = log.read_text(encoding="utf-8")
        assert "synthetic-api-rig-" not in raw and "X-CSRF" not in raw
