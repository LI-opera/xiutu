"""Free, real-DB WP-11 candidate diagnostics through the SDK MockTransport."""

import json
from threading import Event
from uuid import UUID, uuid4

import httpx
import pytest
from app.legacy_execution.runner import run_diagnosis
from app.agents.state import ProposalEnvelope
from app.config import Settings
from app.infrastructure.model_budget import BudgetLedger
from app.infrastructure.model_gateway import DeepSeekGateway, ModelError
from app.infrastructure.orm import diagnosis_publications, runs, tool_calls, tool_executions
from app.services.diagnosis_service import DiagnosisService, StartDiagnosis
from sqlalchemy import select
from test_document_ingest import docrig as docrig
from test_evidence_measurement import indexed_rig as indexed_rig
from test_wp10_proposals import FIX, prepare, synthetic_step

pytestmark = pytest.mark.database


def _completion(content):
    return httpx.Response(200, json={
        "id": "offline-wp11", "object": "chat.completion", "created": 0,
        "model": "deepseek-flash",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                     "finish_reason": "stop"}],
    })


@pytest.mark.parametrize("scenario", [
    "rejected_twice", "need_input", "schema_invalid", "valid_step",
    "interpretation_repaired", "interpretation_still_invalid",
    "interpretation_other_field_invalid", "interpretation_repair_need_input",
    "interpretation_repair_schema_invalid",
])
def test_candidate_diagnostic_actual_runner_path(indexed_rig, tmp_path, monkeypatch, scenario):
    r = indexed_rig
    r.store.lease_seconds = 60
    content = (FIX / "extra-synthetic.md").read_bytes()
    _, case, _, _, cite = prepare(r, content)
    start = DiagnosisService(r.store.engine).start(
        r.actor, UUID(case["id"]), StartDiagnosis(expected_revision=0), uuid4().hex
    )
    run_id = UUID(start[1]["run_id"])
    lease = r.store.claim_legacy("wp11-diagnostic-" + scenario, run_id=run_id)
    assert lease is not None
    settings = Settings(app_mode="test", retrieval_profile="synthetic",
                        tool_mode="local", deepseek_api_key="offline-placeholder")
    r.store.settings = settings
    valid = synthetic_step(cite)
    secret = "SYNTHETIC_PRIVATE_CANDIDATE_MARKER"
    invalid = json.loads(json.dumps(valid))
    invalid["title"] = secret
    invalid["location"] = None
    interpretation_invalid = json.loads(json.dumps(valid))
    interpretation_invalid["interpretation"] = [valid["input"]["choices"][0]]
    interpretation_invalid["title"] = "台架观察 synthetic@example.com"
    if scenario == "rejected_twice":
        candidates = [invalid, invalid]
    elif scenario == "need_input":
        candidates = [{"type": "need_input", "missing": [secret]}]
    elif scenario == "schema_invalid":
        candidates = [{"type": "propose_step", "extra": secret}, valid]
    elif scenario == "interpretation_repaired":
        candidates = [interpretation_invalid, valid]
    elif scenario == "interpretation_still_invalid":
        candidates = [interpretation_invalid, interpretation_invalid]
    elif scenario == "interpretation_other_field_invalid":
        invalid_location = json.loads(json.dumps(valid))
        invalid_location["location"] = None
        candidates = [interpretation_invalid, invalid_location]
    elif scenario == "interpretation_repair_need_input":
        candidates = [interpretation_invalid, {"type": "need_input", "missing": ["来源不足"]}]
    elif scenario == "interpretation_repair_schema_invalid":
        candidates = [interpretation_invalid, {"type": "propose_step", "extra": secret}]
    else:
        candidates = [valid]
    queue = iter(["continue", *(json.dumps(x, ensure_ascii=False) for x in candidates)])
    # A repair request is a third transport call after the initial tools and JSON calls.
    sent = []

    def transport(request):
        sent.append(json.loads(request.content))
        return _completion(next(queue))

    ledger = BudgetLedger(tmp_path / "offline-ledger.json")
    ledger.initialize("offline MockTransport only")
    events = []

    def gateway():
        return DeepSeekGateway(settings, transport=httpx.MockTransport(transport),
                               ledger=ledger, max_output_tokens=1536)

    factory_args = {}
    if scenario == "valid_step":
        # Exercise the trusted production factory call, while replacing only
        # the transport-owning factory with this free MockTransport gateway.
        def offline_factory(_settings, **kwargs):
            factory_args.update(kwargs)
            return gateway()

        monkeypatch.setenv("XIUTU_WP11_PAID", "1")
        monkeypatch.setattr("app.legacy_execution.runner.llm_factory", offline_factory)

    try:
        if scenario in {"rejected_twice", "need_input", "interpretation_still_invalid",
                        "interpretation_other_field_invalid", "interpretation_repair_need_input"}:
            with pytest.raises(ModelError, match="DIAGNOSIS_PROPOSAL_NEEDS_INPUT") as exc:
                run_diagnosis(r.store, lease, Event(), settings=settings,
                              gateway_factory=gateway, diagnostic_sink=events.append)
            r.store.finish(lease, exc.value.code, False)
        elif scenario == "interpretation_repair_schema_invalid":
            with pytest.raises(ModelError, match="MODEL_SCHEMA_INVALID") as exc:
                run_diagnosis(r.store, lease, Event(), settings=settings,
                              gateway_factory=gateway, diagnostic_sink=events.append)
            r.store.finish(lease, exc.value.code, False)
        else:
            result = run_diagnosis(
                r.store, lease, Event(), settings=settings,
                gateway_factory=None if scenario == "valid_step" else gateway,
                diagnostic_sink=events.append)
            assert result["accepted"] and result["candidate"]["type"] == "propose_step"
            r.store.finish(lease, result=result)
    finally:
        lease.close()
    expected_calls = 2 if scenario in {"need_input", "valid_step"} else 3
    if scenario == "valid_step":
        assert factory_args["max_model_calls"] == 4
        assert factory_args["resume_existing"] is True
        assert factory_args["max_output_tokens"] == settings.diagnosis_max_output_tokens
    assert len(sent) == expected_calls
    assert len(ledger.read()["calls"]) == expected_calls
    assert events[0]["stage"] == "initial"
    assert events[0]["repair_used"] is False
    assert secret not in json.dumps(events, ensure_ascii=False)
    assert all(set(event) == {
        "stage", "candidate_type", "schema_status", "disposition", "issues",
        "issue_count", "repair_used", "error_code",
    } for event in events)
    with r.store.engine.connect() as c:
        run = c.execute(select(runs).where(runs.c.id == run_id)).mappings().one()
        publications = c.execute(select(diagnosis_publications.c.id).where(
            diagnosis_publications.c.run_id == run_id)).all()
        tools = c.execute(select(tool_calls.c.tool).join(
            tool_executions, tool_executions.c.id == tool_calls.c.execution_id).where(
            tool_executions.c.run_id == run_id).order_by(tool_calls.c.call_key)).scalars().all()
    assert tools.count("search_manuals") == 1
    assert 2 <= tools.count("get_evidence_context") <= 3
    assert "complete source sentence" in sent[0]["messages"][0]["content"]
    if expected_calls == 3:
        repair_text = sent[2]["messages"][-1]["content"]
        repair_context = json.loads(repair_text.split("Repair context: ", 1)[1])
        assert set(repair_context) == {"rejected_candidate", "issues"}
        assert all(set(issue) == {"code", "path"} for issue in repair_context["issues"])
        if scenario == "schema_invalid":
            assert repair_context["rejected_candidate"] is None
        elif scenario.startswith("interpretation_"):
            expected_candidate = ProposalEnvelope.model_validate(
                interpretation_invalid).model_dump(mode="json")
            expected_candidate["title"] = "台架观察 [EMAIL]"
            assert repair_context["rejected_candidate"] == expected_candidate
            assert interpretation_invalid["title"] == "台架观察 synthetic@example.com"
            assert "synthetic@example.com" not in repair_text
            assert repair_context["issues"] == [
                {"code": "INTERPRETATION_UNCERTAIN", "path": "interpretation"}]
            assert "empty interpretation array" in repair_text
        else:
            assert repair_context["rejected_candidate"] == ProposalEnvelope.model_validate(
                invalid).model_dump(mode="json")
    if scenario == "rejected_twice":
        assert len(events) == 2
        assert [x["candidate_type"] for x in events] == ["propose_step"] * 2
        assert all(x["disposition"] == "needs_input" for x in events)
        assert all(any(i["code"] == "LOCATION_MISSING" for i in x["issues"]) for x in events)
        assert events[-1]["repair_used"] is True
        assert run["budget_json"]["proposal_repair_used"] is True
        assert run["status"] == "failed" and not publications
    elif scenario == "need_input":
        assert len(events) == 1 and events[0]["candidate_type"] == "need_input"
        assert events[0]["disposition"] == "needs_input"
        assert run["budget_json"].get("proposal_repair_used") is not True
        assert run["status"] == "failed" and not publications
    elif scenario == "schema_invalid":
        assert len(events) == 2
        assert events[0]["schema_status"] == "invalid"
        assert events[0]["error_code"] == "MODEL_SCHEMA_INVALID"
        assert events[1]["candidate_type"] == "propose_step"
        assert events[1]["repair_used"] is True
        assert run["budget_json"]["proposal_repair_used"] is True
        assert run["status"] == "waiting_input" and len(publications) == 1
    elif scenario.startswith("interpretation_"):
        assert events[0]["candidate_type"] == "propose_step"
        assert events[0]["issues"] == [
            {"code": "INTERPRETATION_UNCERTAIN", "path": "interpretation"}]
        assert events[1]["repair_used"] is True
        assert run["budget_json"]["proposal_repair_used"] is True
        if scenario == "interpretation_repaired":
            assert events[1]["disposition"] == "candidate"
            assert run["status"] == "waiting_input" and len(publications) == 1
        elif scenario == "interpretation_repair_need_input":
            assert events[1]["candidate_type"] == "need_input"
            assert run["status"] == "failed" and not publications
        elif scenario == "interpretation_repair_schema_invalid":
            assert events[1]["schema_status"] == "invalid"
            assert events[1]["error_code"] == "MODEL_SCHEMA_INVALID"
            assert run["status"] == "failed" and not publications
        else:
            expected = ("INTERPRETATION_UNCERTAIN" if scenario.endswith("still_invalid")
                        else "LOCATION_MISSING")
            assert any(issue["code"] == expected for issue in events[1]["issues"])
            assert run["status"] == "failed" and not publications
    else:
        assert len(events) == 1 and events[0]["candidate_type"] == "propose_step"
        assert events[0]["disposition"] == "candidate"
        assert run["status"] == "waiting_input" and len(publications) == 1

    # Error responses and SSE contain only the public error code, never the
    # internal issue identifiers, candidate marker, or private diagnostic trace.
    response = r.client.get(f"/api/v2/runs/{run_id}")
    assert response.status_code == 200
    public = json.dumps(response.json(), ensure_ascii=False)
    assert secret not in public and "LOCATION_MISSING" not in public
    stream = r.client.get(f"/api/v2/runs/{run_id}/events")
    assert stream.status_code == 200
    assert secret not in stream.text and "LOCATION_MISSING" not in stream.text
