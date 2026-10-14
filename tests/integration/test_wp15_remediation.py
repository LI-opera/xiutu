"""WP-15 remediation coverage for immutable PDF source access."""

import os
from uuid import UUID, uuid4

from app.config import Settings
from app.domain.measurements import BindEvidence
from app.domain.schemas import CreateCase
from app.infrastructure.orm import chunk_embeddings, chunks
from app.legacy_case_creation import LegacyCaseService as CaseService
from app.services.evidence_service import EvidenceService
from sqlalchemy import select
from test_document_ingest import docrig  # noqa: F401
from test_evidence_measurement import (  # noqa: F401
    VEHICLE,
    indexed_rig,
    review,
)
from wp04_fixtures import pdf_bytes


def test_archived_pdf_evidence_read_preserves_version_and_rejects_new_bind(indexed_rig):  # noqa: F811
    r = indexed_rig
    uploaded = r.upload(
        pdf_bytes(("text", "text")),
        name="synthetic-two-pages.pdf",
        meta={
            "title": "synthetic PDF",
            "source_kind": "synthetic_fixture",
            "source_reference": "generated locally",
            "source_status": "unknown",
            "license_status": "unknown",
            "scope": {
                "model": "SYNTHETIC-M",
                "year_from": 2020,
                "year_to": 2022,
                "engine_family": "SYNTH-F",
                "engine_code": "SYNTH-C",
            },
            "synthetic": True,
        },
    ).json()
    parsed = r.complete(uploaded)
    assert parsed["page_count"] == 2
    reviewed = review(r, uploaded)
    assert reviewed.status_code == 202, reviewed.text
    worker, _ = r.worker(dict(uploaded, run_id=reviewed.json()["index_run_id"]), lease=10)
    assert worker.wait(timeout=30) == 0

    _, case = CaseService(r.store.engine, b"synthetic", profile="synthetic").create(
        r.actor,
        CreateCase(vehicle=VEHICLE, fault_description="SYNTHETIC archived PDF evidence"),
        uuid4().hex,
    )
    with r.store.engine.connect() as conn:
        indexed = conn.execute(
            select(chunks, chunk_embeddings.c.index_id)
            .join(chunk_embeddings, chunk_embeddings.c.chunk_id == chunks.c.id)
            .where(chunks.c.document_version_id == UUID(uploaded["version_id"]))
        ).mappings().all()
    hit = next(item for item in indexed if item["locator_json"]["page"] == 2)
    payload = {
        "chunk_id": hit["id"],
        "document_version_id": hit["document_version_id"],
        "index_id": hit["index_id"],
        "quote": hit["text"],
        "start": 0,
        "end": len(hit["text"]),
    }
    binding = BindEvidence(**payload)
    _, evidence = EvidenceService(
        r.store.engine,
        Settings(
            app_mode="test",
            retrieval_profile="synthetic",
            database_url=os.environ["TEST_DATABASE_URL"],
        ),
    ).bind(r.actor, UUID(case["id"]), binding, uuid4().hex)
    denied = r.client.post(
        f"/api/v2/cases/{case['id']}/evidence",
        headers=dict(r.headers, **{"Idempotency-Key": uuid4().hex}),
        json=binding.model_dump(mode="json"),
    )
    assert denied.status_code == 409, denied.text
    assert denied.json()["error"]["code"] == "LEGACY_CASE_READ_ONLY"
    assert evidence["source_access"] == {
        "kind": "pdf",
        "status": "available",
        "page": 2,
        "page_count": 2,
        "needs_ocr": False,
        "content_url": evidence["source_content_url"],
        "page_image_url": None,
        "page_image_status": "unavailable",
    }
    assert evidence["source_content_url"].endswith("?page=2#page=2")

    # A later version cannot replace the immutable evidence/version URL.
    later = r.upload(
        pdf_bytes(("text",)),
        name="synthetic-two-pages.pdf",
        meta={
            "document_id": uploaded["document_id"],
            "title": "synthetic PDF v2",
            "source_kind": "synthetic_fixture",
            "source_reference": "generated locally",
            "source_status": "unknown",
            "license_status": "unknown",
            "scope": {"model": "SYNTHETIC-M"},
            "synthetic": True,
        },
    ).json()
    r.complete(later)
    reread = r.client.get(f"/api/v2/evidence/{evidence['evidence_id']}").json()
    assert reread["snapshot"]["document_version_id"] == uploaded["version_id"]
    assert reread["source_access"]["page"] == 2
    assert f"/versions/{uploaded['version_id']}/content" in reread["source_content_url"]
    assert later["version_id"] not in reread["source_content_url"]

