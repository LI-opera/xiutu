"""Owned WP-14 isolated browser instance. Never touches 5180/5196."""

import argparse
import ctypes
import json
import os
import secrets
import socket
import subprocess
import time
from ctypes import wintypes
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".local-data" / "wp14-frontend"
STATE = RUNTIME / "runtime.json"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
WEB_PORT, API_PORT = 5214, 8214


def process_stamp(pid: int, terminate: bool = False, expected: int | None = None):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    handle = kernel.OpenProcess(0x1000 | (1 if terminate else 0), False, pid)
    if not handle:
        return None
    try:
        values = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *[ctypes.byref(value) for value in values]):
            return None
        stamp = (values[0].dwHighDateTime << 32) | values[0].dwLowDateTime
        if terminate and stamp == expected:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10)
        return stamp
    finally:
        kernel.CloseHandle(handle)


def save(state):
    temporary = STATE.with_suffix(".new")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temporary.replace(STATE)


def environment(state):
    password = json.loads((ROOT / ".local-data" / "wp01-postgres.json").read_text(encoding="utf-8"))["password"]
    url = f"postgresql://xiutu:{quote(password, safe='')}@127.0.0.1:5433/{state['database']}"
    env = {key: value for key, value in os.environ.items() if not key.startswith(("PG", "DEEPSEEK", "LLM_", "MCP_", "XIUTU_", "TEST_DATABASE")) and key not in {"DATABASE_URL", "APP_MODE", "DATA_PATH", "RETRIEVAL_PROFILE", "OPERATOR_TOKEN", "OPERATOR_ID", "APP_ORIGIN"}}
    env.update(
        PYTHONPATH=str(ROOT / "backend"), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
        APP_MODE="test", RETRIEVAL_PROFILE="synthetic", DATABASE_URL=url, TEST_DATABASE_URL=url,
        DATA_PATH=state["storage"], OPERATOR_TOKEN=state["token"], OPERATOR_ID=state["actor"],
        APP_ORIGIN=f"http://localhost:{WEB_PORT}", TOOL_MODE="local", DEEPSEEK_API_KEY="",
        EMBEDDING_PROVIDER="local_e5",
        EMBEDDING_PATH=str(ROOT / ".local-data" / "models" / "multilingual-e5-small" / "614241f622f53c4eeff9890bdc4f31cfecc418b3"),
    )
    return env


def ensure_free(port):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))


def init():
    if STATE.exists():
        raise SystemExit("Existing WP-14 instance retained; use status/start.")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    state = {
        "database": "xiutu_test_wp14_" + uuid4().hex[:12],
        "storage": str(RUNTIME / ("storage-" + uuid4().hex)),
        "actor": str(uuid4()), "token": secrets.token_urlsafe(36), "processes": [],
    }
    inspect = json.loads(subprocess.check_output(["docker", "inspect", "xiutu-v5-postgres-1"], text=True))[0]
    assert inspect["State"]["Running"] and inspect["Config"]["Labels"]["com.docker.compose.project"] == "xiutu-v5"
    assert any(item["HostIp"] == "127.0.0.1" and item["HostPort"] == "5433" for item in inspect["NetworkSettings"]["Ports"]["5432/tcp"])
    env = environment(state)
    env["DATABASE_URL"] = env["DATABASE_URL"].rsplit("/", 1)[0] + "/xiutu_dev"
    log_path = RUNTIME / "init.log"
    with log_path.open("x", encoding="utf-8") as log:
        created = subprocess.run([str(PYTHON), "-B", "scripts/probes/prepare_database.py", "--name", state["database"]], cwd=ROOT, env=env, stdout=log, stderr=log)
        if created.returncode:
            raise SystemExit("Database creation failed; inspect private init.log.")
        migrated = subprocess.run([str(PYTHON), "-B", "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=environment(state), stdout=log, stderr=log)
        if migrated.returncode:
            raise SystemExit("Migration failed; isolated database retained.")
    save(state)
    (RUNTIME / "access.txt").write_text(state["token"], encoding="utf-8")
    print("Initialized isolated WP-14 instance; access token is in private access.txt.")


def start(state):
    if any(process_stamp(item["pid"]) == item["stamp"] for item in state["processes"]):
        raise SystemExit("Owned WP-14 processes already running.")
    ensure_free(WEB_PORT)
    ensure_free(API_PORT)
    env = environment(state)
    env["XIUTU_API_TARGET"] = f"http://127.0.0.1:{API_PORT}"
    commands = [
        ("api", [str(PYTHON), "-B", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(API_PORT), "--log-level", "warning"]),
        ("worker", [str(PYTHON), "-B", "-m", "app.worker"]),
        ("web", ["cmd.exe", "/d", "/s", "/c", "npm.cmd run dev -- --host localhost --port 5214 --strictPort"]),
    ]
    state["processes"] = []
    try:
        for label, command in commands:
            log = (RUNTIME / f"{label}-{uuid4().hex[:8]}.log").open("x", encoding="utf-8")
            cwd = ROOT / "frontend" if label == "web" else ROOT
            process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
            log.close()
            state["processes"].append(
                {"label": label, "pid": process.pid, "stamp": process_stamp(process.pid)}
            )
            save(state)
        import httpx
        deadline = time.monotonic() + 40
        with httpx.Client(trust_env=False, timeout=2) as client:
            while time.monotonic() < deadline:
                if any(process_stamp(item["pid"]) != item["stamp"] for item in state["processes"]):
                    raise RuntimeError("Owned process exited; inspect private logs.")
                try:
                    if client.get(f"http://127.0.0.1:{API_PORT}/api/v2/health/ready").status_code == 200 and client.get(f"http://localhost:{WEB_PORT}/workbench").status_code == 200:
                        break
                except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
                    pass
                time.sleep(0.3)
            else:
                raise RuntimeError("Bounded WP-14 startup failed.")
        print(f"WP-14 ready: http://localhost:{WEB_PORT}/workbench")
    except Exception:
        for item in reversed(state["processes"]):
            process_stamp(item["pid"], True, item["stamp"])
        state["processes"] = []
        save(state)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["init", "start", "stop", "status"])
    args = parser.parse_args()
    if args.action == "init":
        init()
        return
    state = json.loads(STATE.read_text(encoding="utf-8"))
    if args.action == "status":
        print(
            json.dumps(
                {
                    "url": f"http://localhost:{WEB_PORT}/workbench",
                    "database": state["database"],
                    "processes": [
                        {
                            "label": item["label"],
                            "alive": process_stamp(item["pid"]) == item["stamp"],
                        }
                        for item in state["processes"]
                    ],
                },
                indent=2,
            )
        )
        return
    if args.action == "stop":
        for item in reversed(state["processes"]):
            process_stamp(item["pid"], True, item["stamp"])
        state["processes"] = []
        save(state)
        print("Stopped owned WP-14 processes; database/storage retained.")
        return
    start(state)


if __name__ == "__main__":
    main()
