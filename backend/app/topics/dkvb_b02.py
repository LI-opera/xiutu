"""Immutable B02 execution overlay over the frozen B01 content library."""
import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from app.domain.policies import DomainError
from app.topics import dkvb_b01

TOPIC_VERSION = "2.2.1-b02"
RULES = Path(__file__).with_name("tanyue_dkvb_p0299_b02_rules.json")


@lru_cache(maxsize=1)
def catalog():
    base, base_digest = dkvb_b01.catalog()
    raw = RULES.read_bytes()
    rules = json.loads(raw)
    if (rules["version"] != TOPIC_VERSION or rules["base_sha256"] != base_digest
            or not rules["synthetic"] or not rules["demo"] or rules["formal_usable"]):
        raise RuntimeError("B02 execution overlay does not match frozen B01 content")
    topic = deepcopy(base)
    topic["version"] = TOPIC_VERSION
    topic["authority"] = "B01 frozen content plus B02 immutable execution overlay; synthetic DEMO only"
    topic["execution_rules"] = rules
    for question in topic["questions"]:
        if question["answer_kind"] == "conditional_operation":
            question["execution_conditions"] = rules["conditional_operations"][question["id"]]
    return topic, hashlib.sha256(base_digest.encode("ascii") + raw).hexdigest()


def binding():
    topic, digest = catalog()
    return {"topic_id": topic["topic_id"], "version": TOPIC_VERSION,
            "content_hash": digest, "synthetic": True, "demo": True,
            "formal_usable": False}


def bound(case):
    return (case.get("intake_snapshot") or {}).get("topic_binding") == binding()


def require_bound(case):
    if not bound(case):
        raise DomainError("TOPIC_NOT_BOUND", "This case is not bound to DKVB B02", 404)


def plan(intake):
    return dkvb_b01.plan(intake)
