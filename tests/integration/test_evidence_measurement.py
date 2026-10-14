"""Synthetic fixtures only; real HTTP, database and separate indexing worker."""

import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from app.config import Settings
from app.domain.measurements import BindEvidence
from app.domain.schemas import CreateCase
from app.infrastructure.orm import case_evidence, chunk_embeddings, chunks, measurement_specs
from app.legacy_case_creation import LegacyCaseService as CaseService
from app.services.evidence_service import EvidenceService
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from test_document_ingest import docrig  # noqa: F401

pytestmark = pytest.mark.database


@pytest.fixture
def indexed_rig(monkeypatch, request):
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.setenv("RETRIEVAL_PROFILE", "synthetic")
    return request.getfixturevalue("docrig")


SCOPE = dict(
    model="SYNTHETIC-M",
    year_from=2020,
    year_to=2022,
    engine_family="SYNTH-F",
    engine_code="SYNTH-C",
)
VEHICLE = dict(model="SYNTHETIC-M", year=2021, engine_family="SYNTH-F", engine_code="SYNTH-C")
CONTENT = "SYNTHETIC ONLY: voltage 1 to 2 V with engine off; not a repair specification."


def post(r, path, body, key=None):
    return r.client.post(
        "/api/v2/" + path,
        headers=dict(r.headers, **{"Idempotency-Key": key or uuid4().hex}),
        json=body,
    )


def document(r, scope=None):
    body = r.upload(CONTENT.encode()).json()
    r.complete(body)
    reviewed = review(r, body, scope=scope or SCOPE)
    assert reviewed.status_code == 202, reviewed.text
    p, _ = r.worker(dict(body, run_id=reviewed.json()["index_run_id"]), lease=10)
    assert p.wait(timeout=30) == 0
    return body


def review(r, body, decision="approved", scope=None):
    return r.client.post(
        r.path(body) + "/review",
        headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
        json=dict(
            decision=decision,
            scope=scope or SCOPE,
            source_status="unknown",
            license_status="unknown",
            review_note="Synthetic fixture, not real repair approval",
        ),
    )


def create_case(r, vehicle=None):
    response = post(
        r,
        "cases",
        dict(
            vehicle=vehicle or VEHICLE, fault_description="SYNTHETIC no real repair", fault_codes=[]
        ),
    )
    assert response.status_code == 201, response.text
    return response.json()


def citation(r, case):
    found = post(r, "cases/" + case["id"] + "/evidence/search", dict(query="voltage", top_k=5))
    assert found.status_code == 200, found.text
    chunk = found.json()["chunks"][0]
    return dict(
        chunk_id=chunk["chunk_id"],
        document_version_id=chunk["document_version_id"],
        index_id=chunk["index_id"],
        quote=chunk["text"],
        start=0,
        end=len(chunk["text"]),
    )


def bind(r, case, quote):
    response = post(r, "cases/" + case["id"] + "/evidence", quote)
    assert response.status_code in [200, 201], response.text
    return response.json()


def archived_case(r, vehicle=None):
    """Build an isolated synthetic history fixture without the retired public case writer."""
    status, case = CaseService(r.store.engine, b"synthetic", profile="synthetic").create(
        r.actor,
        CreateCase(vehicle=vehicle or VEHICLE, fault_description="SYNTHETIC archived tool fixture"),
        uuid4().hex,
    )
    assert status == 201
    return case


def archived_citation(r, case):
    """Find a chunk in this case's frozen manifest without old case-level search."""
    manifest = case["corpus_manifest"]
    assert len(manifest) == 1
    with r.store.engine.connect() as conn:
        hit = (
            conn.execute(
                select(chunks, chunk_embeddings.c.index_id)
                .join(chunk_embeddings, chunk_embeddings.c.chunk_id == chunks.c.id)
                .where(
                    chunk_embeddings.c.index_id == UUID(manifest[0]["index_id"]),
                    chunks.c.document_version_id == UUID(manifest[0]["document_version_id"]),
                )
            )
            .mappings()
            .first()
        )
    assert hit is not None
    return dict(
        chunk_id=str(hit["id"]),
        document_version_id=str(hit["document_version_id"]),
        index_id=str(hit["index_id"]),
        quote=hit["text"],
        start=0,
        end=len(hit["text"]),
    )


def archived_bind(r, case, quote):
    """Create a historical evidence row internally; current public bind stays retired."""
    status, evidence = EvidenceService(
        r.store.engine,
        Settings(
            app_mode="test",
            retrieval_profile="synthetic",
            database_url=r.env["DATABASE_URL"],
        ),
    ).bind(r.actor, UUID(case["id"]), BindEvidence(**quote), uuid4().hex)
    assert status in (200, 201)
    return evidence


def spec(r, evidence, **extra):
    data = dict(
        evidence_id=evidence["evidence_id"],
        component_key="SYNTHETIC-COMPONENT",
        quantity="voltage",
        unit="V",
        lower="1",
        upper="2",
        lower_inclusive=True,
        upper_inclusive=True,
        conditions={"engine": "off"},
    )
    data.update(extra)
    response = post(r, "measurement-specs", data)
    assert response.status_code == 201, response.text
    return response.json()


def compare(r, sid, **extra):
    body = dict(value="1000", quantity="voltage", unit="mV", conditions={"engine": "off"})
    body.update(extra)
    response = post(r, "measurement-specs/" + sid + "/compare", body)
    assert response.status_code == 201, response.text
    return response.json()


def approve(r, sid):
    return post(
        r,
        "measurement-specs/" + sid + "/review",
        dict(decision="approved", note="Synthetic test review only"),
    )


def record(name, value):
    path = os.environ.get("WP06_EVIDENCE")
    if path:
        with (Path(path) / (name + "-" + uuid4().hex[:8] + ".json")).open(
            "x", encoding="utf-8"
        ) as f:
            json.dump(value, f, ensure_ascii=False, indent=2, default=str)


def test_archived_evidence_and_measurement_snapshots_are_immutable(indexed_rig):
    """Existing historical references stay readable and cannot be overwritten."""
    r = indexed_rig
    uploaded = document(r)
    _, case = CaseService(r.store.engine, b"synthetic", profile="synthetic").create(
        r.actor,
        CreateCase(vehicle=VEHICLE, fault_description="SYNTHETIC archived evidence"),
        uuid4().hex,
    )
    with r.store.engine.connect() as conn:
        hit = (
            conn.execute(
                select(chunks, chunk_embeddings.c.index_id)
                .join(chunk_embeddings, chunk_embeddings.c.chunk_id == chunks.c.id)
                .where(chunks.c.document_version_id == UUID(uploaded["version_id"]))
            )
            .mappings()
            .first()
        )
    assert hit is not None
    binding = BindEvidence(
        chunk_id=hit["id"],
        document_version_id=hit["document_version_id"],
        index_id=hit["index_id"],
        quote=hit["text"],
        start=0,
        end=len(hit["text"]),
    )
    _, evidence = EvidenceService(
        r.store.engine,
        Settings(
            app_mode="test",
            retrieval_profile="synthetic",
            database_url=r.env["DATABASE_URL"],
        ),
    ).bind(r.actor, UUID(case["id"]), binding, uuid4().hex)
    sid = spec(r, evidence)["spec"]["id"]

    with pytest.raises(DBAPIError):
        with r.store.engine.begin() as conn:
            conn.execute(
                update(case_evidence)
                .where(case_evidence.c.id == UUID(evidence["evidence_id"]))
                .values(quote="tampered")
            )
    with pytest.raises(DBAPIError):
        with r.store.engine.begin() as conn:
            conn.execute(
                update(measurement_specs)
                .where(measurement_specs.c.id == UUID(sid))
                .values(upper_value=99)
            )

    historical = r.client.get(f"/api/v2/evidence/{evidence['evidence_id']}")
    assert historical.status_code == 200
    assert historical.json()["snapshot"]["quote"] == binding.quote
    saved_spec = r.client.get(f"/api/v2/measurement-specs/{sid}")
    assert saved_spec.status_code == 200
    assert saved_spec.json()["spec"]["upper_value"] == "2"
    denied = post(r, f"cases/{case['id']}/evidence", binding.model_dump(mode="json"))
    assert denied.status_code == 409
    assert denied.json()["error"]["code"] == "LEGACY_CASE_READ_ONLY"
