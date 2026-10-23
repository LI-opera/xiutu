"""Upload a Markdown manual for a vehicle -> worker chunks and embeds it -> versions."""
from uuid import UUID, uuid4

import pytest
from app.infrastructure.orm import area_reference_chunk_vectors, area_reference_chunks
from app.services import reference_ingest, reference_store
from app.worker import Worker
from sqlalchemy import func, select


pytestmark = pytest.mark.database

VEHICLE = {"brand": "大众", "model": "测试车", "year": 2020, "engine_code": "TEST1"}
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


@pytest.fixture
def doc_id():
    """The test database is shared: every test uses its own document."""
    return "demo-ingest-" + uuid4().hex[:12]


def upload(rig, default_id, content=BODY, **extra):
    body = {"document_id": extra.pop("document_id", default_id), "title": "演示资料", "filename": "demo.md",
            "content": content, "vehicle": VEHICLE, **extra}
    return rig.client.post("/api/v2/area-references", json=body, headers=rig.headers)


def new_version(rig, document_id, content):
    return rig.client.post(f"/api/v2/area-references/{document_id}/versions",
                           json={"content": content, "filename": "v2.md"}, headers=rig.headers)


def run_worker(rig, run_id):
    assert Worker(rig.store).once(run_id=UUID(run_id))


def item(rig, document_id, version):
    items = rig.client.get("/api/v2/area-references").json()["items"]
    return next(i for i in items if i["document_id"] == document_id and i["version"] == version)


def test_upload_processes_and_versions(api_rig, fake_embedder, doc_id):  # noqa: F811
    first = upload(api_rig, doc_id, always_include=["## 3. 处理后怎样确认"])
    assert first.status_code == 202, first.text
    created = first.json()
    assert created["version"] == "1" and created["status"] == "queued"
    assert item(api_rig, doc_id, "1")["vehicle"] == VEHICLE

    run_worker(api_rig, created["run_id"])
    ready = item(api_rig, doc_id, "1")
    assert ready["status"] == "ready" and ready["vector_fingerprint"] == "fake-embedding-v1"
    # 1 lead, 2.1, 2.2, 3 lead: "## 2" has no text of its own before its first ###.
    assert ready["chunk_count"] == 4

    chunks = api_rig.client.get(f"/api/v2/area-references/{doc_id}/versions/1/chunks").json()["items"]
    assert [c["section"] for c in chunks if not c["searchable"]] == ["## 1. 阅读入口"]
    assert all(c["has_vector"] == c["searchable"] for c in chunks)
    outer = next(c for c in chunks if c["subsection"] == "### 2.1 外观")
    assert set(outer["identifiers"]) == {"G31", "VAG1687"}
    with api_rig.store.engine.connect() as conn:
        # Exact lookup by code runs in the database (GIN-indexed array overlap).
        hits = conn.execute(select(area_reference_chunks.c.ordinal).where(
            area_reference_chunks.c.document_id == doc_id,
            area_reference_chunks.c.identifiers.overlap(["VAG1687"]))).scalars().all()
        assert hits == [outer["ordinal"]]
        # The vehicle's manuals are what analyses choose from; the case vehicle's case/spacing don't matter.
        found = reference_store.candidates(conn, {"brand": "大众", "model": "测试车", "year": "2020", "engine_code": "test1"})
        assert [d["id"] for d in found] == [doc_id]
        assert reference_store.candidates(conn, {**VEHICLE, "year": 2021}) == []
        # A case without an engine code still finds the vehicle's manuals.
        assert [d["id"] for d in reference_store.candidates(conn, {**VEHICLE, "engine_code": None})] == [doc_id]

    again = upload(api_rig, doc_id)
    assert again.status_code == 200 and again.json()["reused"] and again.json()["version"] == "1"
    clash = upload(api_rig, doc_id, content=BODY + "\n## 4. 另一份\n\n正文。\n")
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "REFERENCE_EXISTS"

    changed = new_version(api_rig, doc_id, BODY + "\n## 4. 补充\n\n新增一节。\n")
    assert changed.status_code == 202 and changed.json()["version"] == "2"
    second = item(api_rig, doc_id, "2")
    assert second["title"] == "演示资料" and second["vehicle"] == VEHICLE
    assert second["always_include"] == ["## 3. 处理后怎样确认"]
    with api_rig.store.engine.connect() as conn:
        # While v2 is processing, analyses keep reading the ready v1.
        assert [d["version"] for d in reference_store.candidates(conn, VEHICLE)] == ["1"]
    run_worker(api_rig, changed.json()["run_id"])
    with api_rig.store.engine.connect() as conn:
        assert [d["version"] for d in reference_store.candidates(conn, VEHICLE)] == ["2"]
    assert item(api_rig, doc_id, "1")["status"] == "ready", "older versions stay for existing analyses"


def test_failed_processing_is_reported_and_can_be_retried(api_rig, monkeypatch, doc_id):  # noqa: F811
    def unavailable():
        raise reference_ingest.IngestError("MODEL_PATH_UNAVAILABLE")
    monkeypatch.setattr(reference_ingest, "load_embedder", unavailable)
    created = upload(api_rig, doc_id).json()
    run_worker(api_rig, created["run_id"])
    failed = item(api_rig, doc_id, created["version"])
    assert failed["status"] == "failed" and failed["error_code"] == "MODEL_PATH_UNAVAILABLE"
    with api_rig.store.engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(area_reference_chunk_vectors).where(
            area_reference_chunk_vectors.c.document_id == doc_id)).scalar_one() == 0
        assert all(d["id"] != doc_id for d in reference_store.candidates(conn, VEHICLE))

    monkeypatch.setattr(reference_ingest, "load_embedder", lambda: (FakeModel(), "fake-embedding-v1"))
    retry = upload(api_rig, doc_id)
    assert retry.status_code == 200 and retry.json()["status"] == "queued" and retry.json()["run_id"]
    run_worker(api_rig, retry.json()["run_id"])
    assert item(api_rig, doc_id, created["version"])["status"] == "ready"


@pytest.mark.parametrize("change,code", [
    ({"content": "# 没有章节\n\n正文"}, "REFERENCE_NO_SECTIONS"),
    ({"always_include": ["## 9. 不存在"]}, "REFERENCE_SECTION_NOT_FOUND"),
    ({"document_id": "Bad ID"}, "REFERENCE_ID_INVALID"),
    ({"vehicle": {**VEHICLE, "model": "  "}}, "REFERENCE_VEHICLE_REQUIRED"),
])
def test_invalid_uploads_are_refused_without_rows(api_rig, change, code, doc_id):  # noqa: F811
    response = upload(api_rig, doc_id, **change)
    assert response.status_code == 422 and response.json()["error"]["code"] == code
    assert not [i for i in api_rig.client.get("/api/v2/area-references").json()["items"]
                if i["document_id"] == doc_id]


def test_new_version_of_an_unknown_manual_is_refused(api_rig, doc_id):  # noqa: F811
    response = new_version(api_rig, doc_id, BODY)
    assert response.status_code == 404 and response.json()["error"]["code"] == "REFERENCE_NOT_FOUND"


def test_known_vehicles_include_template_vehicles(api_rig):  # noqa: F811
    response = api_rig.client.get("/api/v2/area-references/vehicles")
    assert response.status_code == 200
    vehicles = response.json()["vehicles"]
    assert vehicles and all(set(v) == {"brand", "model", "year", "engine_code"} for v in vehicles)
