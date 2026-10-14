"""One opt-in synthetic BGE + DeepSeek turn; no preset candidate is published.

The same test without DIAGNOSIS_SLICE_LIVE=1 stops after free source validation.
Private credentials and bounded candidate diagnostics remain outside public evidence.
"""

# ruff: noqa: E402
import hashlib
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/integration"))
sys.path.insert(0, str(ROOT / "scripts"))

import httpx
from app.legacy_execution.runner import WorkerIdentity, _initial_source_chunks
from app.agents.state import ProposalContext, ProposalEnvelope
from app.config import Settings
from app.domain.measurements import BindEvidence, CaseSearch
from app.domain.retrieval import ReindexInput
from app.infrastructure.job_store import JobStore
from app.infrastructure.model_budget import LIVE_LEDGER, BudgetLedger, exclusive
from app.infrastructure.orm import case_evidence, diagnosis_publications, runs, tool_executions
from app.mcp_server.config import TOOLS
from app.services.evidence_service import EvidenceService
from app.services.index_service import IndexService
from app.services.proposal_service import ProposalService
from app.tools.executor import ToolExecutor
from app.validators.proposal import claims
from app.worker import Worker
from dotenv import dotenv_values
from provision_mcp_role import provision
from pydantic import SecretStr
from sqlalchemy import func, select
from test_document_ingest import docrig, wait  # noqa: F401
from test_evidence_measurement import SCOPE, VEHICLE, indexed_rig, review  # noqa: F401
from test_wp10_proposals import synthetic_step

BENCH = ROOT / "tests/fixtures/diagnosis-slice/bench.md"
BGE = Path(r"E:\AI_Cache\huggingface\models--BAAI--bge-m3\snapshots\5617a9f61b028005a4858fdac845db406aefb181")


def test_one_bounded_synthetic_turn(indexed_rig, tmp_path, monkeypatch):  # noqa: F811
    r = indexed_rig
    out = Path(os.environ["DIAGNOSIS_SLICE_PRIVATE"])
    assert out.is_dir() and BGE.is_dir()
    # Alembic creates the isolated schema, while LangGraph's pinned saver
    # installs its own tables separately. Do both before admitting a turn.
    assert r.env["DATABASE_URL"] == r.env["TEST_DATABASE_URL"]
    checkpoint = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/setup_graph_checkpoint.py")],
        cwd=ROOT, env=r.env, capture_output=True, text=True, timeout=30,
    )
    (out / "checkpoint-setup.private.log").write_text(
        checkpoint.stdout + checkpoint.stderr, encoding="utf8")
    assert checkpoint.returncode == 0, "Isolated checkpoint setup failed"
    source = BENCH.read_bytes()
    r.env.update(EMBEDDING_PROVIDER="local_e5", EMBEDDING_DIMENSION="384")
    r.env.pop("EMBEDDING_MODEL_PATH", None)
    upload = r.upload(source, name="bench.md", meta=dict(
        title="隔离台架合成观察样本", source_kind="synthetic_fixture",
        source_reference="tests/fixtures/diagnosis-slice/bench.md",
        source_status="unknown", license_status="unknown", scope=SCOPE, synthetic=True))
    assert upload.status_code == 202, upload.text
    document = upload.json()
    r.complete(document)
    approved = review(r, document, scope=SCOPE)
    assert approved.status_code == 202, approved.text
    p, _ = r.worker(dict(document, run_id=approved.json()["index_run_id"]), lease=30)
    assert p.wait(timeout=90) == 0
    settings = Settings(app_mode="test", database_url=r.env["DATABASE_URL"],
                        data_path=r.env["DATA_PATH"], retrieval_profile="synthetic",
                        tool_mode="local", embedding_provider="local_bge_m3",
                        embedding_model_path=BGE)
    _, reindex = IndexService(r.store.engine, settings).reindex(
        r.actor, UUID(document["document_id"]), UUID(document["version_id"]),
        ReindexInput(), uuid4().hex)
    r.env.update(EMBEDDING_PROVIDER="local_bge_m3", EMBEDDING_DIMENSION="1024",
                 EMBEDDING_MODEL_PATH=str(BGE))
    p, _ = r.worker(dict(document, run_id=reindex["run_id"]), lease=60)
    assert p.wait(timeout=180) == 0
    indexed = r.state(document)
    assert indexed["active_index_id"] == reindex["index_id"] and indexed["index_status"] == "ready"
    case_response = r.client.post("/api/v2/cases", headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
        json=dict(vehicle=VEHICLE, fault_description="隔离台架 P01 外观异常，先做有出处的检查；不作真实维修诊断。", fault_codes=[]))
    assert case_response.status_code == 201, case_response.text
    case = case_response.json()
    assert len(case["corpus_manifest"]) == 1
    assert case["corpus_manifest"][0]["index_id"] == reindex["index_id"]
    with r.store.engine.connect() as c:
        from app.infrastructure.orm import chunks
        rows = c.execute(select(chunks).where(chunks.c.document_version_id == UUID(document["version_id"]))).mappings().all()

    def cite(text):
        row = next(x for x in rows if text in x["text"])
        start = row["text"].index(text)
        body = dict(chunk_id=str(row["id"]), document_version_id=document["version_id"],
                    index_id=reindex["index_id"], quote=text, start=start, end=start + len(text))
        _, evidence = EvidenceService(r.store.engine, settings).bind(
            r.actor, UUID(case["id"]), BindEvidence.model_validate(body), uuid4().hex)
        return dict(text=text, references=[dict(evidence_id=evidence["evidence_id"],
                                                document_version_id=document["version_id"])])

    candidate = synthetic_step(cite)
    candidate["input"]["choices"] = [cite("P01 外观完好。"), cite("P01 外观损坏。")]
    validated = ProposalService(r.store.engine, settings).validate(
        ProposalContext(r.actor, UUID(case["id"]), case["revision"]), candidate)
    assert validated["accepted"], validated["issues"]
    # The fixture's initial HTTP child was booted for E5. Query the same
    # frozen BGE manifest through the accepted case service with BGE settings;
    # the separately started browser API uses these same settings.
    search = EvidenceService(r.store.engine, settings).search(
        r.actor, UUID(case["id"]), CaseSearch(query="P01 外观检查", top_k=3))
    assert search["chunks"]
    # This is the same trusted tool path that supplies the worker's initial
    # model citations, not a query over the entire uploaded file.
    identity = WorkerIdentity(r.actor)
    executor = ToolExecutor(r.store.engine, settings)
    source_context = executor.contexts.open(identity, identity.cookie, UUID(case["id"]),
        allowlist=["search_manuals", "get_evidence_context"], call_limit=6, search_limit=3)
    source_chunks = _initial_source_chunks(executor, source_context, case["fault_description"])
    required = ["P01 位于隔离台架左侧。", "发动机关闭，engine=off。",
                "检查 P01 外观。", "P01 外观完好。", "P01 外观损坏。"]
    assert all(any(sentence in x["text"] for x in source_chunks) for sentence in required)
    assert all(x["document_version_id"] == document["version_id"]
               and x["index_id"] == reindex["index_id"] for x in source_chunks)
    (out / "free-preflight.json").write_text(json.dumps(dict(
        fixture_sha256=hashlib.sha256(source).hexdigest(), synthetic=True,
        formal_usable=False, model="local_bge_m3", dimensions=1024,
        document_version_id=document["version_id"], index_id=reindex["index_id"],
        case_id=case["id"], manifest_count=1, grounded_candidate_accepted=True,
        search_chunks=len(search["chunks"]), runner_source_chunks=len(source_chunks),
        runner_source_fields_present=True), indent=2), encoding="utf8")
    # Operator-only local browser proof; the caller must protect this directory.
    (out / "runtime.private.json").write_text(json.dumps(dict(
        database=r.env["DATABASE_URL"], storage=r.env["DATA_PATH"],
        actor=str(r.actor), token=r.operator_token, case_id=case["id"])), encoding="utf8")
    if os.environ.get("DIAGNOSIS_SLICE_LIVE") != "1":
        return

    with exclusive(LIVE_LEDGER):
        before = BudgetLedger(LIVE_LEDGER).read()
        assert before["version"] == 2 and before["policy"] == "metered_no_cumulative_cap"
        before_count = len(before["calls"])
    private = dotenv_values(ROOT / ".env")
    secret = private.get("DEEPSEEK_API_KEY")
    assert secret, "Protected DeepSeek configuration missing"
    binding = dict(actor_id=str(r.actor), case_id=case["id"], revision=case["revision"],
                   manifest=case["corpus_manifest"], profile="synthetic", allowlist=list(TOOLS))
    dbfile = tmp_path / "readonly-db.private.json"
    provision(r.env["DATABASE_URL"], dbfile)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    token = "synthetic-slice-" + uuid4().hex
    serverfile = tmp_path / "mcp-server.private.json"
    serverfile.write_text(json.dumps(dict(database=json.loads(dbfile.read_text()),
        grants=[dict(binding, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                     expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())],
        hosts=[f"127.0.0.1:{port}"], origins=["http://127.0.0.1:8020"],
        embedding_path=str((ROOT / ".local-data/models/multilingual-e5-small/614241f622f53c4eeff9890bdc4f31cfecc418b3").absolute()),
        embedding_model_path=str(BGE), data_path=r.env["DATA_PATH"], retrieval_profile="synthetic")), encoding="utf8")
    clientfile = tmp_path / "mcp-client.private.json"
    clientfile.write_text(json.dumps(dict(url=f"http://127.0.0.1:{port}/mcp", token=token,
                                          binding=binding)), encoding="utf8")
    log=(tmp_path / "mcp-server.private.log").open("x", encoding="utf8")
    proc=subprocess.Popen([sys.executable,"-B","-m","uvicorn","app.mcp_server.main:create_app",
        "--factory","--host","127.0.0.1","--port",str(port),"--no-access-log","--log-level","warning"],
        cwd=ROOT, env=dict(r.env, MANUAL_MCP_CONFIG=str(serverfile)), stdout=log, stderr=log)
    try:
        def ready():
            assert proc.poll() is None, "Owned MCP process exited"
            try:
                return httpx.get(f"http://127.0.0.1:{port}/health", trust_env=False, timeout=2).status_code == 200
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
                return False
        wait(ready, 90)
        paid_settings = Settings(app_mode="test", database_url=r.env["DATABASE_URL"],
            data_path=r.env["DATA_PATH"], retrieval_profile="synthetic", tool_mode="remote_mcp",
            mcp_client_config=clientfile, embedding_provider="local_bge_m3", embedding_model_path=BGE,
            deepseek_api_key=SecretStr(secret), deepseek_model="deepseek-flash")
        store=JobStore(r.env["DATABASE_URL"], settings=paid_settings)
        try:
            start=r.client.post(f"/api/v2/cases/{case['id']}/diagnosis/runs",
                headers=dict(r.headers, **{"Idempotency-Key":uuid4().hex}), json={"expected_revision":0})
            assert start.status_code==202, start.text
            run_id=UUID(start.json()["run_id"])
            with store.engine.connect() as c:
                turn_id=c.execute(select(runs.c.turn_id).where(runs.c.id==run_id)).scalar_one()
            monkeypatch.setenv("XIUTU_WP11_PAID","1")
            diagnostic_path=out / "proposal-diagnostic.private.jsonl"
            fd=os.open(diagnostic_path, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
            with os.fdopen(fd,"w",encoding="utf8") as diagnostic:
                def save(event):
                    diagnostic.write(json.dumps(event,ensure_ascii=False)+"\n")
                    diagnostic.flush()
                    os.fsync(diagnostic.fileno())
                assert Worker(store, heartbeat_seconds=15, diagnostic_sink=save,
                              legacy_execution=True).once(run_id=run_id)
            with store.engine.connect() as c:
                run=c.execute(select(runs).where(runs.c.id==run_id)).mappings().one()
                publication_count=c.execute(select(func.count()).select_from(diagnosis_publications).where(
                    diagnosis_publications.c.run_id==run_id)).scalar_one()
                tool_attempts=sum(c.execute(select(tool_executions.c.used).where(
                    tool_executions.c.run_id==run_id)).scalars().all())
            current=r.client.get(f"/api/v2/cases/{case['id']}/diagnosis").json()
            step=current["current_step"]
            refs=0
            if step:
                allowed={(x["document_version_id"],x["index_id"]) for x in case["corpus_manifest"]}
                with store.engine.connect() as c:
                    for _,claim,_ in claims(ProposalEnvelope.model_validate(step["candidate"]).root):
                        for ref in claim.references:
                            evidence=c.execute(select(case_evidence).where(
                                case_evidence.c.id==ref.evidence_id,
                                case_evidence.c.case_id==UUID(case["id"]))).mappings().one()
                            assert (str(evidence["document_version_id"]),str(evidence["index_id"])) in allowed
                            refs+=1
            with exclusive(LIVE_LEDGER):
                after=BudgetLedger(LIVE_LEDGER).read()
                calls=[v for k,v in after["calls"].items() if k.startswith(str(turn_id)+":") and k not in before["calls"]]
            summary=dict(synthetic=True, run_id=str(run_id), case_id=case["id"],
                status=run["status"], error_code=run["error_json"].get("code"),
                publication_count=publication_count, step_id=step["id"] if step else None,
                authorized_references=refs, tool_attempts=tool_attempts,
                model_requests=len(calls), usage_status=[x.get("usage_status") for x in calls],
                reserved_before=before["reserved_cny"], reserved_after=after["reserved_cny"],
                calls_before=before_count, calls_after=len(after["calls"]), invoice_verified=False)
            (out / "live-summary.json").write_text(json.dumps(summary,indent=2),encoding="utf8")
            (out / "runtime.private.json").write_text(json.dumps(dict(database=r.env["DATABASE_URL"],
                storage=r.env["DATA_PATH"], actor=str(r.actor), token=r.operator_token,
                case_id=case["id"], run_id=str(run_id))),encoding="utf8")
            print("one bounded turn: status="+run["status"]+", publications="+str(publication_count)+", requests="+str(len(calls)))
            assert run["status"]=="waiting_input" and publication_count==1 and refs>0, summary["error_code"]
        finally:
            store.close()
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
        log.close()
