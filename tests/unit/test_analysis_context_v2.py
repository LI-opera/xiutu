"""The published v2 templates must get section-scoped reading, not the full-document fallback."""
import hashlib
import json
from copy import deepcopy

import pytest
from app.services.analysis_context import CONFIG, digest, enrich, model_payload

from scripts.build_analysis_context import (
    MANIFEST,
    RELATIONS,
    ReviewRequired,
    build,
    derive_documents,
    derive_template,
)
from scripts.seed_area_references import DEFAULT_PACKAGE, build_documents

CONFIG_DATA = json.loads(CONFIG.read_text(encoding="utf-8"))
RELATION_LIST = json.loads(RELATIONS.read_text(encoding="utf-8"))["relations"]
DOCUMENTS = list(build_documents(DEFAULT_PACKAGE, json.loads(MANIFEST.read_text(encoding="utf-8"))))


def topic_of(relation):
    return json.loads((RELATIONS.parent / relation["content_file"]).read_text(encoding="utf-8"))


def area_payload(relation, topic, area_id, answered=()):
    """Same keys build_input hands to enrich; answered = question IDs with their first option."""
    questions = [q for q in topic["questions"] if q["area_id"] == area_id]
    qmap = {q["id"]: q for q in questions}
    observations = [{"id": f"obs-{qid}", "question_id": qid,
                     "option_ids": [qmap[qid]["options"][0]["id"]]} for qid in answered]
    documents = [{"id": doc["document_id"], "version": doc["version"], "title": doc["title"],
                  "body": doc["body"], "content_hash": doc["content_hash"]}
                 for entry, doc in DOCUMENTS if entry["area_id"] == area_id]
    return {"template_binding": {"template_id": relation["template_id"],
                                 "version": relation["version"], "content_hash": digest(topic)},
            "questions": [{"id": q["id"], "title": q["title"]} for q in questions],
            "observations": observations,
            "unknown_question_ids": [q["id"] for q in questions if q["id"] not in answered
                                     and q["answer_kind"] != "automatic_derived"],
            "documents": documents}


CASES = [(relation, area["id"]) for relation in RELATION_LIST for area in topic_of(relation)["areas"]]


@pytest.mark.parametrize("relation,area_id", CASES, ids=[f"{r['template_id']}-{a}" for r, a in CASES])
def test_every_v2_area_reads_configured_sections(relation, area_id):
    topic = topic_of(relation)
    answered = [q["id"] for q in topic["questions"]
                if q["area_id"] == area_id and q["answer_kind"] != "automatic_derived"][:2]
    result = enrich(area_payload(relation, topic, area_id, answered), topic)
    guide = result["reference_reading_guide"]
    assert guide["template_status"] == "matched"
    assert guide["documents"] and all(d["status"] == "matched" for d in guide["documents"])
    assert all(q["record_role"] != "unclassified" for q in result["questions"])
    sent = model_payload(result)
    for doc, original in zip(sent["documents"], result["documents"]):
        assert doc["body_scope"] == "configured_sections_with_context"
        assert len(doc["body"]) < len(original["body"])
        assert doc["full_content_hash"] == original["content_hash"]


def test_decision_questions_stay_separate_from_unknown_facts():
    relation = RELATION_LIST[0]
    topic = topic_of(relation)
    roles = next(t for t in CONFIG_DATA["templates"] if t["template_id"] == relation["template_id"]
                 and t["version"] == relation["version"])["questions"]
    decisions = {qid for qid, spec in roles.items() if spec["role"] in {"human_judgment", "disposition"}}
    area_id = next(q["area_id"] for q in topic["questions"] if q["id"] in decisions)
    result = enrich(area_payload(relation, topic, area_id), topic)
    assert result["unrecorded_decision_question_ids"]
    assert set(result["unrecorded_decision_question_ids"]) <= decisions
    assert not set(result["unknown_question_ids"]) & decisions


def test_changed_question_definition_falls_back_to_full_body():
    relation = RELATION_LIST[0]
    topic = deepcopy(topic_of(relation))
    area_id = topic["areas"][0]["id"]
    payload = area_payload(relation, topic, area_id)
    next(q for q in topic["questions"] if q["area_id"] == area_id)["title"] += "（改动）"
    result = enrich(payload, topic)
    assert all(d["status"] == "invalid_locators_full_body_retained"
               for d in result["reference_reading_guide"]["documents"])
    assert all(d["body_scope"] == "full_document_fallback" for d in model_payload(result)["documents"])


def test_reading_guide_is_up_to_date_and_keeps_reviewed_v1_entries():
    result, _, _ = build(CONFIG_DATA)
    assert result == CONFIG_DATA, "Run: python scripts/build_analysis_context.py --write"
    versions = {(t["template_id"], t["version"]) for t in CONFIG_DATA["templates"]}
    assert {("tayron-dkvb-p0299", "1"), ("tayron-dkvb-p0236", "1")} <= versions


def test_changed_options_or_bodies_stop_for_manual_review():
    relation = RELATION_LIST[0]
    topic = deepcopy(topic_of(relation))
    documents = derive_documents(CONFIG_DATA, json.loads(MANIFEST.read_text(encoding="utf-8")))
    topic["questions"][0]["options"].append({"id": "brand-new", "label": "新选项"})
    with pytest.raises(ReviewRequired, match="options changed"):
        derive_template(CONFIG_DATA, relation, topic, documents)

    topic = deepcopy(topic_of(relation))
    option = topic["questions"][0]["options"][0]
    option["status_semantics"] = "not_executed_not_normal"
    with pytest.raises(ReviewRequired, match="not executed"):
        derive_template(CONFIG_DATA, relation, topic, documents)

    config = deepcopy(CONFIG_DATA)
    for doc in config["documents"]:
        doc["content_hash"] = hashlib.sha256(b"other body").hexdigest()
    with pytest.raises(ReviewRequired, match="body changed"):
        derive_documents(config, json.loads(MANIFEST.read_text(encoding="utf-8")))
