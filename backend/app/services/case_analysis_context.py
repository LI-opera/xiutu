"""Versioned, bounded source excerpts for the synthetic DKVB B02 topic."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from app.topics import dkvb_b02

CONTEXT_PATH = Path(__file__).resolve().parents[1] / "topics" / "tanyue_dkvb_p0299_c15_context.json"
MAX_INPUT_CHARS = 48000
PROMPT_VERSION = "dkvb-c19-v5"
PREVIOUS_OUTPUT_CONTRACT_VERSION = "case-advice-open-c19-v1"
OUTPUT_CONTRACT_VERSION = "case-advice-open-c19-v2"


@lru_cache(maxsize=1)
def context_pack():
    raw = CONTEXT_PATH.read_bytes()
    pack = json.loads(raw)
    topic, _ = dkvb_b02.catalog()
    if (pack["topic_version"] != dkvb_b02.TOPIC_VERSION or not pack["synthetic"]
            or pack["formal_usable"]):
        raise RuntimeError("C01 source context is not bound to B02")
    sources = {item["id"] for item in topic["sources"]}
    assets = {item["id"] for item in topic["assets"]}
    if len({item["id"] for item in pack["excerpts"]}) != len(pack["excerpts"]):
        raise RuntimeError("C01 source excerpt IDs are not unique")
    for item in pack["excerpts"]:
        if item["source_ref"] not in sources or not set(item["asset_ids"]) <= assets:
            raise RuntimeError("C01 source context has an unknown reference")
        if not item["text"].strip() or not item["file_sha256"] or item["page"] < 1:
            raise RuntimeError("C01 source context lacks a readable excerpt locator")
    return pack, hashlib.sha256(raw).hexdigest()


def selected_context(topic, question_ids):
    pack, digest = context_pack()
    questions = {item["id"]: item for item in topic["questions"]}
    sources = {item["id"]: item for item in topic["sources"]}
    cards = {item["id"]: item for item in topic["long_cards"]}
    assets = {item["id"]: item for item in topic["assets"]}
    relevant = [questions[qid] for qid in question_ids if qid in questions]
    source_refs = set().union(*(set(q["source_refs"]) for q in relevant)) if relevant else set()
    area_ids = {q["area_id"] for q in relevant}
    excerpts = [item for item in pack["excerpts"] if item["source_ref"] in source_refs or
                set(item["related_areas"]) & area_ids]
    long_ids = {long_id for q in relevant for long_id in q["long_card_ids"]}
    editorial = [{"id": item["id"], "title": item["title"], "text": item["markdown"],
                  "kind": "editorial_demo", "source_document": item["source_document"]}
                 for item in topic["long_cards"] if item["id"] in long_ids]
    provided_refs = {item["source_ref"] for item in excerpts}
    source_metadata = [{"id": ref, "kind": sources[ref]["kind"], "citation": sources[ref]["citation"],
                        "pages_or_use": sources[ref]["pages_or_use"],
                        "scope_or_limit": sources[ref]["scope_or_limit"]}
                       for ref in sorted(source_refs) if ref in sources]
    asset_ids = {asset_id for item in excerpts for asset_id in item["asset_ids"]}
    asset_ids.update(asset_id for q in relevant for asset_id in q["assetIds"])
    images = [{"id": asset_id, "title": assets[asset_id]["title"], "file": assets[asset_id]["file"],
               "description": assets[asset_id]["description"], "source_ref": assets[asset_id].get("source_ref"),
               "model_read_image": False} for asset_id in sorted(asset_ids) if asset_id in assets]
    missing_body = {ref for ref in source_refs - provided_refs if ref in sources and
                    sources[ref]["kind"] in {"local_manual", "generic_web_register_only"}}
    return {"version": pack["version"], "hash": digest, "boundary": pack["boundary"],
            "excerpts": excerpts, "editorial_cards": editorial, "source_metadata": source_metadata,
            "image_references": images, "missing_body_source_refs": sorted(missing_body)}
