"""Explicit adapter between the DKVB content catalog and frozen CHK-3.1.0.

The catalog describes 78 visible questions. Only entries in WIRED may create
formal observations; the remaining questions are read-only content.
"""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from app.agents.trusted_protocol import PROFILE
from app.domain.policies import DomainError

TOPIC_ID = "tanyue-dkvb-p0299-demo-v2"
TOPIC_VERSION = "2.0.0"
CATALOG = Path(__file__).with_name("dkvb_p0299_v2.json")

# (formal check, formal option) -> (topic question, topic option). The mapping
# is deliberately narrow and never inferred by manipulating AIR/RET IDs.
WIRED = {
    ("CHK-04", "air.seating_suspect"): ("AIR-07", "partially_seated"),
    ("CHK-05", "leak.localized"): ("AIR-15", "connector"),
    ("CHK-05", "leak.not_found"): ("AIR-15", "none"),
    ("CHK-06", "repair.completed"): ("RET-01", "reseat"),
    ("CHK-07", "retest.record"): ("RET-04", "recovered"),
}


@lru_cache(maxsize=1)
def catalog():
    raw = CATALOG.read_bytes()
    data = json.loads(raw)
    if (data.get("topic_id"), data.get("version"), len(data.get("questions", []))) != (TOPIC_ID, TOPIC_VERSION, 78):
        raise RuntimeError("DKVB V2 catalog identity or cardinality changed")
    questions = {q["id"]: q for q in data["questions"]}
    for question_id, option_id in WIRED.values():
        if question_id not in questions or option_id not in {x["id"] for x in questions[question_id]["options"]}:
            raise RuntimeError(f"Invalid formal topic mapping: {question_id}/{option_id}")
    return data, hashlib.sha256(raw).hexdigest()


def binding():
    _, digest = catalog()
    return {"topic_id": TOPIC_ID, "version": TOPIC_VERSION,
            "content_hash": digest, "synthetic": True, "formal_usable": False}


def applicable(vehicle, fault_codes, diagnosis_mode):
    return (diagnosis_mode == "conservative" and
            all(vehicle.get(key) == value for key, value in PROFILE.items()) and
            "P0299" in fault_codes)


def bound(case):
    claim = (case.get("intake_snapshot") or {}).get("topic_binding")
    return claim == binding() and applicable(
        case.get("vehicle_json") or case.get("vehicle") or {},
        case.get("fault_codes", []), case.get("diagnosis_mode"))


def validate_annotation(case, protocol_payload, question_id, option_id, version):
    if not bound(case):
        raise DomainError("TOPIC_BINDING_MISSING", "Case is not bound to this topic", 422)
    if version != TOPIC_VERSION:
        raise DomainError("TOPIC_VERSION_MISMATCH", "Topic version differs from the case", 409)
    check_id, formal_option = protocol_payload.get("check_id"), protocol_payload.get("option_id")
    expected = WIRED.get((check_id, formal_option))
    if expected != (question_id, option_id):
        raise DomainError("TOPIC_OPTION_NOT_WIRED", "This topic answer is not wired to the current formal check", 422)
    fields = protocol_payload.get("protocol_fields", {})
    if check_id == "CHK-04" and formal_option == "air.seating_suspect" and not fields.get("note"):
        raise DomainError("TOPIC_EVIDENCE_MISSING", "Record the observation basis before saving the connector finding", 422)
    if check_id == "CHK-05":
        if formal_option == "leak.localized" and (fields.get("leak_object_id") != "connector" or not fields.get("evidence_kind")):
            raise DomainError("TOPIC_EVIDENCE_MISMATCH", "Connector location and evidence are required", 422)
    if check_id == "CHK-07":
        from app.services.protocol_service import ProtocolService
        if ProtocolService._result_value(check_id, protocol_payload) != "retest.recovered":
            raise DomainError("TOPIC_RETEST_MISMATCH", "Recovered option requires a new recovered retest", 422)
    return {"topic_id": TOPIC_ID, "topic_version": TOPIC_VERSION,
            "topic_content_hash": binding()["content_hash"],
            "topic_question_id": question_id, "topic_option_id": option_id,
            "topic_source": "SYNTHETIC_DEMO_TOPIC"}
