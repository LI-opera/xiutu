"""Version-bound, data-driven reading guides; never infer or rewrite case facts."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "topics" / "analysis_context_v1.json"
ROLES = {"observation", "inspection_status", "human_judgment", "disposition",
         "completed_action", "retest", "unclassified"}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def enrich(payload, topic, config=None):
    """Add locators into complete source bodies, preserving every original value."""
    config = config if config is not None else json.loads(CONFIG.read_text(encoding="utf-8"))
    binding = payload["template_binding"]
    matches = [t for t in config["templates"] if all(
        t.get(k) == binding.get(k) for k in ("template_id", "version", "content_hash"))]
    template = matches[0] if len(matches) == 1 else None
    # Also verify actual question definitions, rather than trusting an ID alone.
    qmap = {q["id"]: q for q in topic["questions"]}
    definitions = template["questions"] if template else {}
    roles = {}
    for q in payload["questions"]:
        spec = definitions.get(q["id"], {})
        valid = (spec.get("definition_hash") == digest(qmap[q["id"]])
                 and spec.get("role") in ROLES
                 and all(role in ROLES for role in spec.get("option_roles", {}).values()))
        roles[q["id"]] = spec if valid else {}
        q["record_role"] = spec.get("role", "unclassified") if valid else "unclassified"
    for record in payload["observations"]:
        spec = roles[record["question_id"]]
        record["record_role"] = spec.get("role", "unclassified")
        record["selected_option_roles"] = [
            {"option_id": oid, "role": spec.get("option_roles", {}).get(oid, record["record_role"])}
            for oid in record.get("option_ids", [])]
        record["free_text_role"] = "unclassified"
    original_unknown = payload["unknown_question_ids"]
    payload["unrecorded_decision_question_ids"] = [qid for qid in original_unknown
        if roles[qid].get("role") in {"human_judgment", "disposition"}]
    payload["unknown_question_ids"] = [qid for qid in original_unknown
        if qid not in payload["unrecorded_decision_question_ids"]]
    guide = {"version": config["version"], "config_hash": digest(config),
             "template_status": "matched" if template else "unconfigured_or_changed",
             "mode": "selected_sections_with_full_snapshot", "documents": []}
    recorded = {o["question_id"] for o in payload["observations"]}
    for document in payload["documents"]:
        specs = [d for d in config["documents"] if d["id"] == document["id"]
                 and d["version"] == document.get("version")
                 and d["content_hash"] == document.get("content_hash")
                 and d["content_hash"] == hashlib.sha256(document.get("body", "").encode()).hexdigest()]
        entry = {"document_id": document["id"], "status": "unconfigured_or_changed", "sections": []}
        if len(specs) == 1 and template:
            spec = specs[0]
            selected = {}
            for sid in spec["always_include"]:
                selected[sid] = {"reason": "context_conditions_and_verification", "question_ids": []}
            for qid in sorted(recorded):
                for sid in roles[qid].get("references", {}).get(document["id"], []):
                    selected.setdefault(sid, {"reason": "recorded_question", "question_ids": []})["question_ids"].append(qid)
            for qid in payload["unknown_question_ids"]:
                for sid in roles[qid].get("references", {}).get(document["id"], []):
                    selected.setdefault(sid, {"reason": "unknown_fact_method", "question_ids": []})["question_ids"].append(qid)
            focus = {}
            for record in payload["observations"]:
                qid = record["question_id"]
                for oid in record.get("option_ids", []):
                    for sid in roles[qid].get("option_references", {}).get(oid, {}).get(document["id"], []):
                        focus.setdefault(sid, []).append({"observation_id": record["id"], "option_id": oid})
            for sid in focus:
                selected.setdefault(sid, {"reason": "selected_result", "question_ids": []})
            valid = all(sid in spec["sections"] for sid in selected)
            for sid, why in selected.items():
                if not valid:
                    break
                section = spec["sections"][sid]
                start, end = section["start"], section["end"]
                if not (0 <= start < end <= len(document["body"])) or not document["body"][start:end].startswith(section["heading"]):
                    valid = False
                    break
                # The gateway may redact text; character offsets are only local validation.
                # Stable headings remain readable locators in the outbound document.
                entry["sections"].append({"section_id": sid, "heading": section["heading"], **why})
            # Any unconfigured question in this area means selection may miss relevant context.
            if any(not roles[q["id"]] for q in payload["questions"]):
                valid = False
            entry["status"] = "matched" if valid else "invalid_locators_full_body_retained"
            if not valid:
                entry["sections"] = []
            else:
                # Exact extracts, not generated summaries; union overlapping ranges once.
                ranges = sorted((spec["sections"][sid]["start"], spec["sections"][sid]["end"]) for sid in selected)
                merged = []
                for start, end in ranges:
                    if merged and start <= merged[-1][1]:
                        merged[-1][1] = max(merged[-1][1], end)
                    else:
                        merged.append([start, end])
                document["analysis_extracts"] = [document["body"][a:b] for a,b in merged]
                entry["result_methods"] = [{"section_id":sid, "heading":spec["sections"][sid]["heading"],
                    "selected_by":links, "text":document["body"][spec["sections"][sid]["start"]:spec["sections"][sid]["end"]]}
                    for sid,links in focus.items()]
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
            doc["body_scope"] = "configured_sections_with_context"
            doc["full_content_hash"] = doc.pop("content_hash")
            doc["content_hash"] = hashlib.sha256(doc["body"].encode()).hexdigest()
        else:
            doc["body_scope"] = "full_document_fallback"
    return result
