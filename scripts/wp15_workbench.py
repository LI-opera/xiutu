"""Owned WP-15 synthetic browser instance; never operates 5180 or 5196."""

import argparse
import ctypes
import json
import os
import socket
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".local-data" / "wp15-workbench"
STATE = RUNTIME / "runtime.json"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
WEB_PORT, API_PORT = 5215, 8215
TEST_TOKEN = "wp15-isolated-synthetic-browser-token-only"


def stamp(pid: int, terminate: bool = False, expected: int | None = None):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    handle = kernel.OpenProcess(0x1000 | (1 if terminate else 0), False, pid)
    if not handle:
        return None
    try:
        values = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *[ctypes.byref(value) for value in values]):
            return None
        created = (values[0].dwHighDateTime << 32) | values[0].dwLowDateTime
        if terminate and created == expected:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10
            )
        return created
    finally:
        kernel.CloseHandle(handle)


def save(state):
    temp = STATE.with_suffix(".new")
    temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temp.replace(STATE)


EMBEDDING_FIELDS = ("embedding_provider", "embedding_path", "embedding_model_path", "embedding_model",
                    "embedding_revision", "embedding_dimension")


def embedding_environment(settings):
    """The project's local embedding choice (.env), passed to the launched API and worker.

    The launched processes run in test mode and do not read .env, so without this they fall
    back to the default E5 model while scripts and evaluations use the configured one.
    """
    result = {}
    for name in EMBEDDING_FIELDS:
        value = getattr(settings, name, None)
        if value is not None:
            result[name.upper()] = str(value)
    return result


def environment(state, *, real_case_id=None, real_revision=None, c05_key=None,
                real_output_tokens=4096, local_auto_identity=True, real_context_hash=None,
                real_prompt_version=None, ranking_real_case_id=None,
                ranking_local_testing=True):
    password = json.loads(
        (ROOT / ".local-data" / "wp01-postgres.json").read_text(encoding="utf-8")
    )["password"]
    url = f"postgresql://xiutu:{quote(password, safe='')}@127.0.0.1:5433/{state['database']}"
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("PG", "DEEPSEEK", "LLM_", "MCP_", "XIUTU_", "TEST_DATABASE"))
        and key
        not in {
            "DATABASE_URL",
            "APP_MODE",
            "DATA_PATH",
            "RETRIEVAL_PROFILE",
            "OPERATOR_TOKEN",
            "OPERATOR_ID",
            "APP_ORIGIN",
            "LOCAL_DEV_AUTO_IDENTITY",
            "CASE_ANALYSIS_MAX_OUTPUT_TOKENS",
        }
    }
    env.update(
        PYTHONPATH=str(ROOT / "backend"),
        PYTHONDONTWRITEBYTECODE="1",
        APP_MODE="test",
        RETRIEVAL_PROFILE="synthetic",
        DATABASE_URL=url,
        TEST_DATABASE_URL=url,
        DATA_PATH=state["storage"],
        OPERATOR_TOKEN=TEST_TOKEN,
        OPERATOR_ID=state["actor"],
        APP_ORIGIN=f"http://localhost:{WEB_PORT}",
        # Loopback login is independent from the separately bounded paid-call gate.
        LOCAL_DEV_AUTO_IDENTITY="1" if local_auto_identity else "0",
        TOOL_MODE="local",
        DEEPSEEK_API_KEY="",
        XIUTU_C01_MODEL_MODE="stub",
        XIUTU_C01_REAL_AUTHORIZED="0",
        XIUTU_WP11_PAID="0",
        CASE_ANALYSIS_MAX_OUTPUT_TOKENS="1536",
    )
    sys.path.insert(0, str(ROOT / "backend"))
    from app.config import load_settings

    env.update(embedding_environment(load_settings(project_env=True, embedding_local_files_only=True)))
    if real_case_id is None and (ranking_real_case_id is not None or ranking_local_testing):
        ranking_case_id = str(UUID(ranking_real_case_id)) if ranking_real_case_id is not None else None
        sys.path.insert(0, str(ROOT / "backend"))
        from app.config import load_settings

        settings = load_settings(project_env=True, embedding_local_files_only=True)
        if (not settings.deepseek_api_key or settings.llm_provider != "deepseek"
                or settings.deepseek_base_url.rstrip("/") not in
                {"https://api.deepseek.com", "https://api.deepseek.com/v1"}):
            raise RuntimeError("AREA_RANKING_MODEL_CONFIG_UNAVAILABLE")
        env.update(
            DEEPSEEK_API_KEY=settings.deepseek_api_key.get_secret_value(),
            DEEPSEEK_MODEL="deepseek-flash",
            DEEPSEEK_BASE_URL=settings.deepseek_base_url,
            XIUTU_AREA_RANKING_PAID_AUTHORIZED="1",
        )
        if ranking_case_id is not None:
            env["XIUTU_AREA_RANKING_ALLOWED_CASE_ID"] = ranking_case_id
        else:
            env["XIUTU_AREA_RANKING_LOCAL_TESTING"] = "1"
    if real_case_id is not None:
        if real_revision is None or real_revision < 1:
            raise ValueError("C03 requires a positive reviewed revision")
        if real_output_tokens not in {4096, 8192}:
            raise ValueError("Real output budget must be an explicitly reviewed 4096 or 8192")
        case_id = str(UUID(real_case_id))
        # Read the existing project dotenv through the application's validated
        # loader. Its unrelated legacy embedding flag is overridden in memory;
        # neither the key nor the selected model is written back to .env/state.
        sys.path.insert(0, str(ROOT / "backend"))
        from app.config import load_settings

        settings = load_settings(project_env=True, embedding_local_files_only=True)
        if (not settings.deepseek_api_key or settings.llm_provider != "deepseek"
                or settings.deepseek_base_url.rstrip("/") not in
                {"https://api.deepseek.com", "https://api.deepseek.com/v1"}):
            raise RuntimeError("C03_MODEL_CONFIG_UNAVAILABLE")
        env.update(
            DEEPSEEK_API_KEY=settings.deepseek_api_key.get_secret_value(),
            DEEPSEEK_MODEL="deepseek-flash",
            DEEPSEEK_BASE_URL=settings.deepseek_base_url,
            XIUTU_C01_MODEL_MODE="real",
            XIUTU_C01_REAL_AUTHORIZED="1",
            CASE_ANALYSIS_MAX_OUTPUT_TOKENS=str(real_output_tokens),
        )
        if c05_key is not None:
            if not c05_key.startswith(f"c05-{case_id}-r{real_revision}-"):
                raise ValueError("C05 key must identify the reviewed case and revision")
            env.update(
                XIUTU_C05_ALLOWED_CASE_ID=case_id,
                XIUTU_C05_ALLOWED_REVISION=str(real_revision),
                XIUTU_C05_ALLOWED_KEY=c05_key,
            )
            if real_context_hash is not None:
                if len(real_context_hash) != 64 or any(ch not in "0123456789abcdef" for ch in real_context_hash):
                    raise ValueError("Expected a reviewed SHA-256 source context")
                env["XIUTU_C19_ALLOWED_CONTEXT_HASH"] = real_context_hash
            if real_prompt_version is not None:
                from app.services.case_analysis_context import PROMPT_VERSION
                if not real_context_hash or real_prompt_version != PROMPT_VERSION:
                    raise ValueError("Version-bound grant requires current prompt and source hash")
                env["XIUTU_C19_ALLOWED_PROMPT_VERSION"] = real_prompt_version
        else:
            env.update(
                XIUTU_C03_ALLOWED_CASE_ID=case_id,
                XIUTU_C03_ALLOWED_REVISION=str(real_revision),
            )
    return env


def free(port):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))


def start(state, *, real_case_id=None, real_revision=None, c05_key=None,
          real_output_tokens=4096, local_auto_identity=True, real_context_hash=None,
          real_prompt_version=None, ranking_real_case_id=None,
          ranking_local_testing=True):
    if any(stamp(item["pid"]) == item["stamp"] for item in state.get("processes", [])):
        raise SystemExit("Owned WP-15 processes already running")
    free(WEB_PORT)
    free(API_PORT)
    env = environment(state, real_case_id=real_case_id, real_revision=real_revision,
                      c05_key=c05_key, real_output_tokens=real_output_tokens,
                      local_auto_identity=local_auto_identity, real_context_hash=real_context_hash,
                      real_prompt_version=real_prompt_version,
                      ranking_real_case_id=ranking_real_case_id,
                      ranking_local_testing=ranking_local_testing)
    ranking_enabled = real_case_id is None and (ranking_real_case_id is not None or ranking_local_testing)
    env["XIUTU_API_TARGET"] = f"http://127.0.0.1:{API_PORT}"
    commands = [
        (
            "api",
            [
                str(PYTHON),
                "-B",
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(API_PORT),
                "--log-level",
                "warning",
            ],
            ROOT,
        ),
        (
            "web",
            [
                "cmd.exe",
                "/d",
                "/s",
                "/c",
                f"npm.cmd run dev -- --host localhost --port {WEB_PORT} --strictPort",
            ],
            ROOT / "frontend",
        ),
        (
            "worker",
            [str(PYTHON), "-B", "-m", "app.worker"],
            ROOT,
        ),
    ]
    state["processes"] = []
    try:
        for label, command, cwd in commands:
            process_env = env
            if ranking_enabled and label != "api":
                process_env = env.copy()
                for name in ("DEEPSEEK_API_KEY", "XIUTU_AREA_RANKING_PAID_AUTHORIZED",
                             "XIUTU_AREA_RANKING_ALLOWED_CASE_ID", "XIUTU_AREA_RANKING_LOCAL_TESTING"):
                    process_env.pop(name, None)
            log = (RUNTIME / f"{label}.log").open("w", encoding="utf-8")
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=process_env,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            log.close()
            state["processes"].append(
                {"label": label, "pid": process.pid, "stamp": stamp(process.pid)}
            )
            save(state)
        import httpx

        deadline = time.monotonic() + 40
        with httpx.Client(trust_env=False, timeout=2) as client:
            while time.monotonic() < deadline:
                if any(stamp(item["pid"]) != item["stamp"] for item in state["processes"]):
                    raise RuntimeError("Owned process exited")
                try:
                    if (
                        client.get(f"http://127.0.0.1:{API_PORT}/api/v2/health/ready").status_code
                        == 200
                        and client.get(f"http://localhost:{WEB_PORT}/workbench").status_code == 200
                    ):
                        print(
                            f"WP-15 ready: http://localhost:{WEB_PORT}/workbench/{state['case_id']}"
                        )
                        return
                except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
                    pass
                time.sleep(0.25)
        raise RuntimeError("Bounded startup failed")
    except Exception:
        for item in reversed(state["processes"]):
            stamp(item["pid"], True, item["stamp"])
        state["processes"] = []
        save(state)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "status"])
    parser.add_argument("--c03-real-once-case")
    parser.add_argument("--c03-revision", type=int)
    parser.add_argument("--c05-real-once-case")
    parser.add_argument("--c05-revision", type=int)
    parser.add_argument("--c05-key")
    parser.add_argument("--real-output-tokens", type=int, choices=[4096, 8192], default=4096)
    parser.add_argument("--real-context-hash", help="Explicit single attempt for a reviewed new source version")
    parser.add_argument("--real-prompt-version", help="Scope a reviewed retry to the current prompt and contract")
    parser.add_argument("--manual-login", action="store_true",
                        help="Disable loopback auto identity for this local start")
    parser.add_argument("--area-ranking-real-once-case",
                        help="Open one paid semantic area ranking attempt for this exact case")
    parser.add_argument("--no-area-ranking-real", action="store_true",
                        help="Disable the default local paid area-ranking option")
    args = parser.parse_args()
    state = json.loads(STATE.read_text(encoding="utf-8"))
    if args.action == "start":
        if args.real_context_hash and not args.c05_real_once_case:
            raise SystemExit("A context grant requires the bounded C05 case/revision/key")
        if args.c05_real_once_case and args.c03_real_once_case:
            raise SystemExit("Choose only one real-call window")
        if args.area_ranking_real_once_case and (args.c05_real_once_case or args.c03_real_once_case):
            raise SystemExit("Choose only one real-call window")
        if args.area_ranking_real_once_case and args.no_area_ranking_real:
            raise SystemExit("Choose either exact-case ranking or disabled ranking")
        if args.c05_real_once_case and (args.c05_revision is None or not args.c05_key):
            raise SystemExit("C05 requires reviewed revision and exact idempotency key")
        start(state, real_case_id=args.c05_real_once_case or args.c03_real_once_case,
              real_revision=args.c05_revision if args.c05_real_once_case else args.c03_revision,
              c05_key=args.c05_key, real_output_tokens=args.real_output_tokens,
              local_auto_identity=not args.manual_login, real_context_hash=args.real_context_hash,
              real_prompt_version=args.real_prompt_version,
              ranking_real_case_id=args.area_ranking_real_once_case,
              ranking_local_testing=not args.no_area_ranking_real)
    elif args.action == "stop":
        for item in reversed(state.get("processes", [])):
            stamp(item["pid"], True, item["stamp"])
        state["processes"] = []
        save(state)
        print("Stopped owned WP-15 browser processes")
    else:
        print(
            json.dumps(
                {
                    "url": f"http://localhost:{WEB_PORT}/workbench/{state['case_id']}",
                    "processes": [
                        {"label": item["label"], "alive": stamp(item["pid"]) == item["stamp"]}
                        for item in state.get("processes", [])
                    ],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
