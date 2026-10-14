"""Small, frozen source-to-operation allowlist for the B02 synthetic topic."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from app.topics import dkvb_b02

ACTION_PATH = Path(__file__).resolve().parents[1] / "topics" / "tanyue_dkvb_p0299_c15_actions.json"


@lru_cache(maxsize=1)
def action_catalog():
    raw = ACTION_PATH.read_bytes()
    pack = json.loads(raw)
    if pack["topic_version"] != dkvb_b02.TOPIC_VERSION:
        raise RuntimeError("C02 action catalog is not bound to B02")
    ids = [item["id"] for item in pack["actions"]]
    if len(ids) != len(set(ids)):
        raise RuntimeError("C02 action IDs are not unique")
    return {item["id"]: item for item in pack["actions"]}, pack["version"], hashlib.sha256(raw).hexdigest()


def supported_actions(source_context, vehicle=None):
    actions, version, digest = action_catalog()
    excerpts = {item["id"]: item for item in source_context["excerpts"]}
    supported = {}
    for action_id, rule in actions.items():
        if vehicle is not None and not action_case_applicable(rule, vehicle):
            continue
        required = rule["required_excerpt_ids"]
        if all(excerpt_id in excerpts and excerpts[excerpt_id]["kind"] == "local_manual"
               for excerpt_id in required) and excerpts[required[0]]["text"] == rule["required_excerpt_text"]:
            supported[action_id] = rule
    return {"version": version, "hash": digest, "actions": supported}


def action_facts_satisfied(rule, observations):
    """Evaluate the frozen option predicates, including every mandatory fact."""
    any_of = rule.get("required_question_options", {})
    all_of = rule.get("required_all_question_options", {})
    if not any_of or not any(
        fact["question_id"] in any_of and
        bool(set(fact["option_ids"]) & set(any_of[fact["question_id"]]))
        for fact in observations
    ):
        return False
    return all(any(
        fact["question_id"] == question_id and
        bool(set(fact["option_ids"]) & set(options))
        for fact in observations
    ) for question_id, options in all_of.items())


def action_case_applicable(rule, vehicle):
    years = rule.get("allowed_vehicle_years")
    return years is None or vehicle.get("year") in years
