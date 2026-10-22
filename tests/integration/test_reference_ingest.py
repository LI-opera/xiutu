"""Upload a Markdown manual -> worker chunks and embeds it -> it becomes the area's document."""
from uuid import UUID, uuid4

import pytest
from app.infrastructure.orm import (
    area_reference_bindings,
    area_reference_chunk_vectors,
    area_reference_chunks,
    workbench_templates,
)
from app.services import reference_ingest
from app.worker import Worker
from sqlalchemy import func, select

from test_document_ingest import docrig  # noqa: F401  Reuse the isolated API/auth process fixture.

pytestmark = pytest.mark.database

BODY = """# 演示资料

## 1. 阅读入口

本节只是导航，不参与检索。

## 2. 检查 G31 插头

### 2.1 外观

检查 G31 插头锁止，必要时用 V.A.G 1687 低压检漏。

### 2.2 记录

记录插头状态。

## 3. 处理后怎样确认

复检时在原工况下采集三帧。
"""


class FakeModel:
    def embed_documents(self, texts):
        return [[1.0, float(len(t) % 7 + 1), 0.5] for t in texts]


@pytest.fixture
def fake_embedder(monkeypatch):
    monkeypatch.setattr(reference_ingest, "load_embedder", lambda: (FakeModel(), "fake-embedding-v1"))


def first_area(rig):
    with rig.store.engine.connect() as conn:
        row = conn.execute(select(workbench_templates).order_by(
            workbench_templates.c.template_id, workbench_templates.c.version)).mappings().first()
    assert row is not None, "templates are installed in the isolated database"
    return {"template_id": row["template_id"], "template_version": row["version"],
            "area_id": row["content_json"]["areas"][0]["id"]}


@pytest.fixture
def doc_id():
    """The test database is shared: every test uses its own document."""
    return "demo-ingest-" + uuid4().hex[:12]


def upload(rig, default_id, content=BODY, **extra):
    body = {"document_id": extra.pop("document_id", default_id), "title": "演示资料", "filename": "demo.md",
            "content": content, "areas": [first_area(rig)], **extra}
    return rig.client.post("/api/v2/area-references", json=body, headers=rig.headers)


def run_worker(rig, run_id):
    assert Worker(rig.store).once(run_id=UUID(run_id))


def bound_version(rig, area, document_id):
    with rig.store.engine.connect() as conn:
        return conn.execute(select(area_reference_bindings.c.document_version).where(
            area_reference_bindings.c.template_id == area["template_id"],
            area_reference_bindings.c.template_version == area["template_version"],
            area_reference_bindings.c.area_id == area["area_id"],
            area_reference_bindings.c.document_id == document_id)).scalar_one_or_none()


def item(rig, document_id, version):
    items = rig.client.get("/api/v2/area-references").json()["items"]
    return next(i for i in items if i["document_id"] == document_id and i["version"] == version)


def test_upload_processes_binds_and_versions(docrig, fake_embedder, doc_id):  # noqa: F811
    area = first_area(docrig)
    first = upload(docrig, doc_id, always_include=["## 3. 处理后怎样确认"])
    assert first.status_code == 202, first.text
    created = first.json()
    assert created["version"] == "1" and created["status"] == "queued"
    # Queued versions are listed but not bound to any area yet.
    assert item(docrig, doc_id, "1")["status"] == "queued" and bound_version(docrig, area, doc_id) is None

    run_worker(docrig, created["run_id"])
    ready = item(docrig, doc_id, "1")
    assert ready["status"] == "ready" and ready["vector_fingerprint"] == "fake-embedding-v1"
    # 1 lead, 2.1, 2.2, 3 lead: "## 2" has no text of its own before its first ###.
    assert ready["chunk_count"] == 4 and area in ready["bound_areas"]
    assert bound_version(docrig, area, doc_id) == "1"

    chunks = docrig.client.get(f"/api/v2/area-references/{doc_id}/versions/1/chunks").json()["items"]
    navigation = [c for c in chunks if not c["searchable"]]
    assert [c["section"] for c in navigation] == ["## 1. 阅读入口"]
    assert all(c["has_vector"] == c["searchable"] for c in chunks)
    outer = next(c for c in chunks if c["subsection"] == "### 2.1 外观")
    assert set(outer["identifiers"]) == {"G31", "VAG1687"}
    with docrig.store.engine.connect() as conn:
        # Exact lookup by code runs in the database (GIN-indexed array overlap).
        hits = conn.execute(select(area_reference_chunks.c.ordinal).where(
            area_reference_chunks.c.document_id == doc_id,
            area_reference_chunks.c.identifiers.overlap(["VAG1687"]))).scalars().all()
        assert hits == [outer["ordinal"]]

    again = upload(docrig, doc_id)
    assert again.status_code == 200 and again.json()["reused"] and again.json()["version"] == "1"

    changed = upload(docrig, doc_id, content=BODY + "\n## 4. 补充\n\n新增一节。\n")
    assert changed.status_code == 202 and changed.json()["version"] == "2"
    assert bound_version(docrig, area, doc_id) == "1", "the area keeps the ready version while v2 is processing"
    run_worker(docrig, changed.json()["run_id"])
    assert bound_version(docrig, area, doc_id) == "2"
    assert item(docrig, doc_id, "1")["status"] == "ready", "older versions stay for existing analyses"


def test_failed_processing_is_reported_and_can_be_retried(docrig, monkeypatch, doc_id):  # noqa: F811
    def unavailable():
        raise reference_ingest.IngestError("MODEL_PATH_UNAVAILABLE")
    monkeypatch.setattr(reference_ingest, "load_embedder", unavailable)
    area = first_area(docrig)
    created = upload(docrig, doc_id).json()
    run_worker(docrig, created["run_id"])
    failed = item(docrig, doc_id, created["version"])
    assert failed["status"] == "failed" and failed["error_code"] == "MODEL_PATH_UNAVAILABLE"
    assert bound_version(docrig, area, doc_id) is None
    with docrig.store.engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(area_reference_chunk_vectors).where(
            area_reference_chunk_vectors.c.document_id == doc_id)).scalar_one() == 0

    monkeypatch.setattr(reference_ingest, "load_embedder", lambda: (FakeModel(), "fake-embedding-v1"))
    retry = upload(docrig, doc_id)
    assert retry.status_code == 200 and retry.json()["status"] == "queued" and retry.json()["run_id"]
    run_worker(docrig, retry.json()["run_id"])
    assert item(docrig, doc_id, created["version"])["status"] == "ready"
    assert bound_version(docrig, area, doc_id) == created["version"]


@pytest.mark.parametrize("change,code", [
    ({"content": "# 没有章节\n\n正文"}, "REFERENCE_NO_SECTIONS"),
    ({"always_include": ["## 9. 不存在"]}, "REFERENCE_SECTION_NOT_FOUND"),
    ({"document_id": "Bad ID"}, "REFERENCE_ID_INVALID"),
])
def test_invalid_uploads_are_refused_without_rows(docrig, change, code, doc_id):  # noqa: F811
    response = upload(docrig, doc_id, **change)
    assert response.status_code == 422 and response.json()["error"]["code"] == code
    assert not [i for i in docrig.client.get("/api/v2/area-references").json()["items"]
                if i["document_id"] == doc_id]


def test_unknown_area_is_refused(docrig, doc_id):  # noqa: F811
    area = {**first_area(docrig), "area_id": "no-such-area"}
    response = upload(docrig, doc_id, areas=[area])
    assert response.status_code == 422 and response.json()["error"]["code"] == "AREA_NOT_FOUND"


def test_targets_list_templates_with_their_areas(docrig):  # noqa: F811
    response = docrig.client.get("/api/v2/area-references/targets")
    assert response.status_code == 200
    templates = response.json()["templates"]
    area = first_area(docrig)
    match = next(t for t in templates if (t["template_id"], t["version"]) ==
                 (area["template_id"], area["template_version"]))
    assert match["title"] and area["area_id"] in {a["id"] for a in match["areas"]}
    assert all(a["title"] for t in templates for a in t["areas"])
