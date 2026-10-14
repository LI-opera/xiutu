"""Free WP-11 contract alignment on isolated PostgreSQL; no LLM credentials."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from app.agents.state import ProposalContext
from app.config import Settings
from app.legacy_preview.dkvb import MANUALS, VEHICLE, safe_file, verify_package
from app.domain.retrieval import ReindexInput
from app.infrastructure.orm import (
    cases,
    chunks,
    diagnosis_publications,
    document_versions,
    graph_progress,
)
from app.retrieval.eligibility import applicability
from app.services.diagnosis_service import DiagnosisService, StartDiagnosis
from app.services.index_service import IndexService
from app.services.proposal_service import ProposalService
from app.validators.repetition import action_key, normalize
from app.validators.support import has_complete_context, location_supported, operating_conditions
from sqlalchemy import func, select
from test_document_ingest import docrig as docrig
from test_evidence_measurement import bind, review
from test_evidence_measurement import indexed_rig as indexed_rig
from test_wp10_proposals import FIX, prepare, synthetic_step

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parents[2] / "resources/legacy/tayron-dkvb-p0299"
BGE = Path(r"E:\AI_Cache\huggingface\models--BAAI--bge-m3\snapshots\5617a9f61b028005a4858fdac845db406aefb181")
pytestmark = pytest.mark.database


def _field_status(scope, vehicle):
    out = {}
    for key in ("model", "engine_family", "engine_code"):
        source, target = scope.get(key), vehicle.get(key)
        out[key] = ("unknown" if not source or not target else
                    "matched" if source.strip().casefold() == target.strip().casefold()
                    else "mismatch")
    low, high, year = scope.get("year_from"), scope.get("year_to"), vehicle.get("year")
    out["year_from"] = "unknown" if low is None or year is None else "matched" if year >= low else "mismatch"
    out["year_to"] = "unknown" if high is None or year is None else "matched" if year <= high else "mismatch"
    return out


def test_dkvb_source_scope_and_bounded_step_rig(indexed_rig):
    r = indexed_rig
    assert verify_package(PACKAGE)["package_id"] == "DKVB-P0299-DEMO-v1"
    assert BGE.is_dir()
    manuals = []
    for name in MANUALS:
        r.env["EMBEDDING_PROVIDER"] = "local_e5"
        r.env["EMBEDDING_DIMENSION"] = "384"
        r.env.pop("EMBEDDING_MODEL_PATH", None)
        meta = dict(title=name, source_kind="authored_demo",
                    source_reference="DKVB-P0299-DEMO-v1/" + name,
                    source_status="unknown", license_status="unknown",
                    scope=VEHICLE, synthetic=True)
        uploaded = r.upload(safe_file(PACKAGE, name).read_bytes(), name=name, meta=meta)
        assert uploaded.status_code == 202
        body = uploaded.json()
        r.complete(body)
        approved = review(r, body, scope=VEHICLE)
        assert approved.status_code == 202
        worker, _ = r.worker(dict(body, run_id=approved.json()["index_run_id"]), lease=30)
        assert worker.wait(timeout=90) == 0
        settings = Settings(app_mode="test", database_url=r.env["DATABASE_URL"],
                            retrieval_profile="synthetic", embedding_provider="local_bge_m3",
                            embedding_model_path=BGE)
        status, value = IndexService(r.store.engine, settings).reindex(
            r.actor, UUID(body["document_id"]), UUID(body["version_id"]),
            ReindexInput(), uuid4().hex)
        assert status == 202
        r.env["EMBEDDING_PROVIDER"] = "local_bge_m3"
        r.env["EMBEDDING_DIMENSION"] = "1024"
        r.env["EMBEDDING_MODEL_PATH"] = str(BGE)
        bge_worker, _ = r.worker(dict(body, run_id=value["run_id"]), lease=60)
        assert bge_worker.wait(timeout=180) == 0
        assert r.state(body)["active_index_id"] == value["index_id"]
        manuals.append(body)

    created = r.client.post(
        "/api/v2/cases", headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
        json=dict(vehicle=VEHICLE, fault_description="虚拟DKVB/P0299技术验证", fault_codes=["P0299"]))
    assert created.status_code == 201
    case = created.json()
    assert {x["document_version_id"] for x in case["corpus_manifest"]} == {
        x["version_id"] for x in manuals}
    with r.store.engine.connect() as c:
        stored_case = c.execute(select(cases).where(cases.c.id == UUID(case["id"]))).mappings().one()
        stored = {m["version_id"]: c.execute(select(document_versions).where(
            document_versions.c.id == UUID(m["version_id"]))).mappings().one()
            for m in manuals}
    fields = {}
    for body in manuals:
        scope = stored[body["version_id"]]["review_snapshot"]["scope"]
        fields[body["version_id"]] = _field_status(scope, stored_case["vehicle_json"])
        assert fields[body["version_id"]] == dict(
            model="matched", engine_family="unknown", engine_code="matched",
            year_from="unknown", year_to="unknown")
        assert applicability(scope, stored_case["vehicle_json"])["status"] == "unknown"
        assert applicability(dict(scope, engine_code="OTHER"), stored_case["vehicle_json"])["status"] == "mismatch"
    assert all(x["profile"] == "synthetic" for x in case["corpus_manifest"])

    # These source lines are selected by the sealed package's line numbers;
    # neither source prose nor the candidate is written to public evidence.
    raw = safe_file(PACKAGE, MANUALS[0]).read_text(encoding="utf8").splitlines()
    lines = {"purpose": raw[104], "location": raw[20],
             "prerequisites": raw[100], "actions": raw[104],
             "choices": raw[106]}
    with r.store.engine.connect() as c:
        rows = c.execute(select(chunks).where(
            chunks.c.document_version_id == UUID(manuals[0]["version_id"]))).mappings().all()
    def cite(line):
        row = next(x for x in rows if line in x["text"])
        start = row["text"].index(line)
        assert has_complete_context(row["text"], start, start + len(line))
        evidence = bind(r, case, dict(
            chunk_id=str(row["id"]), document_version_id=manuals[0]["version_id"],
            index_id=r.state(manuals[0])["active_index_id"], quote=line,
            start=start, end=start + len(line)))
        return dict(text=line, references=[dict(evidence_id=evidence["evidence_id"],
                                               document_version_id=manuals[0]["version_id"])])

    candidate = dict(type="propose_step", component_key="G31", title="原文边界核对",
                     purpose=cite(lines["purpose"]), location=cite(lines["location"]),
                     prerequisites=[cite(lines["prerequisites"])],
                     actions=[dict(**cite(lines["actions"]), operation="inspect")],
                     input=dict(kind="choice", choices=[cite(lines["choices"])]))
    result = ProposalService(r.store.engine, Settings(
        app_mode="test", retrieval_profile="synthetic")).validate(
            ProposalContext(r.actor, UUID(case["id"]), case["revision"]), candidate)
    codes = {x["code"] for x in result["issues"]}
    assert not result["accepted"] and result["disposition"] == "needs_input"
    assert {"SCOPE_NOT_MATCHED", "LOCATION_UNCERTAIN", "CONDITIONS_UNCERTAIN",
            "ACTION_SEMANTICS_UNCERTAIN", "CHOICE_SEMANTICS_UNCERTAIN"} <= codes
    assert not location_supported(lines["location"], "G31")
    assert operating_conditions([SimpleNamespace(text=lines["prerequisites"])]) is None
    assert action_key(SimpleNamespace(text=lines["actions"], operation="inspect"), "G31") is None
    assert normalize(lines["choices"]) != normalize("G31 未检查时不得排除")
    # Inspect whole original manuals for exact supported condition grammar;
    # this checks the bounded rule, not general natural-language evidence.
    all_paragraphs = [part.strip() for name in MANUALS for part in re.split(
        r"\n\s*\n", safe_file(PACKAGE, name).read_text(encoding="utf8")) if part.strip()]
    assert not any(operating_conditions([SimpleNamespace(text=p)]) for p in all_paragraphs)
    summary = dict(case_id=case["id"], document_version_ids=[m["version_id"] for m in manuals],
                   index_ids=[r.state(m)["active_index_id"] for m in manuals],
                   stored_scope_fields=fields, source_line_numbers={"purpose": 105,
                   "location": 21, "prerequisites": 101, "actions": 105, "choices": 107},
                   rule_codes=sorted(codes), accepted=False,
                   bounded_condition_paragraph_matches=0)
    out = os.environ.get("WP11_ALIGNMENT_OUT")
    if out:
        Path(out).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf8")


def test_complete_scope_free_publish_and_process_readback(indexed_rig, database_url):
    r = indexed_rig
    r.store.lease_seconds = 60
    _, case, ctx, svc, cite = prepare(r, (FIX / "extra-synthetic.md").read_bytes())
    candidate = synthetic_step(cite)
    checked = svc.validate(ctx, candidate)
    assert checked["accepted"] and checked["disposition"] == "candidate"
    cid = UUID(case["id"])
    service = DiagnosisService(r.store.engine)
    status, started = service.start(r.actor, cid, StartDiagnosis(expected_revision=0), uuid4().hex)
    assert status == 202
    rid = UUID(started["run_id"])
    lease = r.store.claim_legacy("wp11-free-contract", run_id=rid)
    assert lease is not None
    try:
        r.store.stage_diagnosis(lease, checked)
        r.store.finish(lease, result=checked)
    finally:
        lease.close()
    current = service.current(r.actor, cid)
    assert current["status"] == "waiting_input" and current["revision"] == 1
    step = current["current_step"]
    # Publication persists the cleared issue list, not the transient
    # ProposalService `accepted` flag from the validation response.
    assert step and step["validation"]["issues"] == []
    with r.store.engine.connect() as c:
        assert c.execute(select(func.count()).select_from(diagnosis_publications).where(
            diagnosis_publications.c.run_id == rid)).scalar_one() == 1
    env = dict(r.env, DATABASE_URL=str(database_url), TEST_DATABASE_URL=str(database_url),
               PYTHONPATH=str(ROOT / "backend"), APP_MODE="test", RETRIEVAL_PROFILE="synthetic")
    for key in ("DEEPSEEK_API_KEY", "XIUTU_WP11_PAID", "XIUTU_LOAD_PROJECT_ENV"):
        env.pop(key, None)
    code = (
        "import json,os;from uuid import UUID;"
        "from app.infrastructure.job_store import JobStore;"
        "from app.services.diagnosis_service import DiagnosisService;"
        "s=JobStore(os.environ['DATABASE_URL']);s.reconcile_pending();"
        "x=DiagnosisService(s.engine).current(UUID(os.environ['ACTOR']),UUID(os.environ['CASE']));"
        "print(json.dumps({'status':x['status'],'revision':x['revision'],"
        "'step_id':x['current_step']['id']}));s.close()"
    )
    proc = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT,
                          env=dict(env, ACTOR=str(r.actor), CASE=case["id"]),
                          capture_output=True, text=True, timeout=20)
    assert proc.returncode == 0, "Isolated readback process failed"
    reread = json.loads(proc.stdout)
    assert reread == dict(status="waiting_input", revision=1, step_id=step["id"])
    with r.store.engine.connect() as c:
        assert c.execute(select(graph_progress.c.phase).where(
            graph_progress.c.run_id == rid)).scalar_one() == "waiting_input"
