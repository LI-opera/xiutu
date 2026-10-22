"""Reference ingest without a database: chunking matches retrieval, validation, embedding batches."""
import json
import threading

import pytest
from app.domain.documents import IngestError
from app.domain.policies import DomainError
from app.retrieval.section_search import split
from app.services import reference_ingest as ri
from app.services.retrieval_reading import NAVIGATION

from scripts.build_analysis_context import MANIFEST
from scripts.seed_area_references import DEFAULT_PACKAGE, READING, always_include, build_documents

DOCUMENTS = [doc for _, doc in build_documents(DEFAULT_PACKAGE, json.loads(MANIFEST.read_text(encoding="utf-8")))]


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


def test_upload_body_rejects_unknown_fields():
    from app.api.area_references import ReferenceUpload
    base = {"document_id": "demo-doc", "title": "演示", "content": "x",
            "areas": [{"template_id": "t", "template_version": "1", "area_id": "a"}]}
    assert ReferenceUpload.model_validate(base).always_include == []
    with pytest.raises(Exception):
        ReferenceUpload.model_validate({**base, "status": "ready"})
    with pytest.raises(Exception):
        ReferenceUpload.model_validate({**base, "areas": []})


def test_reading_config_still_matches_seeded_bodies():
    """The seed script copies always-sent sections from this file; a body change must not drop them silently."""
    config = json.loads(READING.read_text(encoding="utf-8"))
    hashes = {(d["document_id"], d["version"]): d["content_hash"] for d in DOCUMENTS}
    for entry in config["documents"]:
        assert hashes.get((entry["id"], entry["version"])) == entry["content_hash"]
