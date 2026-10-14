import importlib.util
import socket
import sys
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("http_smoke", ROOT / "scripts/probes/http_smoke.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_delayed_listener(tmp_path):
    port = free_port()
    code = f"import time;time.sleep(2);import uvicorn;uvicorn.run('app.main:app',host='127.0.0.1',port={port})"
    import os

    env = dict(os.environ)
    for key in ["DATABASE_URL", "TEST_DATABASE_URL", "DEEPSEEK_API_KEY"]:
        env.pop(key, None)
    result = smoke.run_smoke(
        [sys.executable, "-B", "-c", code], tmp_path / "delayed.txt", port=port, timeout=15, env=env
    )
    assert result["live"] == 200 and result["ready"] == 503


def test_never_listens_is_bounded(tmp_path):
    start = time.monotonic()
    with pytest.raises(TimeoutError, match="deadline"):
        smoke.run_smoke(
            [sys.executable, "-c", "import time;time.sleep(30)"],
            tmp_path / "never.txt",
            port=free_port(),
            timeout=2,
        )
    assert time.monotonic() - start < 6


def test_early_exit(tmp_path):
    start = time.monotonic()
    with pytest.raises(RuntimeError, match="exited"):
        smoke.run_smoke(
            [sys.executable, "-c", "raise SystemExit(7)"],
            tmp_path / "exit.txt",
            port=free_port(),
            timeout=10,
        )
    assert time.monotonic() - start < 5


def test_occupied_port_preserved(tmp_path, monkeypatch):
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        launch = Mock(side_effect=AssertionError("Do not launch on an occupied port"))
        monkeypatch.setattr(smoke.subprocess, "Popen", launch)
        with pytest.raises(OSError):
            smoke.run_smoke([sys.executable], tmp_path / "occupied.txt", port=port)
        launch.assert_not_called()
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            connection, _ = server.accept()
            connection.close()
