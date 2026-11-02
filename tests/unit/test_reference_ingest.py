"""Reference ingest without a database: chunking matches retrieval, validation, embedding batches."""
import json
import threading

import pytest
from app.domain.policies import DomainError
from app.retrieval.section_search import split
from app.services import reference_ingest as ri
from app.services.reference_ingest import IngestError
from app.services.retrieval_reading import NAVIGATION

from scripts.seed_area_references import DEFAULT_PACKAGE, READING, always_include, build_documents, load_manuals

DOCUMENTS = [doc for _, doc in build_documents(DEFAULT_PACKAGE, load_manuals())]


@pytest.mark.parametrize("doc", DOCUMENTS, ids=[d["document_id"] for d in DOCUMENTS])
def test_stored_searchable_chunks_are_exactly_what_retrieval_searches(doc):
    built = ri.build_chunks(doc["document_id"], doc["body"])
    assert [c["ordinal"] for c in built] == list(range(len(built)))
    searched = split(doc["document_id"], doc["body"], NAVIGATION)
    kept = [c for c in built if c["searchable"]]
    assert [(c["section"], c["subsection"], c["text"], c["char_start"], c["char_end"]) for c in kept] == [
        (c.section, c.subsection, c.text, c.start, c.end) for c in searched]
    assert [set(c["identifiers"]) for c in kept] == [c.identifiers for c in searched]
    assert [c["search_text"] for c in kept] == [c.search_text for c in searched]
    # Navigation sections are stored for the record but never searched.
    assert any(not c["searchable"] for c in built)
    for c in built:
        assert doc["body"][c["char_start"]:c["char_end"]].strip() == c["text"]
        assert c["search_hash"] == ri.content_hash(c["search_text"])


@pytest.mark.parametrize("doc", DOCUMENTS, ids=[d["document_id"] for d in DOCUMENTS])
def test_real_documents_and_their_always_included_sections_validate(doc):
    sections = always_include(doc)
    assert sections, "every seeded document has reviewed always-sent sections"
    ri.validate_content(doc["body"], sections)


def test_uploaded_text_is_normalized_like_seeded_files():
    doc = DOCUMENTS[0]
    windows = "﻿" + doc["body"].replace("\n", "\r\n")
    assert ri.normalize(windows) == doc["body"]
    assert ri.content_hash(ri.normalize(windows)) == doc["content_hash"]


@pytest.mark.parametrize("body,code", [
    ("   \n", "REFERENCE_EMPTY"),
    ("# 只有标题\n\n一些正文，没有二级章节。", "REFERENCE_NO_SECTIONS"),
    ("# 标题\n\n## 1. 阅读入口\n\n只有导航章节。", "REFERENCE_NO_SECTIONS"),
])
def test_content_without_searchable_sections_is_refused(body, code):
    with pytest.raises(DomainError) as raised:
        ri.validate_content(body, [])
    assert raised.value.code == code


def test_always_included_section_must_exist():
    body = "# 标题\n\n## 1. 检查什么\n\n正文。\n\n## 2. 怎样确认\n\n正文。"
    ri.validate_content(body, ["## 2. 怎样确认"])
    with pytest.raises(DomainError) as raised:
        ri.validate_content(body, ["## 9. 不存在"])
    assert raised.value.code == "REFERENCE_SECTION_NOT_FOUND"


def test_versions_count_up_from_numeric_ones():
    assert ri.next_version([]) == "1"
    assert ri.next_version(["3", "4", "draft"]) == "5"


class FakeModel:
    def __init__(self, zero_at=None):
        self.calls, self.zero_at = [], zero_at

    def embed_documents(self, texts):
        self.calls.append(len(texts))
        return [[0.0, 0.0] if t == self.zero_at else [1.0, float(len(t))] for t in texts]


def test_only_searchable_chunks_are_embedded_in_batches():
    doc = DOCUMENTS[0]
    built = ri.build_chunks(doc["document_id"], doc["body"])
    model = FakeModel()
    result = ri.embed(built, (model, "fake-v1"))
    searchable = [c["ordinal"] for c in built if c["searchable"]]
    assert sorted(result) == searchable
    assert sum(model.calls) == len(searchable) and max(model.calls) <= ri.EMBED_BATCH


def test_zero_vectors_and_stop_requests_fail_the_ingest():
    doc = DOCUMENTS[0]
    built = ri.build_chunks(doc["document_id"], doc["body"])
    first = next(c for c in built if c["searchable"])
    with pytest.raises(IngestError) as raised:
        ri.embed(built, (FakeModel(zero_at=first["search_text"]), "fake-v1"))
    assert raised.value.code == "REFERENCE_VECTOR_EMPTY"
    stopped = threading.Event()
    stopped.set()
    with pytest.raises(IngestError) as raised:
        ri.embed(built, (FakeModel(), "fake-v1"), stopped)
    assert raised.value.code == "REFERENCE_INGEST_STOPPED"


def test_upload_body_needs_a_vehicle_and_no_areas():
    from app.api.area_references import ReferenceUpload, ReferenceVersionUpload
    vehicle = {"brand": "大众", "model": "探岳", "year": 2019, "engine_code": "DKVB"}
    base = {"document_id": "demo-doc", "title": "演示", "content": "x", "vehicle": vehicle}
    assert ReferenceUpload.model_validate(base).always_include == []
    for broken in ({**base, "vehicle": {**vehicle, "year": 1800}}, {k: v for k, v in base.items() if k != "vehicle"},
                   {**base, "areas": [{"template_id": "t", "template_version": "1", "area_id": "a"}]}):
        with pytest.raises(Exception):
            ReferenceUpload.model_validate(broken)
    # A new version may change its title and always-sent sections (carried over when left out);
    # the vehicle always carries over.
    kept = ReferenceVersionUpload.model_validate({"content": "x"})
    assert kept.title is None and kept.always_include is None
    assert ReferenceVersionUpload.model_validate({"content": "x", "title": "改名"}).title == "改名"
    with pytest.raises(Exception):
        ReferenceVersionUpload.model_validate({"content": "x", "vehicle": vehicle})


def test_vehicle_is_trimmed_and_engine_code_upper_cased():
    assert ri.normalize_vehicle({"brand": " 大众 ", "model": "探岳", "year": 2019, "engine_code": "dkvb"}) == {
        "vehicle_brand": "大众", "vehicle_model": "探岳", "vehicle_year": 2019, "vehicle_engine_code": "DKVB"}
    with pytest.raises(DomainError) as raised:
        ri.normalize_vehicle({"brand": "大众", "model": "  ", "year": 2019, "engine_code": "DKVB"})
    assert raised.value.code == "REFERENCE_VEHICLE_REQUIRED"


def test_reading_config_still_matches_seeded_bodies():
    """The seed script copies always-sent sections from this file; a body change must not drop them silently."""
    config = json.loads(READING.read_text(encoding="utf-8"))
    hashes = {(d["document_id"], d["version"]): d["content_hash"] for d in DOCUMENTS}
    for entry in config["documents"]:
        assert hashes.get((entry["id"], entry["version"])) == entry["content_hash"]


# ---------------------------------------------------------------- guide packages (xiutu-clean)

PACKAGE_BODY = "# 涡轮增压器指南\r\n\r\n## 1. 本区域检查什么\r\n\r\n正文。\r\n\r\n## 2. 检查壳体\r\n\r\n检查 V465。\r\n"


def package(**change):
    """A package as xiutu-clean writes it (Windows line ends), approved."""
    guide = change.pop("guide", PACKAGE_BODY)
    sources = change.pop("sources", json.dumps({"schema_version": ri.PACKAGE_SCHEMA, "sources": [
        {"title": "涡轮增压器", "kind": "local_manual", "pdf_file": "x.pdf", "pdf_sha256": "a", "pages_cited": [3]}],
        "confirmed_facts": []}, ensure_ascii=False))
    files = {"guide.md": ri.file_hash(guide), "sources.json": ri.file_hash(sources)}
    manifest = {"schema_version": ri.PACKAGE_SCHEMA, "document_id": "demo-turbo", "version": "4",
                "title": "涡轮增压器指南", "always_include": ["## 1. 本区域检查什么"],
                "applicability": [{"brand": "大众", "model": "探岳", "year_from": 2019, "year_to": 2019,
                                   "engine_code": "dkvb"}],
                "open_gaps": [{"group": "数值", "gap": "间隙标准未给出"}],
                "review": {"status": "approved", "reviewer": "李", "reviewed_at": "2026-11-02T10:00:00+00:00",
                           "approved_hashes": dict(files)},
                "made_by": {"job": "turbo"}, "files": files}
    for key, value in change.items():
        manifest[key] = value
    return manifest, guide, sources


def test_approved_package_gives_title_vehicle_sections_and_provenance():
    checked = ri.check_package(*package())
    assert checked["document_id"] == "demo-turbo" and checked["title"] == "涡轮增压器指南"
    assert checked["vehicle"] == {"vehicle_brand": "大众", "vehicle_model": "探岳", "vehicle_year": 2019,
                                  "vehicle_engine_code": "DKVB"}
    assert checked["always_include"] == ["## 1. 本区域检查什么"]
    assert "\r" not in checked["body"]
    stored = checked["provenance"]["package"]
    assert stored["review"]["reviewer"] == "李" and stored["package_version"] == "4"
    assert stored["open_gaps"][0]["gap"] == "间隙标准未给出" and stored["sources"][0]["pages_cited"] == [3]


def pending(manifest):
    return {**manifest["review"], "status": "pending", "reviewer": None, "approved_hashes": None}


@pytest.mark.parametrize("make,code", [
    (lambda: package(schema_version="other"), "REFERENCE_PACKAGE_SCHEMA"),
    (lambda: (lambda m, g, s: (m, g + "改动", s))(*package()), "REFERENCE_PACKAGE_CHANGED"),
    (lambda: (lambda m, g, s: (m, g.replace("\r\n", "\n"), s))(*package()), "REFERENCE_PACKAGE_CHANGED"),
    (lambda: (lambda m, g, s: ({**m, "review": pending(m)}, g, s))(*package()), "REFERENCE_PACKAGE_NOT_APPROVED"),
    (lambda: (lambda m, g, s: ({**m, "review": {**m["review"], "approved_hashes": {"guide.md": "old", "sources.json": "old"}}}, g, s))(*package()),
     "REFERENCE_PACKAGE_CHANGED"),
    (lambda: (lambda m, g, s: ({**m, "review": {**m["review"], "reviewer": ""}}, g, s))(*package()), "REFERENCE_PACKAGE_NOT_APPROVED"),
    (lambda: package(document_id="Bad ID"), "REFERENCE_ID_INVALID"),
    (lambda: package(applicability=[{"brand": "大众"}]), "REFERENCE_VEHICLE_REQUIRED"),
    (lambda: package(always_include=["## 9. 不存在"]), "REFERENCE_SECTION_NOT_FOUND"),
    (lambda: package(title=" "), "REFERENCE_PACKAGE_SCHEMA"),
])
def test_package_that_is_not_intact_and_approved_is_refused(make, code):
    with pytest.raises(DomainError) as raised:
        ri.check_package(*make())
    assert raised.value.code == code
