"""Owned DKVB trusted-protocol experience; never operates 5180/5196/5215."""

import argparse
import ctypes
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".local-data" / "dkvb-trusted-protocol-r1-final"
STATE = RUNTIME / "runtime.json"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
WEB_HOST, WEB_PORT, API_PORT = "127.0.0.1", 5225, 8225
BGE_PATH = Path(
    "E:/AI_Cache/huggingface/models--BAAI--bge-m3/"
    "snapshots/5617a9f61b028005a4858fdac845db406aefb181"
)


def process_stamp(pid: int, terminate: bool = False, expected: int | None = None):
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
    temporary = STATE.with_suffix(".new")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(STATE)


def environment(state):
    password = json.loads(
        (ROOT / ".local-data" / "wp01-postgres.json").read_text(encoding="utf-8")
    )["password"]
    database_url = (
        f"postgresql://xiutu:{quote(password, safe='')}@127.0.0.1:5433/{state['database']}"
    )
    excluded = {
        "DATABASE_URL", "APP_MODE", "DATA_PATH", "RETRIEVAL_PROFILE", "OPERATOR_TOKEN",
        "OPERATOR_ID", "APP_ORIGIN", "TEST_DATABASE_URL", "DEEPSEEK_API_KEY",
    }
    env = {key: value for key, value in os.environ.items()
           if key not in excluded and not key.startswith(("PG", "LLM_", "MCP_", "XIUTU_"))}
    env.update(
        PYTHONPATH=str(ROOT / "backend"), PYTHONIOENCODING="utf-8",
        PYTHONDONTWRITEBYTECODE="1", APP_MODE="test", RETRIEVAL_PROFILE="synthetic",
        DATABASE_URL=database_url, TEST_DATABASE_URL=database_url, DATA_PATH=state["storage"],
        OPERATOR_TOKEN=state["token"], OPERATOR_ID=state["actor"],
        APP_ORIGIN=f"http://{WEB_HOST}:{WEB_PORT}", TOOL_MODE="local",
        DEEPSEEK_API_KEY="", XIUTU_WP11_PAID="0",
        EMBEDDING_PROVIDER="local_bge_m3", EMBEDDING_MODEL="BAAI/bge-m3",
        EMBEDDING_REVISION="5617a9f61b028005a4858fdac845db406aefb181",
        EMBEDDING_DIMENSION="1024", EMBEDDING_MODEL_PATH=str(BGE_PATH),
    )
    return env


def ensure_free(port):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))


def init():
    if STATE.exists():
        raise SystemExit("Existing protocol experience retained; use status/start.")
    if not BGE_PATH.is_dir():
        raise SystemExit("Authorized local BGE snapshot is unavailable")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    state = {
        "database": "xiutu_test_dkvb_protocol_" + uuid4().hex[:12],
        "storage": str(RUNTIME / ("storage-" + uuid4().hex)),
        "actor": str(uuid4()), "token": secrets.token_urlsafe(36),
        "processes": [], "cases": {},
    }
    env = environment(state)
    env["DATABASE_URL"] = env["DATABASE_URL"].rsplit("/", 1)[0] + "/xiutu_dev"
    init_log = RUNTIME / f"init-{uuid4().hex[:8]}.log"
    with init_log.open("x", encoding="utf-8") as log:
        commands = [
            [str(PYTHON), "-B", "scripts/probes/prepare_database.py", "--name", state["database"]],
            [str(PYTHON), "-B", "-m", "alembic", "upgrade", "head"],
            [str(PYTHON), "-B", "scripts/setup_graph_checkpoint.py"],
        ]
        for index, command in enumerate(commands):
            command_env = env if index == 0 else environment(state)
            result = subprocess.run(command, cwd=ROOT, env=command_env, stdout=log, stderr=log)
            if result.returncode:
                raise SystemExit("Isolated database initialization failed; inspect private init.log")
    Path(state["storage"]).mkdir(parents=True, exist_ok=True)
    save(state)
    (RUNTIME / "access.txt").write_text(state["token"], encoding="utf-8")
    print("Initialized isolated trusted-protocol experience; token is in private access.txt")


def start(state):
    if any(process_stamp(item["pid"]) == item["stamp"] for item in state["processes"]):
        raise SystemExit("Owned protocol experience is already running")
    ensure_free(WEB_PORT)
    ensure_free(API_PORT)
    env = environment(state)
    env["XIUTU_API_TARGET"] = f"http://127.0.0.1:{API_PORT}"
    commands = [
        ("api", [str(PYTHON), "-B", "-m", "uvicorn", "app.main:app", "--host",
                 "127.0.0.1", "--port", str(API_PORT), "--log-level", "warning"], ROOT),
        ("worker", [str(PYTHON), "-B", "-m", "app.worker"], ROOT),
        ("web", ["cmd.exe", "/d", "/s", "/c",
                 f"npm.cmd run dev -- --host {WEB_HOST} --port {WEB_PORT} --strictPort"],
         ROOT / "frontend"),
    ]
    state["processes"] = []
    try:
        for label, command, cwd in commands:
            log = (RUNTIME / f"{label}-{uuid4().hex[:8]}.log").open("x", encoding="utf-8")
            process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=log,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
            log.close()
            state["processes"].append(
                {"label": label, "pid": process.pid, "stamp": process_stamp(process.pid)}
            )
            save(state)
        deadline = time.monotonic() + 90
        with httpx.Client(trust_env=False, timeout=2) as client:
            while time.monotonic() < deadline:
                if any(process_stamp(item["pid"]) != item["stamp"] for item in state["processes"]):
                    raise RuntimeError("Owned process exited; inspect private logs")
                try:
                    api_ready = client.get(
                        f"http://127.0.0.1:{API_PORT}/api/v2/health/ready"
                    ).status_code == 200
                    web_ready = client.get(
                        f"http://{WEB_HOST}:{WEB_PORT}/workbench"
                    ).status_code == 200
                    if api_ready and web_ready:
                        print(f"Protocol experience ready: http://{WEB_HOST}:{WEB_PORT}/workbench")
                        return
                except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
                    pass
                time.sleep(0.3)
        raise RuntimeError("Bounded protocol experience startup failed")
    except Exception:
        for item in reversed(state["processes"]):
            process_stamp(item["pid"], True, item["stamp"])
        state["processes"] = []
        save(state)
        raise


def wait_for(client, path, predicate, seconds=180):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        response = client.get(path)
        if response.status_code == 200:
            last = response.json()
            if predicate(last):
                return last
        time.sleep(0.4)
    raise RuntimeError(f"Bounded wait expired for {path}; last state was {last}")


def seed(state):
    if state["cases"]:
        print("Protocol cases already seeded; no duplicate versions or cases created")
        return
    sys.path.insert(0, str(ROOT / "backend"))
    from app.agents.trusted_protocol import PROFILE, build_demo_candidates
    from app.config import Settings
    from app.domain.measurements import BindEvidence
    from app.infrastructure.job_store import JobStore
    from app.infrastructure.orm import chunks
    from app.services.evidence_service import EvidenceService
    from app.services.protocol_service import ProtocolService

    env = environment(state)
    settings = Settings(**{key.lower(): value for key, value in {
        "APP_MODE": "test", "RETRIEVAL_PROFILE": "synthetic",
        "DATABASE_URL": env["DATABASE_URL"], "DATA_PATH": env["DATA_PATH"],
        "EMBEDDING_PROVIDER": "local_bge_m3", "EMBEDDING_MODEL_PATH": str(BGE_PATH),
        "EMBEDDING_MODEL": "BAAI/bge-m3",
        "EMBEDDING_REVISION": "5617a9f61b028005a4858fdac845db406aefb181",
        "EMBEDDING_DIMENSION": 1024,
    }.items()})
    actor = UUID(state["actor"])
    origin = f"http://{WEB_HOST}:{WEB_PORT}"
    base = f"http://127.0.0.1:{API_PORT}"
    source = ROOT / "tests" / "fixtures" / "diagnosis-slice" / "dkvb-guided.md"
    scope = {"model": PROFILE["model"], "year_from": PROFILE["year"],
             "year_to": PROFILE["year"], "engine_family": PROFILE["engine_family"],
             "engine_code": PROFILE["engine_code"]}
    metadata = {"title": "DKVB/P0299可信诊断协议演示资料",
                "source_kind": "synthetic_fixture",
                "source_reference": "versioned local DEMO fixture; not a vehicle manual",
                "source_status": "unknown", "license_status": "unknown",
                "scope": scope, "synthetic": True}
    with httpx.Client(base_url=base, trust_env=False, timeout=30) as client:
        login = client.post("/api/v2/auth/login", headers={"Origin": origin},
                            json={"token": state["token"]})
        login.raise_for_status()
        headers = {"Origin": origin, "X-CSRF-Token": login.json()["csrf_token"]}
        response = client.post("/api/v2/documents",
            headers={**headers, "Idempotency-Key": uuid4().hex},
            files={"file": (source.name, source.read_bytes(), "text/markdown"),
                   "metadata": (None, json.dumps(metadata, ensure_ascii=False), "application/json")})
        response.raise_for_status()
        document = response.json()
        version_path = (f"/api/v2/documents/{document['document_id']}/versions/"
                        f"{document['version_id']}")
        wait_for(client, version_path,
                 lambda item: item.get("parse_status") == "review_pending")
        review = client.post(version_path + "/review",
            headers={**headers, "Idempotency-Key": uuid4().hex},
            json={"decision": "approved", "scope": scope, "source_status": "unknown",
                  "license_status": "unknown",
                  "review_note": "Synthetic protocol demo only; formal_usable=false"})
        review.raise_for_status()
        version = wait_for(client, version_path,
                           lambda item: bool(item.get("active_index_id")))
        index_id = UUID(version["active_index_id"])
        version_id = UUID(document["version_id"])
        store = JobStore(env["DATABASE_URL"], lease_seconds=60)
        evidence_service = EvidenceService(store.engine, settings)
        protocol_service = ProtocolService(store.engine, settings)
        with store.engine.connect() as connection:
            rows = connection.execute(select(chunks).where(
                chunks.c.document_version_id == version_id)).mappings().all()

        def make_case(label):
            created = client.post("/api/v2/cases",
                headers={**headers, "Idempotency-Key": uuid4().hex},
                json={"vehicle": PROFILE,
                      "fault_description": f"【DEMO】探岳 DKVB 加速无力，报码 P0299（{label}）",
                      "fault_codes": ["P0299"]})
            created.raise_for_status()
            case = created.json()

            def cite(text):
                row = next(item for item in rows if text in item["text"])
                start_offset = row["text"].index(text)
                _, bound = evidence_service.bind(actor, UUID(case["id"]), BindEvidence(
                    chunk_id=row["id"], document_version_id=version_id, index_id=index_id,
                    start=start_offset, end=start_offset + len(text), quote=text), uuid4().hex)
                return {"text": text, "references": [{"evidence_id": bound["evidence_id"],
                                                       "document_version_id": str(version_id)}]}

            protocol_service.register(actor, UUID(case["id"]), build_demo_candidates(cite))
            started = client.post(f"/api/v2/cases/{case['id']}/diagnosis/runs",
                headers={**headers, "Idempotency-Key": uuid4().hex},
                json={"expected_revision": case["revision"]})
            started.raise_for_status()
            wait_for(client, f"/api/v2/cases/{case['id']}/diagnosis",
                     lambda item: (item.get("current_step") or {}).get("validation", {})
                     .get("protocol", {}).get("next_check_id") == "CHK-05")
            return case["id"]

        for label in ("用户体验", "浏览器路径A", "浏览器路径B", "浏览器路径C"):
            state["cases"][label] = make_case(label)
        state["document"] = document
        save(state)
    print("Seeded one synthetic BGE index and four fresh trusted-protocol cases")


def probe(state):
    """Print bounded, non-secret evidence for the persistent experience."""
    sys.path.insert(0, str(ROOT / "backend"))
    from app.infrastructure.job_store import JobStore
    from app.infrastructure.orm import diagnosis_protocol_bindings, index_versions, tool_executions

    env = environment(state)
    origin = f"http://{WEB_HOST}:{WEB_PORT}"
    with httpx.Client(base_url=f"http://127.0.0.1:{API_PORT}", trust_env=False,
                      timeout=10) as client:
        login = client.post("/api/v2/auth/login", headers={"Origin": origin},
                            json={"token": state["token"]})
        login.raise_for_status()
        cases_summary = {}
        for label, case_id in state["cases"].items():
            diagnosis = client.get(f"/api/v2/cases/{case_id}/diagnosis").json()
            observations = client.get(f"/api/v2/cases/{case_id}/observations").json()
            protocol = ((diagnosis.get("current_step") or {}).get("validation") or {}).get(
                "protocol") or {}
            cases_summary[label] = {
                "next_check_id": protocol.get("next_check_id"),
                "decision": protocol.get("decision"),
                "observation_count": len(observations.get("items", [])),
            }
    store = JobStore(env["DATABASE_URL"], lease_seconds=60)
    with store.engine.connect() as connection:
        index = connection.execute(select(index_versions).where(
            index_versions.c.document_version_id == UUID(state["document"]["version_id"]),
            index_versions.c.status == "ready")).mappings().one()
        bindings = connection.execute(select(diagnosis_protocol_bindings.c.id)).all()
        tool_rows = connection.execute(select(tool_executions.c.id)).all()
    print(json.dumps({
        "index": {"status": index["status"], "dimension": index["dimension"],
                  "provider": index["config_json"].get("provider"),
                  "model": index["config_json"].get("model")},
        "protocol_bindings": len(bindings), "tool_executions": len(tool_rows),
        "cases": cases_summary,
    }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["init", "start", "seed", "probe", "rotate-token", "stop", "status"])
    args = parser.parse_args()
    if args.action == "init":
        init()
        return
    state = json.loads(STATE.read_text(encoding="utf-8"))
    if args.action == "start":
        start(state)
    elif args.action == "seed":
        seed(state)
    elif args.action == "probe":
        probe(state)
    elif args.action == "rotate-token":
        if any(process_stamp(item["pid"]) == item["stamp"] for item in state["processes"]):
            raise SystemExit("Stop the owned instance before rotating its token")
        state["token"] = secrets.token_urlsafe(36)
        save(state)
        (RUNTIME / "access.txt").write_text(state["token"], encoding="utf-8")
        print("Rotated private access token without displaying it")
    elif args.action == "stop":
        for item in reversed(state.get("processes", [])):
            process_stamp(item["pid"], True, item["stamp"])
        state["processes"] = []
        save(state)
        print("Stopped owned protocol processes; database and storage retained")
    else:
        user_case = state.get("cases", {}).get("用户体验")
        print(json.dumps({
            "url": (f"http://{WEB_HOST}:{WEB_PORT}/workbench/{user_case}"
                    if user_case else f"http://{WEB_HOST}:{WEB_PORT}/workbench"),
            "database": state["database"], "seeded": bool(state.get("cases")),
            "processes": [{"label": item["label"],
                           "alive": process_stamp(item["pid"]) == item["stamp"]}
                          for item in state.get("processes", [])],
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
