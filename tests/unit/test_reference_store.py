"""Searching stored chunks goes through the same ranking as computing them now."""
import json

import pytest
from app.retrieval.section_search import dense_rank, exact_rank
from app.services import analysis_context
from app.services.retrieval_reading import ComputedSections, Embeddings, select_sections

from scripts.build_analysis_context import MANIFEST
from scripts.seed_area_references import DEFAULT_PACKAGE, always_include, build_documents

DOCUMENTS = [doc for _, doc in build_documents(DEFAULT_PACKAGE, json.loads(MANIFEST.read_text(encoding="utf-8")))]


class Model:
    """Deterministic stand-in for the embedding model: character-class histogram."""
    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text):
        return [1.0 + sum(1 for ch in text if ord(ch) % 7 == k) for k in range(7)]


class FakeStored:
    """What StoredSections returns, emulated in Python: SQL overlap count and cosine order."""
    source = "stored"

    def __init__(self, document, embeddings):
        computed = ComputedSections(document, embeddings)
        self.chunks, self.index, self.embeddings = computed.chunks, computed.index, embeddings
        self.vectors = embeddings.documents([c.search_text for c in self.chunks])

    def exact(self, query):
        return exact_rank(query, self.chunks)

    def keywords(self, query):
        return self.index.rank(query)

    def dense(self, query):
        return dense_rank(self.embeddings.query(query), self.vectors)


def queries(document, n=12):
    titles = [c.subsection or c.section for c in ComputedSections(document).chunks][:n]
    return [{"text": t.lstrip("# "), "reason": "recorded_question", "question_id": f"Q{i}",
             "observation_id": f"o{i}", "option_ids": ["a"]} for i, t in enumerate(titles)]


@pytest.mark.parametrize("doc", DOCUMENTS, ids=[d["document_id"] for d in DOCUMENTS])
def test_a_stored_source_with_the_same_data_selects_the_same_sections(doc):
    embeddings = Embeddings(Model())
    document = {"id": doc["document_id"], "version": doc["version"], "body": doc["body"],
                "content_hash": doc["content_hash"]}
    kwargs = dict(top_k=3, always_include=always_include(doc), embeddings=embeddings)
    computed = select_sections(document, queries(document), **kwargs)
    stored = select_sections(document, queries(document), source=FakeStored(document, embeddings), **kwargs)
    assert stored == computed and computed


def test_enrich_uses_the_stored_rows_always_included_sections():
    doc = DOCUMENTS[0]
    document = {"id": doc["document_id"], "version": doc["version"], "body": doc["body"],
                "content_hash": doc["content_hash"]}
    from app.services.retrieval_reading import section_ranges
    heading = next(h for h in section_ranges(doc["body"]) if h not in always_include(doc))
    payload = {"template_binding": {}, "questions": [], "observations": [], "unknown_question_ids": [],
               "documents": [dict(document)]}
    result = analysis_context.enrich(payload, {"questions": []}, sections=lambda d: (None, [heading]))
    (guide,) = result["reference_reading_guide"]["documents"]
    assert [s["heading"] for s in guide["sections"]] == [heading]
    # No stored row: the reviewed config decides, as before.
    payload["documents"] = [dict(document)]
    result = analysis_context.enrich(payload, {"questions": []}, sections=lambda d: (None, None))
    (guide,) = result["reference_reading_guide"]["documents"]
    assert [s["heading"] for s in guide["sections"]] == always_include(doc)


def test_warm_loads_the_model_once_and_never_raises():
    calls = []

    def loader():
        calls.append(1)
        return Model()
    embeddings = Embeddings(loader)
    embeddings.warm()
    embeddings.warm()
    assert len(calls) == 1

    def broken():
        raise RuntimeError("MODEL_PATH_UNAVAILABLE")
    Embeddings(broken).warm()  # left for the search to report


def test_each_area_chooses_its_own_manual_among_all_of_the_vehicle():
    """Two-step retrieval, step one, offline: no table says which manual belongs to which area."""
    from app.services.retrieval_reading import area_texts, choose_documents
    from scripts.build_analysis_context import RELATIONS
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assigned = {entry["area_id"]: entry["document_id"] for entry in manifest["documents"]}
    manuals = [{"id": d["document_id"], "version": d["version"], "body": d["body"]} for d in DOCUMENTS]
    relation = json.loads(RELATIONS.read_text(encoding="utf-8"))["relations"][0]
    topic = json.loads((RELATIONS.parent / relation["content_file"]).read_text(encoding="utf-8"))
    for area in topic["areas"]:
        chosen = choose_documents(manuals, area_texts(area, topic["questions"]))
        assert chosen[0][0] == assigned[area["id"]], area["id"]


def test_choosing_uses_stored_pools_when_given():
    from app.services.retrieval_reading import choose_documents, computed_pool
    manuals = [{"id": d["document_id"], "version": d["version"], "body": d["body"]} for d in DOCUMENTS[:2]]
    seen = []

    def pool(document):
        seen.append(document["id"])
        return computed_pool(document)
    assert choose_documents(manuals, ["检查"], pool=pool) and seen == [m["id"] for m in manuals]
    assert choose_documents([], ["检查"]) == []


def test_vehicle_filter_ignores_what_the_case_does_not_know():
    from app.services.reference_store import vehicle_conditions
    full = vehicle_conditions({"brand": "大众", "model": "探岳", "year": 2019, "engine_code": "DKVB"})
    no_engine = vehicle_conditions({"brand": "大众", "model": "探岳", "year": 2019, "engine_code": None})
    assert len(full) == 4 and len(no_engine) == 3
    assert len(vehicle_conditions({"brand": "大众", "model": "探岳", "year": "", "engine_code": ""})) == 2
    assert vehicle_conditions({"brand": None, "model": "虚拟探岳", "year": 2019}) is None
