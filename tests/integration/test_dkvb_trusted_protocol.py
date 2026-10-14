"""Trusted DKVB protocol: synthetic deterministic routing through real PG publication."""

from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from app.legacy_execution.runner import run_diagnosis
from app.agents.trusted_protocol import PROFILE
from app.config import Settings
from app.domain.policies import DomainError
from app.infrastructure.orm import cases as cases_table
from app.infrastructure.orm import diagnosis_publications, diagnosis_steps
from app.services.diagnosis_service import DiagnosisService, StartDiagnosis
from app.services.protocol_service import ProtocolService
from sqlalchemy import func, select
from test_document_ingest import docrig as docrig  # noqa: F401
from test_evidence_measurement import bind, post, review
from test_evidence_measurement import indexed_rig as indexed_rig

pytestmark = pytest.mark.database
SOURCE = Path(__file__).resolve().parents[1] / "fixtures/diagnosis-slice/dkvb-guided.md"
SETTINGS = Settings(app_mode="test", retrieval_profile="synthetic")


def prepare_source(r):
    body = r.upload(SOURCE.read_bytes()).json()
    r.complete(body)
    scope = {"model": PROFILE["model"], "year_from": PROFILE["year"], "year_to": PROFILE["year"],
             "engine_family": PROFILE["engine_family"], "engine_code": PROFILE["engine_code"]}
    queued = review(r, body, scope=scope)
    assert queued.status_code == 202, queued.text
    proc, _ = r.worker(dict(body, run_id=queued.json()["index_run_id"]), lease=30)
    assert proc.wait(timeout=60) == 0
    return body


def prepare_case(r, body):
    response = post(r, "cases", {"vehicle": PROFILE,
        "fault_description": "【DEMO】探岳 DKVB 加速无力，报码 P0299", "fault_codes": ["P0299"],
        "diagnosis_mode": "conservative", "policy_version": "r1"})
    assert response.status_code == 201, response.text
    return response.json()


def execute(r, run_id):
    r.store.settings = SETTINGS
    r.store.lease_seconds = 60
    lease = r.store.claim_legacy("trusted-protocol-test", run_id=UUID(run_id))
    assert lease is not None
    try:
        result = run_diagnosis(r.store, lease, Event(), settings=SETTINGS)
        assert result["accepted"] and result["tool_call_count"] == 0
        r.store.finish(lease, result=result)
        return result
    finally:
        lease.close()


def start(r, case):
    rid = DiagnosisService(r.store.engine, SETTINGS).start(r.actor, UUID(case["id"]),
        StartDiagnosis(expected_revision=case["revision"]), uuid4().hex)[1]["run_id"]
    execute(r, rid)
    return r.client.get(f"/api/v2/cases/{case['id']}/diagnosis").json()


def submit(r, case_id, diagnosis, choice, fields=None, key=None):
    option = diagnosis["current_step"]["validation"]["protocol"]["options"][choice]
    body = {"expected_revision": diagnosis["revision"], "graph_epoch": diagnosis["graph_epoch"],
            "step_id": diagnosis["current_step"]["id"], "kind": "choice",
            "option_id": option["option_id"], "conditions": diagnosis["current_step"]["required_conditions"],
            "protocol_fields": fields or {}}
    response = post(r, f"cases/{case_id}/observations", body, key=key)
    return response, body


def test_guided_branches_two_steps_replay_and_forgery(indexed_rig):
    r = indexed_rig
    source = prepare_source(r)
    cases = []
    for choice, fields, expected, decision in [
        (0, {"leak_object_id":"CAC-HOSE-DEMO","leak_location":"右侧连接处",
             "evidence_kind":"visual"}, "CHK-06", "next_check"),
        (2, {}, "CHK-05-SUPPLEMENT", "need_input"),
    ]:
        case = prepare_case(r, source)
        first = start(r, case)
        assert first["current_step"]["validation"]["protocol"]["next_check_id"] == "CHK-05"
        response, _ = submit(r, case["id"], first, choice, fields)
        assert response.status_code == 202, response.text
        execute(r, response.json()["run_id"])
        current = r.client.get(f"/api/v2/cases/{case['id']}/diagnosis").json()
        protocol = current["current_step"]["validation"]["protocol"]
        assert protocol["next_check_id"] == expected and protocol["decision"] == decision
        with r.store.engine.connect() as c:
            count = c.execute(select(func.count()).select_from(diagnosis_publications).where(
                diagnosis_publications.c.run_id == UUID(response.json()["run_id"]))).scalar_one()
        assert count == 1
        cases.append((case, current))

    # CHK-06 proves the protocol continues beyond one static successor card.
    localized_case, second = cases[0]
    response, _ = submit(r, localized_case["id"], second, 0, {
        "repair_object": "CAC-HOSE-DEMO", "repair_action": "重新正确装配虚拟接头"})
    assert response.status_code == 202
    execute(r, response.json()["run_id"])
    third = r.client.get(f"/api/v2/cases/{localized_case['id']}/diagnosis").json()
    assert third["current_step"]["validation"]["protocol"]["next_check_id"] == "CHK-07"
    assert [x["option_id"] for x in third["current_step"]["validation"]["protocol"]["options"]] == ["retest.record"]
    recovered = {"leak_result": "not_found", "symptom": "absent",
        **{f"target_{i}_hpa": "2000" for i in range(1, 4)},
        **{f"actual_{i}_hpa": "1950" for i in range(1, 4)}}
    response, _ = submit(r, localized_case["id"], third, 0, recovered)
    assert response.status_code == 202, response.text
    execute(r, response.json()["run_id"])
    fourth = r.client.get(f"/api/v2/cases/{localized_case['id']}/diagnosis").json()
    assert fourth["current_step"]["validation"]["protocol"]["next_check_id"] == "CHK-11"
    final = {"symptom": "absent", "p0299": "absent",
        "repairs_rechecked": "completed", "conflict": "none"}
    response, _ = submit(r, localized_case["id"], fourth, 0, final)
    assert response.status_code == 202, response.text
    execute(r, response.json()["run_id"])
    complete = r.client.get(f"/api/v2/cases/{localized_case['id']}/diagnosis").json()
    assert complete["current_step"] is None
    conclusion = r.client.get(f"/api/v2/cases/{localized_case['id']}/diagnosis/areas").json()["areas"][0]["conclusion"]
    assert conclusion["content"]["protocol_terminal"]["terminal_code"] == "AREA_SUMMARY_DEMO_PASS"
    assert conclusion["content"]["protocol_terminal"]["evidence_refs"]

    unavailable_case = prepare_case(r, source)
    unavailable_first = start(r, unavailable_case)
    unavailable = post(r, f"cases/{unavailable_case['id']}/observations", {
        "expected_revision": unavailable_first["revision"],
        "graph_epoch": unavailable_first["graph_epoch"],
        "step_id": unavailable_first["current_step"]["id"],
        "kind": "unavailable", "reason": "当前没有检漏工具", "measurements": []})
    assert unavailable.status_code == 202, unavailable.text
    execute(r, unavailable.json()["run_id"])
    unavailable_areas = r.client.get(
        f"/api/v2/cases/{unavailable_case['id']}/diagnosis/areas").json()["areas"]
    assert unavailable_areas[0]["conclusion"]["content"]["protocol_terminal"]["terminal_code"] == "HANDOFF_UNAVAILABLE"

    # Missing locator fields are rejected before writes.
    guarded = prepare_case(r, source)
    first = start(r, guarded)
    rejected, _ = submit(r, guarded["id"], first, 0, {"leak_object_id":"hose"})
    assert rejected.status_code == 422 and rejected.json()["error"]["code"] == "PROTOCOL_FIELDS_MISSING"

    # Idempotency replays the same observation/child run only once.
    key = uuid4().hex
    fields = {"leak_object_id":"CAC-HOSE-DEMO","leak_location":"右侧连接处","evidence_kind":"touch"}
    accepted, body = submit(r, guarded["id"], first, 0, fields, key)
    replay = post(r, f"cases/{guarded['id']}/observations", body, key=key)
    assert accepted.status_code == 202 and replay.json() == accepted.json()

    # Browser/model cannot submit a transition identity.
    forged = prepare_case(r, source)
    current = start(r, forged)
    body = {"expected_revision": current["revision"], "graph_epoch": current["graph_epoch"],
            "step_id": current["current_step"]["id"], "kind": "choice", "choice_index": 1,
            "conditions": current["current_step"]["required_conditions"],
            "protocol_fields": {}, "transition_id": "FORGED"}
    response = post(r, f"cases/{forged['id']}/observations", body)
    assert response.status_code == 422

    # Changing presentation text cannot select a different transition.
    title_case = prepare_case(r, source)
    title_first = start(r, title_case)
    with r.store.engine.begin() as c:
        step_id = UUID(title_first["current_step"]["id"])
        stored = c.execute(select(diagnosis_steps.c.candidate_json).where(
            diagnosis_steps.c.id == step_id)).scalar_one()
        c.execute(diagnosis_steps.update().where(diagnosis_steps.c.id == step_id).values(
            candidate_json={**stored, "title": "任意改写标题不会改变协议分支"}))
    response, _ = submit(r, title_case["id"], title_first, 1)
    execute(r, response.json()["run_id"])
    assert r.client.get(f"/api/v2/cases/{title_case['id']}/diagnosis").json()["current_step"] is None
    conclusion = r.client.get(f"/api/v2/cases/{title_case['id']}/diagnosis/areas").json()["areas"][0]["conclusion"]
    assert conclusion["content"]["protocol_terminal"]["terminal_code"] == "HANDOFF_CONTROL_DIRECTION"

    # A corrected CHK-05 observation creates a new epoch and reroutes from the
    # current replacement fact rather than retaining the obsolete successor.
    corrected_case = prepare_case(r, source)
    corrected_first = start(r, corrected_case)
    response, _ = submit(r, corrected_case["id"], corrected_first, 0, {
        "leak_object_id":"CAC-HOSE-DEMO", "leak_location":"右侧连接处",
        "evidence_kind":"visual"})
    execute(r, response.json()["run_id"])
    before = r.client.get(f"/api/v2/cases/{corrected_case['id']}/diagnosis").json()
    observations = r.client.get(f"/api/v2/cases/{corrected_case['id']}/observations").json()
    original = next(item for item in observations["items"] if item["effective"])
    correction = post(r, f"cases/{corrected_case['id']}/observations/{original['id']}/correct", {
        "expected_revision": before["revision"], "graph_epoch": before["graph_epoch"],
        "step_id": original["step_id"], "kind": "choice", "option_id": "leak.not_found",
        "conditions": original["required_conditions"], "measurements": [],
        "protocol_fields": {}, "correction_reason": "演示中更正为未发现局部漏点"})
    assert correction.status_code == 202, correction.text
    execute(r, correction.json()["run_id"])
    after = r.client.get(f"/api/v2/cases/{corrected_case['id']}/diagnosis").json()
    assert after["graph_epoch"] == before["graph_epoch"] + 1
    assert after["current_step"] is None

    # Frozen material and vehicle scope are checked again at route time.
    profile_case = prepare_case(r, source)
    profile_first = start(r, profile_case)
    response, _ = submit(r, profile_case["id"], profile_first, 1)
    with r.store.engine.begin() as c:
        vehicle = c.execute(select(cases_table.c.vehicle_json).where(
            cases_table.c.id == UUID(profile_case["id"]))).scalar_one()
        c.execute(cases_table.update().where(cases_table.c.id == UUID(profile_case["id"])).values(
            vehicle_json={**vehicle, "engine_code": "WRONG-DEMO"}))
    r.store.settings = SETTINGS
    lease = r.store.claim_legacy("trusted-protocol-negative", run_id=UUID(response.json()["run_id"]))
    assert lease is not None
    try:
        with pytest.raises(DomainError, match="Vehicle profile changed") as caught:
            run_diagnosis(r.store, lease, Event(), settings=SETTINGS)
        assert caught.value.code == "PROTOCOL_PROFILE_MISMATCH"
    finally:
        lease.close()

    # Revoking an originally valid source invalidates every bounded candidate;
    # the protocol never publishes from a stale evidence snapshot.
    revoked_case = prepare_case(r, source)
    revoked_first = start(r, revoked_case)
    response, _ = submit(r, revoked_case["id"], revoked_first, 1)
    revoked = review(r, source, "revoked")
    assert revoked.status_code == 200, revoked.text
    r.store.settings = SETTINGS
    lease = r.store.claim_legacy("trusted-protocol-revoked", run_id=UUID(response.json()["run_id"]))
    assert lease is not None
    try:
        with pytest.raises(DomainError) as caught:
            run_diagnosis(r.store, lease, Event(), settings=SETTINGS)
        assert caught.value.code == "PROTOCOL_CANDIDATE_REJECTED"
    finally:
        lease.close()

    # Hidden answers and future observations are absent from the only indexed
    # fixture and protocol turns invoke neither tools nor model calls.
    text = SOURCE.read_text(encoding="utf-8")
    assert "expected.json" not in text and "未来观察" not in text and "隐藏答案" not in text

