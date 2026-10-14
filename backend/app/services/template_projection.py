"""Data-driven template plan, observation progress and synthesis.

No vehicle, fault code, area name, question count or domain threshold belongs here.
Published domain calculations remain behind the explicit compatibility boundary.
"""
from types import SimpleNamespace
from uuid import uuid4

from app.domain.policies import DomainError
from app.services import template_choice_calculation as choice_calculation
from app.services import template_evidence_calculation as evidence_calculation
from app.services import template_observation_rules as observation_rules


def _require_independent(topic):
    if topic.get("calculation_catalog") is not None:
        raise DomainError("TEMPLATE_CALCULATOR_UNSUPPORTED", "模板计算规则版本尚不支持", 409)


def _validate_calculations(topic):
    catalog = topic.get("calculation_rules")
    if catalog is not None and not isinstance(catalog, dict):
        raise DomainError("TEMPLATE_CALCULATION_INVALID", "模板派生规则配置无效", 409)
    if catalog is None or catalog.get("version") == "choice-v1":
        return choice_calculation.validate(topic)
    if catalog.get("version") == evidence_calculation.VERSION:
        return evidence_calculation.validate(topic)
    raise DomainError("TEMPLATE_CALCULATION_INVALID", "模板派生规则配置无效", 409)


def build_plan(topic, intake):
    _require_independent(topic)
    _validate_calculations(topic)
    observation_rules.validate(topic)
    kinds = sorted({
        q["capture"]["batch_kind"] for q in topic["questions"]
        if (q.get("capture") or {}).get("batch_id_required")
    })
    return {"version": 1,
            "required_question_ids": [q["id"] for q in topic["questions"]
                                      if q["answer_kind"] != "automatic_derived"],
            "expanded_area_ids": [], "capture_batches": {kind: str(uuid4()) for kind in kinds},
            "rounds": [], "intake": dict(intake)}


def project_template(case, records, report_gate, topic):
    _require_independent(topic)
    return _project_template(case, records, report_gate, topic)


def _project_template(case, records, report_gate, topic, compatibility=None):
    plan = case["intake_snapshot"]["topic_plan"]
    questions = {q["id"]: q for q in topic["questions"]}
    required = set(plan["required_question_ids"]) & questions.keys()
    superseded = {r["supersedes_id"] for r in records if r.get("supersedes_id")}
    workflow = None
    active_round_id = None
    if not compatibility:
        from app.services.workbench_topic_workflow import workflow_for
        workflow = workflow_for(topic, template_bound=True)
        active_round_id = plan["rounds"][-1]["id"] if workflow.repair_id and plan["rounds"] else None
    current = {}
    for row in records:
        qid = row["payload"].get("question_id")
        if row["id"] in superseded or qid not in questions:
            continue
        if workflow and workflow.round_scoped(questions[qid]) and row["payload"].get("round_id") != active_round_id:
            continue
        current[qid] = row
    if workflow and active_round_id and workflow.repair_id:
        repair = current.get(workflow.repair_id)
        if not repair or set(repair["payload"].get("option_ids", [])) <= workflow.none_options:
            active_round_id = None
            current = {qid: row for qid, row in current.items()
                       if not workflow.round_scoped(questions[qid]) or qid == workflow.repair_id}
    states = compatibility["question_states"] if compatibility else {}
    if compatibility:
        derived = compatibility["derived"]
    elif (topic.get("calculation_rules") or {}).get("version") == evidence_calculation.VERSION:
        derived = evidence_calculation.evaluate(topic, current, plan)
    else:
        derived = choice_calculation.evaluate(topic, current)
    observation = (observation_rules.evaluate(topic, current) if not compatibility else
                   {"focus_question_ids": [], "matched_rule_ids": [], "conflicts": []})
    facts, issues, unavailable = [], [], []
    for qid, q in questions.items():
        row = current.get(qid)
        if not compatibility:
            options = row["payload"].get("option_ids", []) if row else []
            condition_blockers = workflow.prerequisites(
                q, plan, records, SimpleNamespace(option_ids=[])) if q["answer_kind"] == "conditional_operation" else []
            calculation = derived.get(qid)
            if q["answer_kind"] == "automatic_derived" and calculation:
                options = [calculation["option_id"]] if calculation["option_id"] else []
            states[qid] = {"status": "derived" if calculation else "saved" if options else "unanswered",
                           "option_ids": options,
                           "observation_id": str(row["id"]) if row else None,
                           "calculation": calculation, "condition_blockers": condition_blockers,
                           "focused": qid in observation["focus_question_ids"]}
        state = states[qid]
        state["required"] = qid in required
        options = state["option_ids"]
        if not state["observation_id"] or not options or not q.get("area_id"):
            continue
        outcomes = {o["id"]: o["outcome"] for o in q["options"]}
        entry = {"question_id": qid, "option_ids": options,
                 "observation_id": state["observation_id"], "area_id": q["area_id"]}
        bypass = (q.get("execution_conditions") or {}).get("bypass_options", [])
        if any(outcomes.get(o) == "unavailable" for o in options) or (len(options) == 1 and options[0] in bypass):
            unavailable.append(entry)
        elif any(outcomes.get(o) == "abnormal" for o in options):
            issues.append(entry)
        else:
            facts.append(entry)
    areas = []
    for index, area in enumerate(topic["areas"], 1):
        ids = {qid for qid, q in questions.items() if q.get("area_id") == area["id"]}
        areas.append({"area_id": area["id"], "priority": index,
                      "recorded": sum(bool(states[qid]["observation_id"] and states[qid]["option_ids"]) for qid in ids),
                      "required": len(ids & required),
                      "missing": [qid for qid in sorted(ids & required) if not states[qid]["option_ids"]],
                      "unavailable": sum(e["area_id"] == area["id"] for e in unavailable),
                      "abnormal": sum(e["area_id"] == area["id"] for e in issues),
                      "recommendation": "按匹配模板展示；可独立记录，未检查不等于正常"})
    area_ids = {a["id"] for a in topic["areas"]}
    area_qids = {qid for qid, q in questions.items() if q.get("area_id") in area_ids}
    conflicts = [item for item in (compatibility["conflicts"] if compatibility else observation["conflicts"])
                 if all(qid in area_qids for qid in item["question_ids"])]
    missing = [qid for a in areas for qid in a["missing"]]
    # A template without a calculator cannot infer derived answers or a repair conclusion.
    readiness = compatibility["ai_readiness"] if compatibility else {
        "ready_for_first_advice": bool(facts or issues or unavailable),
        "repair_conclusion_supported": False,
        "advice_scope": "fact_review" if facts or issues or unavailable else "not_ready",
        "reasons": ["未检查内容保留为未知"] if missing else [],
        "evidence": {"raw_required_responded": not missing,
                     "derived_computable": bool(derived) and all(v["option_id"] for v in derived.values()),
                     "evidence_sufficient": False},
    }
    return {"question_states": states, "derived": derived, "areas": areas,
            "recommendation_rule": None,
            "plan_evaluation": {"required_question_ids": sorted(required),
                                "matched_rule_ids": observation["matched_rule_ids"],
                                "focus_question_ids": observation["focus_question_ids"]},
            "synthesis": {"facts": facts, "issues": issues, "unavailable": unavailable,
                          "conflicts": conflicts, "missing_question_ids": missing,
                          "next_step": "保存检查结果后，可结合对应资料进行 AI 分析；实际处理与复检请分别记录。"},
            "ai_readiness": readiness, "final_report_gate": report_gate,
            "active_round_id": compatibility["active_round_id"] if compatibility else active_round_id}
