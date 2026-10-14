"""Archived report reads remain available after legacy report writes retire."""

from uuid import uuid4

import pytest
from app.infrastructure.orm import cases, reports, runs
from sqlalchemy import update
from test_document_ingest import docrig as docrig  # noqa: F401
from test_evidence_measurement import indexed_rig as indexed_rig  # noqa: F401

pytestmark = pytest.mark.database


def test_archived_report_history_is_readable_but_not_writable(indexed_rig):
    r = indexed_rig
    case_id, run_id, report_id = uuid4(), uuid4(), uuid4()
    content = {"scope": "Synthetic archive only", "confirmed_facts": []}
    with r.store.engine.begin() as conn:
        conn.execute(cases.insert().values(
            id=case_id, owner_id=r.actor,
            vehicle_json={"model": "SYNTHETIC-M", "year": 2021},
            fault_description="Synthetic archived case", fault_codes=[],
            corpus_manifest=[], intake_snapshot={}, revision=3,
            graph_epoch=0, status="completed",
        ))
        conn.execute(runs.insert().values(
            id=run_id, owner_id=r.actor, case_id=case_id,
            kind="report", status="succeeded", input_revision=3,
        ))
        conn.execute(reports.insert().values(
            id=report_id, case_id=case_id, owner_id=r.actor,
            run_id=run_id, kind="progress", status="current",
            input_revision=3, graph_epoch=0, manifest_json=[],
            conclusion_ids=[], content_json=content,
        ))

    base = f"/api/v2/cases/{case_id}/reports"
    listed = r.client.get(base)
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["items"]] == [str(report_id)]
    assert listed.json()["items"][0]["content"] == content
    assert listed.json()["items"][0]["current_validity"] == {"valid": True, "reasons": []}

    detail = r.client.get(f"{base}/{report_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json() == listed.json()["items"][0]
    gate = r.client.get(f"{base}/gate")
    assert gate.status_code == 200, gate.text
    assert gate.json()["allowed"] is False
    assert {item["code"] for item in gate.json()["blocking_items"]} >= {"NO_EFFECTIVE_AREA"}

    denied = r.client.post(base, headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
                           json={"kind": "progress", "expected_revision": 3})
    assert denied.status_code == 409, denied.text
    assert denied.json()["error"]["code"] == "LEGACY_CASE_READ_ONLY"
    diagnosis_denied = r.client.post(
        f"/api/v2/cases/{case_id}/diagnosis/runs",
        headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
        json={"expected_revision": 3},
    )
    assert diagnosis_denied.status_code == 409, diagnosis_denied.text
    assert diagnosis_denied.json()["error"]["code"] == "LEGACY_CASE_READ_ONLY"
    preflight_denied = r.client.get(f"/api/v2/cases/{case_id}/analyses/preflight")
    assert preflight_denied.status_code == 409, preflight_denied.text
    assert preflight_denied.json()["error"]["code"] == "LEGACY_CASE_READ_ONLY"

    other, _, _ = r.api()
    assert other.get(f"/api/v2/cases/{case_id}/analyses/preflight").status_code == 404
    assert other.get(base).status_code == 404
    assert other.get(f"{base}/{report_id}").status_code == 404

    with r.store.engine.begin() as conn:
        conn.execute(update(cases).where(cases.c.id == case_id).values(revision=4))
    stale = r.client.get(f"{base}/{report_id}")
    assert stale.status_code == 200, stale.text
    assert stale.json()["status"] == "stale"
    assert stale.json()["content"] == content
    assert stale.json()["current_validity"]["reasons"] == ["revision_or_epoch_changed"]
