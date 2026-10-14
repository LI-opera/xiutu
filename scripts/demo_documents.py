"""Synthetic document demonstration; local isolated database only, no real-material approval."""

import argparse
import json
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from wp04_fixtures import MARKDOWN, metadata, pdf_bytes  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--demo-approve-synthetic",
        action="store_true",
        help="Record an explicitly synthetic demonstration review; never a professional source approval",
    )
    args = parser.parse_args()
    validate_target(os.environ["DATABASE_URL"], "test")
    work = Path(tempfile.mkdtemp(prefix="xiutu-wp04-demo-"))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    token = secrets.token_urlsafe(32)
    env = dict(
        os.environ,
        PYTHONPATH=str(ROOT / "backend"),
        PYTHONDONTWRITEBYTECODE="1",
        DATA_PATH=str(work / "storage"),
        OPERATOR_TOKEN=token,
        OPERATOR_ID=str(uuid4()),
        APP_ORIGIN=origin,
    )
    children = []
    print("SYNTHETIC ONLY — not repair evidence or professional review.", flush=True)
    print("Isolated artifacts:", work, flush=True)
    with (work / "process.log").open("x", encoding="utf-8") as log:
        try:
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
                    "--log-level",
                    "warning",
                ],
                env=env,
                cwd=ROOT,
                stdout=log,
                stderr=log,
            )
            children.append(api)
            with httpx.Client(base_url=origin, trust_env=False, timeout=30) as client:
                deadline = time.monotonic() + 15
                while True:
                    if api.poll() is not None:
                        raise RuntimeError("Owned demo API exited")
                    try:
                        if client.get("/api/v2/health/ready").status_code == 200:
                            break
                    except (httpx.ConnectError, httpx.ConnectTimeout):
                        pass
                    if time.monotonic() > deadline:
                        raise RuntimeError("Demo database/migration not ready")
                    time.sleep(0.1)
                login = client.post(
                    "/api/v2/auth/login", headers={"Origin": origin}, json={"token": token}
                )
                login.raise_for_status()
                headers = {"Origin": origin, "X-CSRF-Token": login.json()["csrf_token"]}
                records = []
                for name, data in [
                    ("synthetic.md", MARKDOWN.encode()),
                    ("synthetic.pdf", pdf_bytes(("text", "text"))),
                    ("scan.pdf", pdf_bytes(("scan",))),
                ]:
                    upload = client.post(
                        "/api/v2/documents",
                        headers=dict(headers, **{"Idempotency-Key": uuid4().hex}),
                        files={
                            "file": (name, data),
                            "metadata": (None, json.dumps(metadata(), ensure_ascii=False)),
                        },
                    )
                    upload.raise_for_status()
                    body = upload.json()
                    path = f"/api/v2/documents/{body['document_id']}/versions/{body['version_id']}"
                    command = "import os; from uuid import UUID; from app.infrastructure.job_store import JobStore; from app.worker import Worker; s=JobStore(os.environ['DATABASE_URL']); Worker(s).once(run_id=UUID(os.environ['DEMO_RUN_ID'])); s.close()"
                    worker = subprocess.Popen(
                        [sys.executable, "-B", "-c", command],
                        cwd=ROOT,
                        env=dict(env, DEMO_RUN_ID=body["run_id"]),
                        stdout=log,
                        stderr=log,
                    )
                    children.append(worker)
                    print(name, body, flush=True)
                    with client.stream(
                        "GET", "/api/v2/runs/" + body["run_id"] + "/events"
                    ) as stream:
                        stream.raise_for_status()
                        for line in stream.iter_lines():
                            if line.startswith(("id:", "event:")):
                                print(line, flush=True)
                    if worker.wait(timeout=10) != 0:
                        raise RuntimeError("Owned worker failed")
                    snapshot = client.get(path).json()
                    parts = client.get(path + "/chunks").json()
                    assert client.get(path + "/content").content == data
                    print(
                        "parse:",
                        snapshot["parse_status"],
                        "gaps:",
                        snapshot["page_issues"],
                        flush=True,
                    )
                    if parts["items"]:
                        print("first locator:", parts["items"][0]["locator_json"], flush=True)
                    if snapshot["parse_status"] == "review_pending":
                        approve = args.demo_approve_synthetic
                        if not approve:
                            approve = (
                                input("仅为合成演示记录一次人审（非真实资料专业审核）？输入 yes: ")
                                .strip()
                                .lower()
                                == "yes"
                            )
                        if approve:
                            review = client.post(
                                path + "/review",
                                headers=dict(headers, **{"Idempotency-Key": uuid4().hex}),
                                json=dict(
                                    decision="approved",
                                    scope={"model": "合成车型"},
                                    source_status="unknown",
                                    license_status="unknown",
                                    review_note="Synthetic demonstration only; no professional verification.",
                                ),
                            )
                            review.raise_for_status()
                            print("合成资料审核已记录；资格及索引状态:", review.json(), flush=True)
                    records.append(
                        dict(
                            **body,
                            parse_status=snapshot["parse_status"],
                            chunks=len(parts["items"]),
                        )
                    )
                (work / "result.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        finally:
            for child in children:
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=10)
    print("Demonstration finished; sources retained, only owned processes stopped.", flush=True)


if __name__ == "__main__":
    main()
