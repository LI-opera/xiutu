"""Published v2 templates: reviewed roles, retrieved sections, and no hidden table dependency."""
import json
from copy import deepcopy

import pytest
from app.services.analysis_context import (
    READING_CONFIG,
    ROLES_CONFIG,
    TOP_K,
    _always_include,
    digest,
    enrich,
    model_payload,
)
from app.services.retrieval_reading import section_ranges

from scripts.build_analysis_context import MANIFEST, RELATIONS, ReviewRequired, build, derive_template
from scripts.seed_area_references import DEFAULT_PACKAGE, build_documents

ROLES_DATA = json.loads(ROLES_CONFIG.read_text(encoding="utf-8"))
READING_DATA = json.loads(READING_CONFIG.read_text(encoding="utf-8"))
RELATION_LIST = json.loads(RELATIONS.read_text(encoding="utf-8"))["relations"]
DOCUMENTS = list(build_documents(DEFAULT_PACKAGE, json.loads(MANIFEST.read_text(encoding="utf-8"))))


def topic_of(relation):
    return json.loads((RELATIONS.parent / relation["content_file"]).read_text(encoding="utf-8"))


def area_payload(relation, topic, area_id, answered=()):
    """Same keys build_input hands to enrich; answered = question IDs with their first option."""
    questions = [q for q in topic["questions"] if q["area_id"] == area_id]
    qmap = {q["id"]: q for q in questions}
    observations = [{"id": f"obs-{qid}", "question_id": qid,
                     "option_ids": [qmap[qid]["options"][0]["id"]],
                     "option_labels": [qmap[qid]["options"][0]["label"]]} for qid in answered]
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
def test_every_v2_area_gets_reviewed_roles_and_retrieved_sections(relation, area_id):
    topic = topic_of(relation)
    answered = [q["id"] for q in topic["questions"]
                if q["area_id"] == area_id and q["answer_kind"] != "automatic_derived"][:2]
    result = enrich(area_payload(relation, topic, area_id, answered), topic)
    guide = result["reference_reading_guide"]
    assert guide["roles"] == "reviewed" and guide["top_k"] == TOP_K
    assert all(q["record_role"] != "unclassified" for q in result["questions"])
    assert guide["documents"] and all(d["status"] == "selected" for d in guide["documents"])
    sent = model_payload(result)
    for doc, original in zip(sent["documents"], result["documents"]):
        assert doc["body_scope"] == "retrieved_sections_with_context"
        assert len(doc["body"]) <= len(original["body"])
        assert doc["full_content_hash"] == original["content_hash"]
        for heading in _always_include(original, READING_DATA):
            assert heading in doc["body"]


def test_new_template_without_any_reviewed_data_still_reads_sections():
    """A template nobody has configured: no roles, no table. It must not fall back to full bodies."""
    relation = RELATION_LIST[0]
    topic = deepcopy(topic_of(relation))
    topic["topic_id"] += "-brand-new"
    area_id = topic["areas"][0]["id"]
    answered = [q["id"] for q in topic["questions"] if q["area_id"] == area_id][:3]
    result = enrich(area_payload(relation, topic, area_id, answered), topic)
    guide = result["reference_reading_guide"]
    assert guide["roles"] == "unreviewed"
    assert all(o["record_role"] == "unclassified" for o in result["observations"])
    assert all(d["status"] == "selected" for d in guide["documents"])
    assert all(d["body_scope"] == "retrieved_sections_with_context" for d in model_payload(result)["documents"])


def test_decision_questions_stay_separate_from_unknown_facts():
    relation = RELATION_LIST[0]
    topic = topic_of(relation)
    roles = next(t for t in ROLES_DATA["templates"] if t["template_id"] == relation["template_id"]
                 and t["version"] == relation["version"])["questions"]
    decisions = {qid for qid, spec in roles.items() if spec["role"] in {"human_judgment", "disposition"}}
    area_id = next(q["area_id"] for q in topic["questions"] if q["id"] in decisions)
    result = enrich(area_payload(relation, topic, area_id), topic)
    assert result["unrecorded_decision_question_ids"]
    assert set(result["unrecorded_decision_question_ids"]) <= decisions
    assert not set(result["unknown_question_ids"]) & decisions


def test_runtime_files_hold_no_question_to_section_table():
    for template in ROLES_DATA["templates"]:
        for spec in template["questions"].values():
            assert set(spec) <= {"definition_hash", "role", "option_roles"}


def test_always_included_sections_exist_in_their_documents():
    bodies = {(doc["document_id"], doc["version"], doc["content_hash"]): doc["body"] for _, doc in DOCUMENTS}
    for entry in READING_DATA["documents"]:
        body = bodies[(entry["id"], entry["version"], entry["content_hash"])]
        assert set(entry["always_include"]) <= set(section_ranges(body))
    turbo = next(e for e in READING_DATA["documents"] if e["id"] == "tayron-dkvb-turbo")
    assert any("维修路径" in heading for heading in turbo["always_include"])


def test_record_roles_are_up_to_date_and_keep_reviewed_v1_entries():
    result, _ = build(ROLES_DATA)
    assert result == ROLES_DATA, "Run: python scripts/build_analysis_context.py --write"
    versions = {(t["template_id"], t["version"]) for t in ROLES_DATA["templates"]}
    assert {("tayron-dkvb-p0299", "1"), ("tayron-dkvb-p0236", "1")} <= versions


def test_changed_options_stop_for_manual_review():
    relation = RELATION_LIST[0]
    topic = deepcopy(topic_of(relation))
    topic["questions"][0]["options"].append({"id": "brand-new", "label": "新选项"})
    with pytest.raises(ReviewRequired, match="options changed"):
        derive_template(ROLES_DATA, relation, topic)

    topic = deepcopy(topic_of(relation))
    topic["questions"][0]["options"][0]["status_semantics"] = "not_executed_not_normal"
    with pytest.raises(ReviewRequired, match="not executed"):
        derive_template(ROLES_DATA, relation, topic)
