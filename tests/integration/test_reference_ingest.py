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


def package(document_id, guide, reviewed=True, title="涡轮增压器指南", always=("## 3. 处理后怎样确认",)):
    """The three files of an xiutu-clean guide package, as the page sends them."""
    sources = '{"schema_version": "xiutu-guide-package/1", "sources": [{"title": "涡轮增压器", "pages_cited": [3]}]}'
    files = {"guide.md": reference_ingest.file_hash(guide), "sources.json": reference_ingest.file_hash(sources)}
    review = ({"status": "approved", "reviewer": "李", "reviewed_at": "2026-11-02T10:00:00+00:00",
               "approved_hashes": dict(files)} if reviewed else
              {"status": "pending", "reviewer": None, "reviewed_at": None, "approved_hashes": None})
    manifest = {"schema_version": "xiutu-guide-package/1", "document_id": document_id, "version": "4",
                "title": title, "always_include": list(always),
                "applicability": [{"brand": VEHICLE["brand"], "model": VEHICLE["model"], "year_from": VEHICLE["year"],
                                   "year_to": VEHICLE["year"], "engine_code": VEHICLE["engine_code"]}],
                "open_gaps": [{"group": "数值", "gap": "间隙标准未给出"}], "review": review,
                "made_by": {"job": "turbo"}, "files": files}
    return {"manifest": manifest, "guide": guide, "sources": sources}


def import_package(rig, body):
    return rig.client.post("/api/v2/area-references/packages", json=body, headers=rig.headers)


def test_reviewed_package_sets_title_and_sections_of_a_new_version(api_rig, fake_embedder, doc_id):  # noqa: F811
    first = upload(api_rig, doc_id, always_include=["## 2. 检查 G31 插头"])
    run_worker(api_rig, first.json()["run_id"])

    pending = import_package(api_rig, package(doc_id, BODY.replace("\n", "\r\n") + "\r\n", reviewed=False))
    assert pending.status_code == 409 and pending.json()["error"]["code"] == "REFERENCE_PACKAGE_NOT_APPROVED"
    body = package(doc_id, BODY.replace("\n", "\r\n") + "\r\n## 4. 补充\r\n\r\n新增。\r\n")
    tampered = {**body, "guide": body["guide"] + "改动"}
    assert import_package(api_rig, tampered).json()["error"]["code"] == "REFERENCE_PACKAGE_CHANGED"

    imported = import_package(api_rig, body)
    assert imported.status_code == 202, imported.text
    assert imported.json()["version"] == "2"
    second = item(api_rig, doc_id, "2")
    assert second["title"] == "涡轮增压器指南" and second["source_kind"] == "package"
    assert second["always_include"] == ["## 3. 处理后怎样确认"], "the package's sections, not the old ones"
    assert second["package"]["reviewer"] == "李" and second["package"]["open_gaps"] == ["间隙标准未给出"]
    run_worker(api_rig, imported.json()["run_id"])
    with api_rig.store.engine.connect() as conn:
        found = reference_store.candidates(conn, VEHICLE)
        mine = next(d for d in found if d["id"] == doc_id)
        assert mine["version"] == "2" and "\r" not in mine["body"]
        assert mine["provenance"]["package"]["review"]["reviewer"] == "李"
    again = import_package(api_rig, body)
    assert again.status_code == 200 and again.json()["reused"] and again.json()["version"] == "2"


def test_reviewed_package_creates_a_new_manual(api_rig, fake_embedder, doc_id):  # noqa: F811
    imported = import_package(api_rig, package(doc_id, BODY))
    assert imported.status_code == 202 and imported.json()["version"] == "1"
    created = item(api_rig, doc_id, "1")
    assert created["vehicle"] == VEHICLE and created["package"]["package_version"] == "4"


def test_new_version_can_set_title_and_sections(api_rig, fake_embedder, doc_id):  # noqa: F811
    upload(api_rig, doc_id, always_include=["## 3. 处理后怎样确认"])
    response = api_rig.client.post(f"/api/v2/area-references/{doc_id}/versions", json={
        "content": BODY + "\n## 4. 补充\n\n新增。\n", "title": "演示资料（新）", "always_include": ["## 4. 补充"]},
        headers=api_rig.headers)
    assert response.status_code == 202, response.text
    second = item(api_rig, doc_id, "2")
    assert second["title"] == "演示资料（新）" and second["always_include"] == ["## 4. 补充"]
    missing = api_rig.client.post(f"/api/v2/area-references/{doc_id}/versions", json={
        "content": BODY + "\n## 5. 再补充\n\n正文。\n", "always_include": ["## 9. 不存在"]}, headers=api_rig.headers)
    assert missing.status_code == 422 and missing.json()["error"]["code"] == "REFERENCE_SECTION_NOT_FOUND"


def test_package_of_text_already_current_attaches_its_review(api_rig, fake_embedder, doc_id):  # noqa: F811
    first = upload(api_rig, doc_id, always_include=["## 2. 检查 G31 插头"])
    run_worker(api_rig, first.json()["run_id"])
    body = package(doc_id, BODY)  # the same text, now reviewed
    attached = import_package(api_rig, body)
    assert attached.status_code == 200 and attached.json()["reused"] and attached.json()["version"] == "1"
    current = item(api_rig, doc_id, "1")
    assert current["title"] == "涡轮增压器指南" and current["source_kind"] == "package"
    assert current["always_include"] == ["## 3. 处理后怎样确认"] and current["package"]["reviewer"] == "李"
    assert current["status"] == "ready", "the text did not change: no reprocessing"
    with api_rig.store.engine.connect() as conn:
        mine = next(d for d in reference_store.candidates(conn, VEHICLE) if d["id"] == doc_id)
        assert mine["provenance"]["upload"]["filename"] == "demo.md", "the upload record is kept"


def test_package_of_an_older_versions_text_becomes_a_new_version(api_rig, fake_embedder, doc_id):  # noqa: F811
    run_worker(api_rig, upload(api_rig, doc_id).json()["run_id"])
    run_worker(api_rig, new_version(api_rig, doc_id, BODY + "\n## 4. 补充\n\n正文。\n").json()["run_id"])
    imported = import_package(api_rig, package(doc_id, BODY))
    assert imported.status_code == 202 and imported.json()["version"] == "3"
    assert item(api_rig, doc_id, "1")["source_kind"] == "upload", "the old version is left as it was"


GUIDE = BODY + "\n## 4. 本指南的缺口与限制\n\n- G31 插头锁止力没有标准。\n"


def test_gap_list_stored_as_searchable_earlier_is_not_searched(api_rig, fake_embedder, doc_id):  # noqa: F811
    run_worker(api_rig, upload(api_rig, doc_id, content=GUIDE).json()["run_id"])
    with api_rig.store.engine.begin() as conn:
        # As stored before the gap list became navigation.
        conn.execute(area_reference_chunks.update().where(
            area_reference_chunks.c.document_id == doc_id,
            area_reference_chunks.c.section == "## 4. 本指南的缺口与限制").values(searchable=True))
    with api_rig.store.engine.connect() as conn:
        document = next(d for d in reference_store.candidates(conn, VEHICLE) if d["id"] == doc_id)
        source, _ = reference_store.load(conn, document, None)
        assert source is not None
        assert "## 4. 本指南的缺口与限制" not in {c.section for c in source.chunks}
