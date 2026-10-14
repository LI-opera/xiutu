"""WP-15 deterministic HTTP contract and optional isolated browser seed."""

import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from app.agents.state import ProposalContext
from app.config import Settings
from app.services.diagnosis_service import DiagnosisService, StartDiagnosis
from test_document_ingest import docrig  # noqa: F401
from test_evidence_measurement import indexed_rig  # noqa: F401
from test_wp10_proposals import prepare, synthetic_step

BENCH = Path(__file__).resolve().parents[1] / "fixtures/diagnosis-slice/bench.md"


def publish_waiting_step(r):
    source = BENCH.read_text(encoding="utf-8") + "\n\n检查 P01 插头。\n\n检查 P01 外壳。\n"
    _, case, _, validator, cite = prepare(r, source.encode("utf-8"))
    cid = UUID(case["id"])
    candidate = synthetic_step(cite)
    candidate["input"]["choices"] = [cite("P01 外观完好。"), cite("P01 外观损坏。")]
    checked = validator.validate(ProposalContext(r.actor, cid, 0), candidate)
    assert checked["accepted"], checked["issues"]
    run_id = UUID(DiagnosisService(r.store.engine).start(
        r.actor, cid, StartDiagnosis(expected_revision=0), uuid4().hex)[1]["run_id"])
    r.store.lease_seconds = 60
    r.store.settings = Settings(app_mode="test", retrieval_profile="synthetic")
    lease = r.store.claim_legacy("wp15-deterministic", run_id=run_id)
    try:
        r.store.stage_diagnosis(lease, checked)
        r.store.finish(lease, result=checked)
    finally:
        lease.close()
    return cid, validator, cite


def test_wp15_real_http_workbench_read_submit_replay_and_restore(indexed_rig):  # noqa: F811
    r = indexed_rig
    cid, validator, cite = publish_waiting_step(r)
    case = r.client.get(f"/api/v2/cases/{cid}").json()
    diagnosis = r.client.get(f"/api/v2/cases/{cid}/diagnosis").json()
    areas = r.client.get(f"/api/v2/cases/{cid}/diagnosis/areas").json()
    assert case["status"] == diagnosis["status"] == "waiting_input"
    assert len(areas["areas"]) == 1 and areas["areas"][0]["current_step_id"]
    step = diagnosis["current_step"]
    body = {"expected_revision": case["revision"], "graph_epoch": case["graph_epoch"],
            "step_id": step["id"], "kind": "choice", "choice_index": 0,
            "conditions": step["required_conditions"]}
    key = uuid4().hex
    headers = dict(r.headers, **{"Idempotency-Key": key})
    first = r.client.post(f"/api/v2/cases/{cid}/observations", headers=headers, json=body)
    replay = r.client.post(f"/api/v2/cases/{cid}/observations", headers=headers, json=body)
    assert first.status_code == 202 and replay.json() == first.json()
    history = r.client.get(f"/api/v2/cases/{cid}/observations").json()
    assert len(history["items"]) == 1
    assert history["items"][0]["input_schema"]["kind"] == "choice"
    assert history["items"][0]["required_conditions"] == {"engine": "off"}
    restored = r.client.get(f"/api/v2/cases/{cid}").json()
    assert restored["revision"] == case["revision"] + 1
    next_candidate = synthetic_step(cite)
    next_candidate["title"] = "依据已保存观察继续检查"
    next_candidate["actions"] = [dict(**cite("检查 P01 插头。"), operation="inspect")]
    checked = validator.validate(ProposalContext(r.actor, cid, restored["revision"]), next_candidate)
    assert checked["accepted"], checked["issues"]
    child_id = UUID(first.json()["run_id"])
    lease = r.store.claim_legacy("wp15-next", run_id=child_id)
    try:
        r.store.stage_diagnosis(lease, checked)
        r.store.finish(lease, result=checked)
    finally:
        lease.close()
    refreshed = r.client.get(f"/api/v2/cases/{cid}/diagnosis").json()
    assert refreshed["status"] == "waiting_input"
    assert refreshed["current_step"]["candidate"]["title"] == "依据已保存观察继续检查"
    gate = r.client.get(f"/api/v2/cases/{cid}/reports/gate").json()
    assert not gate["allowed"] and gate["blocking_items"]


def test_wp15_optional_browser_seed(indexed_rig):  # noqa: F811
    output = os.environ.get("WP15_BROWSER_SEED")
    if not output:
        return
    r = indexed_rig
    cid, _, _ = publish_waiting_step(r)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({
        "database": str(os.environ["TEST_DATABASE_URL"]).rsplit("/", 1)[1],
        "storage": r.env["DATA_PATH"], "actor": str(r.actor),
        "case_id": str(cid), "processes": [],
    }, indent=2), encoding="utf-8")
