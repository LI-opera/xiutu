"""Run one local API, Vite and document worker without the original machine registry."""
import argparse
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web-port", type=int, default=5215)
    parser.add_argument("--api-port", type=int, default=8215)
    args = parser.parse_args()
    for port in (args.web_port, args.api_port):
        if not 1024 <= port <= 65535:
            raise RuntimeError("Use a valid unprivileged local port")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", port))
    if args.web_port == args.api_port:
        raise RuntimeError("Web and API ports must differ")
    from app.config import load_settings
    from app.infrastructure.db import Database

    settings = load_settings(project_env=True)
    if settings.app_mode == "production":
        raise RuntimeError("This entry point is local development only")
    if not settings.database_url:
        raise RuntimeError("Configure a local DATABASE_URL first")
    database = Database(settings.database_url.get_secret_value())
    database.open()
    try:
        if not database.ready():
            raise RuntimeError("Database schema is not ready; initialize an empty workspace first")
    finally:
        database.close()
    vite = ROOT / "frontend/node_modules/vite/bin/vite.js"
    if not vite.is_file():
        raise RuntimeError("Run npm ci inside frontend first")
    env = os.environ.copy()
    env.update(
        PYTHONPATH=str(ROOT / "backend"),
        PYTHONDONTWRITEBYTECODE="1",
        XIUTU_LOAD_PROJECT_ENV="1",
        DATABASE_URL=settings.database_url.get_secret_value(),
        APP_ORIGIN=f"http://localhost:{args.web_port}",
        XIUTU_API_TARGET=f"http://127.0.0.1:{args.api_port}",
        DATA_PATH=str(settings.data_path),
        OPERATOR_TOKEN=(settings.operator_token.get_secret_value() if settings.operator_token else secrets.token_urlsafe(48)),
        LOCAL_DEV_AUTO_IDENTITY="1" if settings.local_dev_auto_identity else "0",
    )
    children = []
    def stop_requested(_signum, _frame):
        raise KeyboardInterrupt
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, stop_requested)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    commands = [
        [sys.executable, "-B", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.api_port)],
        ["node", str(vite), "--host", "localhost", "--port", str(args.web_port), "--strictPort"],
        [sys.executable, "-B", "-m", "app.worker"],
    ]
    try:
        for index, command in enumerate(commands):
            children.append(subprocess.Popen(command, cwd=ROOT / "frontend" if index == 1 else ROOT,
                                             env=env, creationflags=flags))
        import httpx

        deadline = time.monotonic() + 40
        ready = False
        with httpx.Client(trust_env=False, timeout=2) as client:
            while time.monotonic() < deadline:
                if any(child.poll() is not None for child in children):
                    raise RuntimeError("A managed development process exited")
                try:
                    ready = client.get(f"http://127.0.0.1:{args.api_port}/api/v2/health/ready").status_code == 200
                    ready = ready and client.get(f"http://localhost:{args.web_port}/workbench").status_code == 200
                    if ready:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.25)
        if not ready:
            raise RuntimeError("Bounded startup failed")
        print(f"Ready: http://localhost:{args.web_port}/workbench (Ctrl+C to stop this session)", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)


if __name__ == "__main__":
    main()
