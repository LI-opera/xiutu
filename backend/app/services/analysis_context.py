"""Reading guide for an analysis: record roles, and which manual sections to send.

Sections are chosen by searching each document's own text (retrieval_reading), never by a
hand-written question-to-section table. Record roles come from record_roles_v1.json when a
template has reviewed entries; without them records are "unclassified" and the analysis
still runs with retrieved sections. Never infers or rewrites case facts.
"""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from app.services.retrieval_reading import METHOD_VERSION, queries_for, select_sections

CONFIG_DIR = Path(__file__).resolve().parents[1] / "reading_config"
ROLES_CONFIG = CONFIG_DIR / "record_roles_v1.json"
READING_CONFIG = CONFIG_DIR / "reading_documents_v1.json"
ROLES = {"observation", "inspection_status", "human_judgment", "disposition",
         "completed_action", "retest", "unclassified"}
TOP_K = 3


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _apply_roles(payload, topic, roles_config):
    """Tag records with reviewed roles; anything unreviewed or changed stays unclassified."""
    binding = payload["template_binding"]
    matches = [t for t in roles_config["templates"] if all(
        t.get(k) == binding.get(k) for k in ("template_id", "version", "content_hash"))]
    definitions = matches[0]["questions"] if len(matches) == 1 else {}
    qmap = {q["id"]: q for q in topic["questions"]}
    roles = {}
    for q in payload["questions"]:
        spec = definitions.get(q["id"], {})
        # Verify the actual question definition, rather than trusting an ID alone.
        valid = (q["id"] in qmap and spec.get("definition_hash") == digest(qmap[q["id"]])
                 and spec.get("role") in ROLES
                 and all(role in ROLES for role in spec.get("option_roles", {}).values()))
        roles[q["id"]] = spec if valid else {}
        q["record_role"] = spec.get("role", "unclassified") if valid else "unclassified"
    for record in payload["observations"]:
        spec = roles.get(record["question_id"], {})
        record["record_role"] = spec.get("role", "unclassified")
        record["selected_option_roles"] = [
            {"option_id": oid, "role": spec.get("option_roles", {}).get(oid, record["record_role"])}
            for oid in record.get("option_ids", [])]
        record["free_text_role"] = "unclassified"
    original_unknown = payload["unknown_question_ids"]
    payload["unrecorded_decision_question_ids"] = [qid for qid in original_unknown
        if roles.get(qid, {}).get("role") in {"human_judgment", "disposition"}]
    payload["unknown_question_ids"] = [qid for qid in original_unknown
        if qid not in payload["unrecorded_decision_question_ids"]]
    return "reviewed" if definitions else "unreviewed"


def _always_include(document, reading_config):
    """A document's always-sent sections apply only to the exact body they were written for."""
    body_hash = hashlib.sha256(document.get("body", "").encode()).hexdigest()
    for entry in reading_config["documents"]:
        if (entry["id"] == document["id"] and entry["version"] == document.get("version")
                and entry["content_hash"] == document.get("content_hash") == body_hash):
            return entry["always_include"]
    return []


def enrich(payload, topic, embeddings=None, *, roles_config=None, reading_config=None, top_k=TOP_K,
           sections=None):
    """Add record roles and a retrieved-section reading guide, preserving every original value.

    embeddings=None searches with exact codes and keywords only (offline tests); the service
    passes local vectors. sections(document) -> (stored source or None, always-included
    sections or None) lets the service search chunks and vectors stored at ingest; without
    it (or when nothing is stored) the body is split and embedded now, with the same result.
    If search cannot run for a document, its full body is sent.
    """
    roles_config = roles_config if roles_config is not None else _load(ROLES_CONFIG)
    reading_config = reading_config if reading_config is not None else _load(READING_CONFIG)
    roles_status = _apply_roles(payload, topic, roles_config)
    queries = queries_for(payload)
    guide = {"version": METHOD_VERSION, "mode": "retrieved_sections_with_full_snapshot",
             "top_k": top_k, "channels": ["exact", "bm25"] + (["dense"] if embeddings is not None else []),
             "embedding": getattr(embeddings, "fingerprint", None),
             "roles": roles_status, "roles_config_hash": digest(roles_config),
             "reading_config_hash": digest(reading_config), "documents": []}
    for document in payload["documents"]:
        document.pop("analysis_extracts", None)  # never reuse extracts from an earlier call
        entry = {"document_id": document["id"], "status": "full_body_retained", "sections": []}
        try:
            source, always = sections(document) if sections is not None else (None, None)
            if always is None:
                always = _always_include(document, reading_config)
            chosen = select_sections(document, queries, top_k=top_k, embeddings=embeddings,
                                     always_include=always, source=source)
        except Exception as error:  # search unavailable (e.g. local model): send everything
            entry["status"] = "retrieval_unavailable_full_body_retained"
            entry["error"] = getattr(error, "code", type(error).__name__)
            chosen = None
        if chosen:
            entry["status"] = "selected"
            entry["sections"] = [{"heading": s["heading"], "reason": s["reason"],
                                  "question_ids": s["question_ids"]} for s in chosen]
            # Point to the section by heading only: its text is already in the sent body.
            entry["result_methods"] = [{"heading": s["heading"], "selected_by": s["selected_by"]}
                                       for s in chosen if s["selected_by"]]
            spans = sorted((s["start"], s["end"]) for s in chosen)
            merged = []
            for start, end in spans:
                if merged and start <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], end)
                else:
                    merged.append([start, end])
            # Exact extracts, not generated summaries.
            document["analysis_extracts"] = [document["body"][a:b] for a, b in merged]
        guide["documents"].append(entry)
    payload["reference_reading_guide"] = guide
    return payload


def model_payload(payload):
    """Transport projection only; stored full source and old analyses remain untouched."""
    result = deepcopy(payload)
    for doc in result["documents"]:
        extracts = doc.pop("analysis_extracts", None)
        if extracts:
            doc["body"] = "\n\n".join(extracts)
            doc["body_scope"] = "retrieved_sections_with_context"
            doc["full_content_hash"] = doc.pop("content_hash")
            doc["content_hash"] = hashlib.sha256(doc["body"].encode()).hexdigest()
        else:
            doc["body_scope"] = "full_document_fallback"
    return result
