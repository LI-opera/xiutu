"""Explicit paid WP-11 probe; excluded from the standard test entrypoint.

Uses the user-authorized synthetic DKVB manual, real BGE, a separate read-only
business MCP process and the ORIGINAL shared DeepSeek budget ledger. Never
prints secrets, the ledger, source body or raw provider responses.
"""

# ruff: noqa: E402

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "integration"))

import httpx
import pytest
from app.agents.state import ProposalEnvelope
from app.config import Settings
from app.legacy_preview.dkvb import MANUALS, VEHICLE, safe_file, verify_package
from app.domain.retrieval import ReindexInput
from app.infrastructure.job_store import JobStore
from app.infrastructure.model_budget import LIVE_LEDGER, BudgetLedger
from app.infrastructure.orm import (
    case_evidence,
    cases,
    diagnosis_publications,
    runs,
    tool_executions,
)
from app.mcp_server.config import TOOLS
from app.services.index_service import IndexService
from app.validators.proposal import claims
from app.worker import Worker
from dotenv import dotenv_values
from pydantic import SecretStr
from sqlalchemy import select
from test_document_ingest import docrig, wait  # noqa: F401
from test_evidence_measurement import review

sys.path.insert(0, str(ROOT / "scripts"))
from provision_mcp_role import provision

PACKAGE = Path(__file__).resolve().parents[2] / "resources/legacy/tayron-dkvb-p0299"
BGE = Path(r"E:\AI_Cache\huggingface\models--BAAI--bge-m3\snapshots\5617a9f61b028005a4858fdac845db406aefb181")
pytestmark = pytest.mark.database


def test_one_paid_dkvb_mcp_turn(monkeypatch, request, tmp_path):
    assert os.environ.get("WP11_LIVE") == "1", "Explicit live opt-in required"
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.setenv("RETRIEVAL_PROFILE", "synthetic")
    r = request.getfixturevalue("docrig")
    assert BGE.is_dir()
    verified = verify_package(PACKAGE)
    assert len(verified["files"]) >= 2
    manuals = []
    for name in MANUALS:
        # Review schedules the normal E5 index first; only the explicit
        # reindex job below may run with BGE. Keep the two model configs apart
        # across successive manual uploads.
        r.env["EMBEDDING_PROVIDER"] = "local_e5"
        r.env["EMBEDDING_DIMENSION"] = "384"
        r.env.pop("EMBEDDING_MODEL_PATH", None)
        raw = safe_file(PACKAGE, name).read_bytes()
        meta = dict(title=name, source_kind="authored_demo",
                    source_reference="DKVB-P0299-DEMO-v1/" + name,
                    source_status="unknown", license_status="unknown",
                    scope=VEHICLE, synthetic=True)
        upload = r.upload(raw, name=name, meta=meta)
        assert upload.status_code == 202, upload.text
        body = upload.json()
        r.complete(body)
        approved = review(r, body, scope=VEHICLE)
        assert approved.status_code == 202
        worker, _ = r.worker(dict(body, run_id=approved.json()["index_run_id"]), lease=30)
        assert worker.wait(timeout=90) == 0
        index_settings = Settings(app_mode="test", database_url=r.env["DATABASE_URL"],
                                  retrieval_profile="synthetic",
                                  embedding_provider="local_bge_m3", embedding_model_path=BGE)
        status, value = IndexService(r.store.engine, index_settings).reindex(
            r.actor, UUID(body["document_id"]), UUID(body["version_id"]),
            ReindexInput(), uuid4().hex)
        assert status == 202
        r.env["EMBEDDING_PROVIDER"] = "local_bge_m3"
        r.env["EMBEDDING_DIMENSION"] = "1024"
        r.env["EMBEDDING_MODEL_PATH"] = str(BGE)
        bge_worker, _ = r.worker(dict(body, run_id=value["run_id"]), lease=60)
        assert bge_worker.wait(timeout=180) == 0
        state = r.state(body)
        assert state["active_index_id"] == value["index_id"] and state["index_status"] == "ready"
        manuals.append(body)
    case_response = r.client.post(
        "/api/v2/cases", headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
        json=dict(vehicle=VEHICLE,
                  fault_description="探岳DKVB出现P0299，建议先检查什么？请只引用授权演示资料。",
                  fault_codes=["P0299"]))
    assert case_response.status_code == 201
    case = case_response.json()
    assert {x["document_version_id"] for x in case["corpus_manifest"]} == {
        x["version_id"] for x in manuals}
    with r.store.engine.connect() as c:
        row = c.execute(select(cases).where(cases.c.id == UUID(case["id"]))).mappings().one()
    binding = dict(actor_id=str(r.actor), case_id=case["id"],
                   revision=row["revision"], manifest=row["corpus_manifest"],
                   profile="synthetic", allowlist=list(TOOLS))
    dbfile = tmp_path / "read-only-db-secret.json"
    provision(r.env["DATABASE_URL"], dbfile)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    token = "synthetic-wp11-" + uuid4().hex
    serverfile = tmp_path / "mcp-server-secret.json"
    serverfile.write_text(json.dumps(dict(
        database=json.loads(dbfile.read_text()),
        grants=[dict(binding, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                     expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())],
        hosts=[f"127.0.0.1:{port}"], origins=["http://127.0.0.1:8020"],
        embedding_path=str((ROOT / ".local-data/models/multilingual-e5-small/614241f622f53c4eeff9890bdc4f31cfecc418b3").absolute()),
        embedding_model_path=str(BGE), data_path=r.env["DATA_PATH"],
        retrieval_profile="synthetic")), encoding="utf8")
    clientfile = tmp_path / "mcp-client-secret.json"
    clientfile.write_text(json.dumps(dict(url=f"http://127.0.0.1:{port}/mcp",
                                          token=token, binding=binding)), encoding="utf8")
    env = dict(r.env, MANUAL_MCP_CONFIG=str(serverfile))
    log = (tmp_path / "mcp-server.log").open("x", encoding="utf8")
    proc = subprocess.Popen([sys.executable, "-B", "-m", "uvicorn",
                             "app.mcp_server.main:create_app", "--factory",
                             "--host", "127.0.0.1", "--port", str(port),
                             "--no-access-log", "--log-level", "warning"],
                            cwd=ROOT, env=env, stdout=log, stderr=log)
    try:
        def ready():
            assert proc.poll() is None, "Owned MCP service exited"
            try:
                return httpx.get(f"http://127.0.0.1:{port}/health",
                                 trust_env=False, timeout=2).status_code == 200
            except (httpx.ConnectError, httpx.ReadTimeout):
                return False

        # Cold process startup imports the local embedding stack before the
        # HTTP listener exists. Bound readiness separately from the turn's
        # 120-second model/tool deadline; no model request is made here.
        wait(ready, 90)
        private = dotenv_values(ROOT / ".env")
        secret = private.get("DEEPSEEK_API_KEY")
        assert secret, "Protected project DeepSeek key unavailable"
        ledger = BudgetLedger(LIVE_LEDGER)
        before = ledger.read()
        assert before["version"] == 2 and before["policy"] == "metered_no_cumulative_cap"
        settings = Settings(app_mode="test", database_url=r.env["DATABASE_URL"],
                            data_path=r.env["DATA_PATH"], retrieval_profile="synthetic",
                            tool_mode="remote_mcp", mcp_client_config=clientfile,
                            embedding_provider="local_bge_m3", embedding_model_path=BGE,
                            deepseek_api_key=SecretStr(secret), deepseek_model="deepseek-flash")
        store = JobStore(r.env["DATABASE_URL"], settings=settings)
        try:
            start = r.client.post(
                f"/api/v2/cases/{case['id']}/diagnosis/runs",
                headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
                json={"expected_revision": case["revision"]})
            assert start.status_code == 202
            run_id = UUID(start.json()["run_id"])
            with store.engine.connect() as c:
                turn_id = c.execute(select(runs.c.turn_id).where(runs.c.id == run_id)).scalar_one()
            monkeypatch.setenv("XIUTU_WP11_PAID", "1")
            # Restrict an empty directory before creating the private trace.
            # Windows file mode alone does not remove inherited Users/Authenticated
            # Users ACLs; the trace must not inherit pytest temp's broad ACL.
            private_dir = tmp_path / "private-diagnostics"
            private_dir.mkdir(mode=0o700)
            if os.name == "nt":
                identity = subprocess.run(
                    ["whoami", "/user", "/fo", "csv", "/nh"],
                    capture_output=True, check=True,
                )
                sid = re.search(rb"S-1-5-\d+(?:-\d+)+", identity.stdout)
                assert sid is not None
                subprocess.run(
                    ["icacls", str(private_dir), "/inheritance:r", "/grant:r",
                     "*" + sid.group().decode("ascii") + ":F", "*S-1-5-18:F"],
                    capture_output=True, check=True,
                )
            else:
                private_dir.chmod(0o700)
            diagnostic_path = private_dir / "proposal-diagnostic.private.jsonl"
            fd = os.open(diagnostic_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf8") as diagnostic:
                def save_diagnostic(event):
                    diagnostic.write(json.dumps(event, ensure_ascii=False) + "\n")
                    diagnostic.flush()
                    os.fsync(diagnostic.fileno())

                assert Worker(store, heartbeat_seconds=15, legacy_execution=True,
                              diagnostic_sink=save_diagnostic).once(run_id=run_id)
            with store.engine.connect() as c:
                run = c.execute(select(runs).where(runs.c.id == run_id)).mappings().one()
                publications = c.execute(select(diagnosis_publications.c.id).where(
                    diagnosis_publications.c.run_id == run_id)).all()
                tool_used = c.execute(select(tool_executions.c.used).where(
                    tool_executions.c.run_id == run_id)).scalars().all()
            current_response = r.client.get(f"/api/v2/cases/{case['id']}/diagnosis")
            assert current_response.status_code == 200
            current = current_response.json()
            step = current["current_step"]
            refs_checked = 0
            if step is not None:
                assert step["validation"]["accepted"] is True
                allowed = {(x["document_version_id"], x["index_id"])
                           for x in case["corpus_manifest"]}
                candidate = ProposalEnvelope.model_validate(step["candidate"]).root
                with store.engine.connect() as c:
                    for _, claim, _ in claims(candidate):
                        for ref in claim.references:
                            evidence = c.execute(select(case_evidence).where(
                                case_evidence.c.id == ref.evidence_id,
                                case_evidence.c.case_id == UUID(case["id"])
                            )).mappings().one()
                            assert str(evidence["document_version_id"]) == str(ref.document_version_id)
                            assert (str(evidence["document_version_id"]),
                                    str(evidence["index_id"])) in allowed
                            refs_checked += 1
            after = ledger.read()
            model_calls = [v for k, v in after["calls"].items()
                           if k.startswith(str(turn_id) + ":") and k not in before["calls"]]
            summary = dict(source="DKVB synthetic manuals, not a real repair verdict",
                           documents=[x["version_id"] for x in manuals],
                           run_id=str(run_id), status=run["status"],
                           error_code=run["error_json"].get("code"),
                           publication_count=len(publications),
                           current_step_id=step["id"] if step else None,
                           validated=bool(step and step["validation"]["accepted"]),
                           authorized_references=refs_checked,
                           tool_attempts=sum(tool_used), model_request_count=len(model_calls),
                           model_usage_status=[x.get("usage_status") for x in model_calls],
                           model_usage=[x.get("usage") for x in model_calls],
                           reserved_before=before["reserved_cny"],
                           reserved_after=after["reserved_cny"],
                           invoice_verified=False)
            (tmp_path / "live-summary.json").write_text(
                json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf8")
            print("WP11 live probe: status=" + run["status"] +
                  ", publication_count=" + str(len(publications)) +
                  ", model_requests=" + str(len(model_calls)))
            # Persist the sanitized failure record first. A test-process exit 0
            # must mean an actual, authorized, durable business publication.
            assert run["status"] == "waiting_input", summary["error_code"]
            assert len(publications) == 1 and step is not None
            assert step["run_id"] == str(run_id) and refs_checked > 0
            restarted = subprocess.run(
                [sys.executable, "-B", "-c",
                 "import json,os;from uuid import UUID;"
                 "from app.infrastructure.uow import make_engine;"
                 "from app.services.case_service import CaseService;"
                 "e=make_engine(os.environ['DATABASE_URL']);"
                 "c=CaseService(e,b'probe',profile='synthetic').get(UUID(os.environ['WP11_ACTOR']),UUID(os.environ['WP11_CASE']));"
                 "print(json.dumps({'step_id':c['current_check']['id'],'revision':c['revision']}));e.dispose()"],
                cwd=ROOT, env=dict(r.env, WP11_ACTOR=str(r.actor), WP11_CASE=case["id"]),
                capture_output=True, text=True, timeout=15, check=True)
            reread = json.loads(restarted.stdout)
            assert reread["step_id"] == step["id"]
            assert reread["revision"] == current["revision"]
            assert len([k for k in ledger.read()["calls"]
                        if k.startswith(str(turn_id) + ":")]) == len(model_calls)
        finally:
            store.close()
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
        log.close()
