"""Immutable Stage B DKVB/P0299 topic identity and case-plan factory."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from app.domain.policies import DomainError

TOPIC_VERSION = "2.2.0-b01"
CATALOG = Path(__file__).with_name("tanyue_dkvb_p0299_b01.json")


@lru_cache(maxsize=1)
def catalog():
    raw = CATALOG.read_bytes()
    topic = json.loads(raw)
    questions = topic["questions"]
    if topic["version"] != TOPIC_VERSION or len(questions) != 78 or len({q["id"] for q in questions}) != 78:
        raise RuntimeError("B01 topic identity/cardinality invalid")
    if not topic["synthetic"] or topic["formal_usable"] or not topic["runtime_enabled"]:
        raise RuntimeError("B01 demo boundary invalid")
    return topic, hashlib.sha256(raw).hexdigest()


def binding():
    topic, digest = catalog()
    return {"topic_id": topic["topic_id"], "version": TOPIC_VERSION,
            "content_hash": digest, "synthetic": True, "demo": True,
            "formal_usable": False}


def bound(case):
    claim = (case.get("intake_snapshot") or {}).get("topic_binding")
    return claim == binding()


def require_bound(case):
    if not bound(case):
        raise DomainError("TOPIC_NOT_BOUND", "This case is not bound to DKVB B01", 404)


def plan(intake):
    topic, _ = catalog()
    initial = list(topic["plan_policy"]["initial_intake_required"])
    for ids in topic["plan_policy"]["first_round_scope"].values():
        initial.extend(ids)
    return {"version": 1, "required_question_ids": list(dict.fromkeys(initial)),
            "expanded_area_ids": [], "capture_batches": {
                "engine_off_static": str(uuid4()),
                "comparable_load_frames": str(uuid4()),
            }, "rounds": [], "intake": intake}
