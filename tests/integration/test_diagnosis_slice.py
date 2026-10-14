"""Free HTTP proof for the new UI contract; candidate is a synthetic fixture."""

from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4

from app.agents.state import ProposalContext
from app.config import Settings
from app.services.diagnosis_service import DiagnosisService, StartDiagnosis
from test_document_ingest import docrig  # noqa: F401
from test_evidence_measurement import indexed_rig  # noqa: F401
from test_wp10_proposals import prepare, synthetic_step

BENCH = Path(__file__).resolve().parents[1] / "fixtures/diagnosis-slice/bench.md"


def test_browser_contract_uses_published_conditions_and_saved_observation(indexed_rig):  # noqa: F811
    r = indexed_rig
    _, case, _, validator, cite = prepare(r, BENCH.read_bytes())
    cid = UUID(case["id"])
    candidate = synthetic_step(cite)
    candidate["input"]["choices"] = [cite("P01 外观完好。"), cite("P01 外观损坏。")]
    checked = validator.validate(ProposalContext(r.actor, cid, 0), candidate)
    assert checked["accepted"], checked["issues"]
    run_id = UUID(DiagnosisService(r.store.engine).start(
        r.actor, cid, StartDiagnosis(expected_revision=0), uuid4().hex)[1]["run_id"])
    r.store.lease_seconds = 60
    r.store.settings = Settings(app_mode="test", retrieval_profile="synthetic")
    lease = r.store.claim_legacy("diagnosis-slice-free", run_id=run_id)
    try:
        r.store.stage_diagnosis(lease, checked)
        r.store.finish(lease, result=checked)
    finally:
        lease.close()
    current = r.client.get(f"/api/v2/cases/{cid}/diagnosis")
    assert current.status_code == 200
    view = current.json()
    assert view["status"] == "waiting_input"
    step = view["current_step"]
    assert step["candidate"]["input"]["choices"][0]["text"] == "P01 外观完好。"
    assert step["required_conditions"] == {"engine": "off"}
    body = dict(expected_revision=view["revision"], graph_epoch=view["graph_epoch"],
                step_id=step["id"], kind="choice", choice_index=0,
                conditions=step["required_conditions"])
    key = uuid4().hex
    headers = dict(r.headers, **{"Idempotency-Key": key})
    first = r.client.post(f"/api/v2/cases/{cid}/observations", headers=headers, json=body)
    assert first.status_code == 202, first.text
    replay = r.client.post(f"/api/v2/cases/{cid}/observations", headers=headers, json=body)
    assert replay.status_code in {200, 202} and replay.json() == first.json()
    history = r.client.get(f"/api/v2/cases/{cid}/observations")
    assert history.status_code == 200 and len(history.json()["items"]) == 1
    assert history.json()["items"][0]["payload"]["appearance_state"] == "intact"
    after = r.client.get(f"/api/v2/cases/{cid}/diagnosis").json()
    assert after["revision"] == view["revision"] + 1 and after["status"] == "analyzing"


def test_source_present_does_not_authorize_unbounded_field_wording(indexed_rig):  # noqa: F811
    r = indexed_rig
    _, case, _, validator, cite = prepare(r, BENCH.read_bytes())
    candidate = synthetic_step(cite)
    candidate["input"]["choices"] = [cite("P01 外观完好。"), cite("P01 外观损坏。")]
    context = ProposalContext(r.actor, UUID(case["id"]), case["revision"])
    assert validator.validate(context, candidate)["accepted"]

    wrong = deepcopy(candidate)
    wrong["prerequisites"] = []
    assert "CONDITIONS_MISSING" in {x["code"] for x in validator.validate(context, wrong)["issues"]}

    wrong = deepcopy(candidate)
    wrong["location"]["text"] = "P01 在隔离台架左侧。"
    assert "LOCATION_UNCERTAIN" in {x["code"] for x in validator.validate(context, wrong)["issues"]}

    wrong = deepcopy(candidate)
    wrong["actions"][0]["text"] = "检视 P01 外观。"
    assert "ACTION_SEMANTICS_UNCERTAIN" in {
        x["code"] for x in validator.validate(context, wrong)["issues"]}

    wrong = deepcopy(candidate)
    wrong["input"]["choices"][0]["text"] = "P01 外观正常。"
    assert "CHOICE_SEMANTICS_UNCERTAIN" in {
        x["code"] for x in validator.validate(context, wrong)["issues"]}

    wrong = deepcopy(candidate)
    wrong["interpretation"] = [cite("P01 未检查时不得排除。")]
    assert "INTERPRETATION_UNCERTAIN" in {
        x["code"] for x in validator.validate(context, wrong)["issues"]}
