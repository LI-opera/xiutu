"""Compatibility boundary for already published B01/B02 calculation catalogs.

Frozen catalogs and legacy case services are not migrated or rewritten here.
New data-only templates do not enter this adapter.
"""
from copy import deepcopy
from uuid import uuid4

from app.domain.policies import DomainError

LEGACY_TEMPLATE_IDENTITIES = frozenset({
    ("tayron-dkvb-p0299", "tayron-dkvb-p0299-v1"),
    ("tayron-dkvb-p0236", "tayron-dkvb-p0236-v1"),
})


def supports(topic):
    catalog = topic.get("calculation_catalog")
    if catalog is None:
        return False
    # Historical frozen v1 identities only; an independent template cannot
    # enter B01/B02 calculations by reusing a catalog version string.
    if (catalog.get("version") not in {"2.2.0-b01", "2.2.1-b02"}
            or (topic.get("topic_id"), topic.get("version")) not in LEGACY_TEMPLATE_IDENTITIES):
        raise DomainError("TEMPLATE_CALCULATOR_UNSUPPORTED", "模板计算规则版本尚不支持", 409)
    return True


def build_plan(topic, intake):
    if not supports(topic):
        raise DomainError("TEMPLATE_CALCULATOR_UNSUPPORTED", "模板计算规则版本尚不支持", 409)
    # The after-setting batch is created by the existing setting action, not intake.
    return {"version": 1,
            "required_question_ids": [q["id"] for q in topic["questions"]
                                      if q["answer_kind"] != "automatic_derived"],
            "expanded_area_ids": [],
            "capture_batches": {kind: str(uuid4()) for kind in
                                ("engine_off_static", "comparable_load_frames")},
            "rounds": [], "intake": dict(intake)}


def project_template(case, records, report_gate, topic):
    from app.services.template_projection import _project_template

    return _project_template(case, records, report_gate, topic,
                             compatibility=evaluate(case, records, report_gate, topic))


def evaluate(case, records, report_gate, topic):
    from app.services.legacy_topic_projection import project
    result = project(case, records, report_gate, deepcopy(topic["calculation_catalog"]))
    qids = {q["id"] for q in topic["questions"]}
    states = {key: value for key, value in result["question_states"].items() if key in qids}
    safety = states.get("IN-08")
    if safety and not safety["observation_id"]:
        safety.update(status="unanswered", option_ids=[])
    return {
        "question_states": states,
        "derived": {key: value for key, value in result["derived"].items() if key in qids},
        "conflicts": result["synthesis"]["conflicts"],
        "ai_readiness": result["ai_readiness"],
        "active_round_id": result["active_round_id"],
    }
