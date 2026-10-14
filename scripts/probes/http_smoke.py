"""Bounded subprocess health probe. Only terminates the child it created."""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


def run_smoke(command, log_path, *, port=8020, timeout=15, expected_ready=503, env=None):
    # Refuse a known occupied endpoint before creating a process.
    with socket.socket() as sock:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(("127.0.0.1", port))
    with Path(log_path).open("x", encoding="utf-8") as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout
        last_error = "not attempted"
        try:
            with httpx.Client(trust_env=False) as client:
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(f"HTTP child exited early: {process.returncode}")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError(f"HTTP startup deadline exceeded ({last_error})")
                    try:
                        live = client.get(
                            f"http://127.0.0.1:{port}/api/v2/health/live", timeout=min(1, remaining)
                        )
                        break
                    except (httpx.ConnectError, httpx.ConnectTimeout) as error:
                        last_error = type(error).__name__
                        time.sleep(min(0.1, max(0, deadline - time.monotonic())))
                if process.poll() is not None:
                    raise RuntimeError("HTTP child exited while checking health")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("HTTP health deadline exceeded")
                ready = client.get(
                    f"http://127.0.0.1:{port}/api/v2/health/ready", timeout=min(3, remaining)
                )
            assert live.status_code == 200 and live.json() == {"status": "live"}
            assert ready.status_code == expected_ready
            assert ready.json()["model_verified"] is False
            result = {
                "pid": process.pid,
                "live": live.status_code,
                "ready": ready.status_code,
                "payload": ready.json(),
            }
            print(json.dumps(result))
            return result
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)


def main():
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"DATABASE_URL", "TEST_DATABASE_URL", "DEEPSEEK_API_KEY"}
    }
    run_smoke(
        [
            sys.executable,
            "-B",
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8020",
        ],
        sys.argv[1],
        env=env,
    )


if __name__ == "__main__":
    main()
