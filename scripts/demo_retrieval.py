"""SYNTHETIC ONLY: isolated upload/parse/review/index/search demonstration and evaluation."""

import argparse
import hashlib
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
from app.config import Settings
from app.domain.retrieval import SearchInput
from app.infrastructure.db_target import validate_target
from app.infrastructure.uow import make_engine
from app.retrieval.service import RetrievalService

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing existing output")
    url = os.environ["DATABASE_URL"]
    validate_target(url, "test")
    fixture = ROOT / "evals/retrieval-synthetic-v1.json"
    frozen = json.loads(fixture.read_text("utf-8"))
    digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
    expected = "29ab9e0e06c63d77340fc5880a4a7e18ca5808961db2b0b7c59bfd3d08c1d1b1"
    if digest != expected:
        raise SystemExit("Frozen evaluation fixture changed")
    corpus = frozen["corpus"] if args.evaluate else frozen["corpus"][:2]
    work = Path(tempfile.mkdtemp(prefix="xiutu-wp05-synthetic-"))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    actor, token = uuid4(), secrets.token_urlsafe(32)
    env = dict(
        os.environ,
        APP_MODE="test",
        RETRIEVAL_PROFILE="synthetic",
        DATA_PATH=str(work / "storage"),
        OPERATOR_TOKEN=token,
        OPERATOR_ID=str(actor),
        APP_ORIGIN=origin,
        PYTHONPATH=str(ROOT / "backend"),
        PYTHONDONTWRITEBYTECODE="1",
    )
    children = []
    output = dict(
        synthetic_only=True,
        no_human_repair_truth=True,
        fixture_sha256=digest,
        config=frozen["config"],
        documents=[],
        evaluation={},
        artifacts=str(work),
    )
    engine = None
    print("SYNTHETIC ONLY. Not repair evidence or professional approval.", flush=True)
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
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=log,
            )
            children.append(api)
            with httpx.Client(base_url=origin, trust_env=False, timeout=60) as client:
                until = time.monotonic() + 20
                while True:
                    if api.poll() is not None:
                        raise RuntimeError("Owned API exited")
                    try:
                        if client.get("/api/v2/health/ready").status_code == 200:
                            break
                    except (httpx.ConnectError, httpx.ConnectTimeout):
                        pass
                    if time.monotonic() > until:
                        raise RuntimeError("Database/migration not ready")
                    time.sleep(0.1)
                login = client.post(
                    "/api/v2/auth/login", headers={"Origin": origin}, json={"token": token}
                )
                login.raise_for_status()
                headers = {"Origin": origin, "X-CSRF-Token": login.json()["csrf_token"]}

                def run_worker(run_id):
                    code = "import os; from uuid import UUID; from app.infrastructure.job_store import JobStore; from app.worker import Worker; s=JobStore(os.environ['DATABASE_URL']); Worker(s).once(run_id=UUID(os.environ['DEMO_RUN_ID'])); s.close()"
                    p = subprocess.Popen(
                        [sys.executable, "-B", "-c", code],
                        cwd=ROOT,
                        env=dict(env, DEMO_RUN_ID=run_id),
                        stdout=log,
                        stderr=log,
                    )
                    children.append(p)
                    with client.stream("GET", "/api/v2/runs/" + run_id + "/events") as response:
                        response.raise_for_status()
                        events = [
                            line for line in response.iter_lines() if line.startswith("event:")
                        ]
                    if p.wait(timeout=20) != 0:
                        raise RuntimeError("Owned worker failed")
                    state = client.get("/api/v2/runs/" + run_id)
                    state.raise_for_status()
                    if state.json()["status"] != "succeeded":
                        raise RuntimeError(
                            "Task failed: " + state.json()["error"].get("code", "unknown")
                        )
                    return events

                mapping = {}
                for item in corpus:
                    metadata = dict(
                        title="SYNTHETIC " + item["id"],
                        source_kind="synthetic",
                        source_reference="WP05 generated fixture",
                        source_status="unknown",
                        license_status="unknown",
                        scope={},
                        synthetic=True,
                    )
                    data = item["text"].encode()
                    response = client.post(
                        "/api/v2/documents",
                        headers=dict(headers, **{"Idempotency-Key": uuid4().hex}),
                        files={
                            "file": ("synthetic.md", data),
                            "metadata": (None, json.dumps(metadata, ensure_ascii=False)),
                        },
                    )
                    response.raise_for_status()
                    body = response.json()
                    path = f"/api/v2/documents/{body['document_id']}/versions/{body['version_id']}"
                    events = run_worker(body["run_id"])
                    review = client.post(
                        path + "/review",
                        headers=dict(headers, **{"Idempotency-Key": uuid4().hex}),
                        json=dict(
                            decision="approved",
                            scope={},
                            source_status="unknown",
                            license_status="unknown",
                            review_note="SYNTHETIC demo review; not professional approval",
                        ),
                    )
                    review.raise_for_status()
                    assert review.status_code == 202
                    events += run_worker(review.json()["index_run_id"])
                    state = client.get(path)
                    state.raise_for_status()
                    snapshot = state.json()
                    assert snapshot["active_index_id"] and not snapshot["formal_usable"]
                    assert client.get(path + "/content").content == data
                    mapping[body["version_id"]] = item["id"]
                    output["documents"].append(
                        dict(
                            fixture_id=item["id"],
                            **body,
                            index_id=snapshot["active_index_id"],
                            events=events,
                        )
                    )
                    print("Indexed synthetic", item["id"], flush=True)
                query = "P0301 第一缸点火异常"
                found = client.post(
                    "/api/v2/evidence/search",
                    headers=headers,
                    json=dict(query=query, vehicle_scope={}, top_k=5),
                )
                found.raise_for_status()
                output["http_search"] = found.json()
                assert output["http_search"]["chunks"] and all(
                    x["synthetic"] for x in output["http_search"]["chunks"]
                )
                if args.evaluate:
                    engine = make_engine(url)
                    settings = Settings(
                        database_url=url, app_mode="test", retrieval_profile="synthetic"
                    )
                    service = RetrievalService(engine, settings)
                    # Warm local query model separately; no heldout-dependent tuning.
                    service.search(actor, SearchInput(query="synthetic warmup"))
                    for mode in ["baseline", "hybrid"]:
                        records = []
                        for q in frozen["queries"]:
                            result = service.search(
                                actor, SearchInput(query=q["query"], top_k=10), mode=mode
                            )
                            ordered = [mapping[x["document_version_id"]] for x in result["chunks"]]
                            relevant = set(q["relevant"])
                            recall = len(set(ordered[:5]) & relevant) / len(relevant)
                            ranks = [i + 1 for i, x in enumerate(ordered[:10]) if x in relevant]
                            records.append(
                                dict(
                                    id=q["id"],
                                    query=q["query"],
                                    relevant=q["relevant"],
                                    returned=ordered,
                                    recall5=recall,
                                    hit5=int(bool(set(ordered[:5]) & relevant)),
                                    mrr10=1 / min(ranks) if ranks else 0,
                                    latency_ms=result["trace"]["elapsed_ms"],
                                )
                            )
                        import numpy as np

                        output["evaluation"][mode] = dict(
                            n=len(records),
                            recall5=sum(x["recall5"] for x in records) / len(records),
                            hit5=sum(x["hit5"] for x in records) / len(records),
                            mrr10=sum(x["mrr10"] for x in records) / len(records),
                            latency_p50_ms=float(
                                np.percentile([x["latency_ms"] for x in records], 50)
                            ),
                            latency_p95_ms=float(
                                np.percentile([x["latency_ms"] for x in records], 95)
                            ),
                            failed_queries=[x["id"] for x in records if x["recall5"] < 1],
                            records=records,
                        )
                    output["hybrid_improved_recall5"] = (
                        output["evaluation"]["hybrid"]["recall5"]
                        > output["evaluation"]["baseline"]["recall5"]
                    )
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open("x", encoding="utf-8") as f:
                    json.dump(output, f, ensure_ascii=False, indent=2)
        finally:
            if engine is not None:
                engine.dispose()
            for child in children:
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=10)
    assert token not in (work / "process.log").read_text("utf-8")
    print(
        json.dumps(
            {
                k: {kk: vv for kk, vv in v.items() if kk != "records"}
                for k, v in output["evaluation"].items()
            }
        ),
        flush=True,
    )
    print("Saved", args.output, "; only owned processes stopped.")


if __name__ == "__main__":
    main()
