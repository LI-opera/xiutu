"""Shared B02 analysis facts, source selection and readiness projection."""

import os
import re

from app.services.case_analysis_context import (MAX_INPUT_CHARS,
                                                 OUTPUT_CONTRACT_VERSION, PREVIOUS_OUTPUT_CONTRACT_VERSION,
                                                 PROMPT_VERSION, selected_context)
from app.services.case_analysis_actions import (action_case_applicable, action_facts_satisfied,
                                                supported_actions)
from app.services.case_analysis_air_reference import reference_context


__all__ = ["MAX_INPUT_CHARS", "PROMPT_VERSION", "configured_mode", "freeze_generation_settings", "_current_snapshot", "_conditional_question_context", "_question_targets", "_gate"]

def configured_mode(settings):
    mode = os.environ.get("XIUTU_C01_MODEL_MODE", "disabled")
    if mode == "stub":
        return {"mode": "stub", "enabled": True, "provider": "model_substitute",
                "model": "dkvb-c01-deterministic-stub", "paid": False}
    if mode == "real":
        enabled = os.environ.get("XIUTU_C01_REAL_AUTHORIZED") == "1" and bool(settings.deepseek_api_key)
        return {"mode": "real", "enabled": enabled, "provider": settings.llm_provider,
                "model": settings.deepseek_model, "paid": True}
    return {"mode": "disabled", "enabled": False, "provider": settings.llm_provider,
            "model": settings.deepseek_model, "paid": False}


def freeze_generation_settings(snapshot, mode, settings):
    """One server setting drives the preview, frozen task and gateway request."""
    snapshot.update({"mode": mode["mode"], "provider": mode["provider"], "model": mode["model"],
                     "max_output_tokens": settings.case_analysis_max_output_tokens,
                     "max_real_calls": 1})
    return snapshot


def _current_snapshot(view):
    topic = view["topic"]
    question_by_id = {q["id"]: q for q in topic["questions"]}
    effective = [item for item in view["observations"] if item["effective"]]
    effective.sort(key=lambda item: (item["created_revision"], item["id"]))
    observations = []
    for item in effective:
        q = question_by_id[item["question_id"]]
        payload = item["payload"]
        observations.append({"id": item["id"], "question_id": q["id"], "question": q["title"],
                             "option_ids": payload["option_ids"], "option_labels": [o["label"] for o in q["options"] if o["id"] in payload["option_ids"]],
                             "fields": payload.get("fields", {}), "note": payload.get("note", ""),
                             "unavailable_reason": payload.get("unavailable_reason", ""),
                             "batch_id": payload.get("batch_id"), "round_id": payload.get("round_id"),
                             "created_revision": item["created_revision"], "source_refs": payload.get("source_refs", [])})
    projection = view["view"]
    case = view["case"]
    relevant_ids = set(projection["plan_evaluation"]["required_question_ids"])
    relevant_ids.update(item["question_id"] for item in observations)
    relevant_ids.update(item["question_id"] for item in projection["synthesis"]["issues"])
    relevant_ids.update(item["question_id"] for item in projection["synthesis"]["unavailable"])
    source_context = reference_context(case["id"]) or selected_context(topic, sorted(relevant_ids))
    readiness = projection["ai_readiness"]
    actions = supported_actions(source_context, case["vehicle"])
    scope = "supplement_or_handoff" if readiness["advice_scope"] == "supplement_or_handoff" else "fact_review"
    if scope == "fact_review" and any(
        rule["kind"] == "conditional_action" and
        action_case_applicable(rule, case["vehicle"]) and
        action_facts_satisfied(rule, observations)
        for rule in actions["actions"].values()
    ):
        # An executable suggestion requires BOTH a responsive, conflict-free
        # plan and a source-backed action with matching saved facts.
        scope = "conditional_action"
    frozen = {"case_id": case["id"], "case_revision": case["revision"],
              "topic_binding": case["intake_snapshot"]["topic_binding"],
              "vehicle": case["vehicle"], "fault_description": case["fault_description"],
              "fault_codes": case["fault_codes"], "intake": view["plan"]["intake"],
              "plan": view["plan"], "observations": observations,
              "derived": projection["derived"], "synthesis": projection["synthesis"],
              "unresolved_questions": _question_targets(topic,
                  list(projection["synthesis"].get("missing_question_ids", [])) +
                  [item["question_id"] for item in projection["synthesis"].get("unavailable", [])],
                  observations),
              "plan_evaluation": projection["plan_evaluation"],
              "ai_readiness": readiness, "active_round_id": projection["active_round_id"],
              "conditional_question_context": _conditional_question_context(topic, projection),
              "source_context": source_context, "action_catalog": actions,
              "question_catalog": [{"id": q["id"], "title": q["title"],
                                    "answer_kind": q["answer_kind"]} for q in topic["questions"]],
              "editorial_thresholds": [
                  {"question_id": rule["question_id"], "id": threshold["id"],
                   "value": threshold["value"], "unit": threshold["unit"],
                   "kind": "editorial_demo", "source_id": threshold["source_id"]}
                  for rule in topic.get("derived_rules", [])
                  for threshold in rule.get("thresholds", [])
                  if threshold.get("source_id") == "EDITORIAL_DEMO"],
              "reference_contract": {
                  "source_ids": [item["id"] for item in source_context["excerpts"]],
                  "observation_ids": [item["id"] for item in observations],
                  "missing_question_ids": [item["question_id"] for item in _question_targets(topic,
                      list(projection["synthesis"].get("missing_question_ids", [])) +
                      [item["question_id"] for item in projection["synthesis"].get("unavailable", [])], observations)],
                  "not_citable": ["source_metadata", "editorial_cards", "image_references", "source_ref", "asset_ids"],
              },
              "allowed_scope": scope,
              "prompt_version": PROMPT_VERSION,
              "output_contract_version": OUTPUT_CONTRACT_VERSION,
              "synthetic": True, "formal_usable": False}
    return frozen


def _conditional_question_context(topic, projection):
    """Describe existing unanswered conditional questions; never change facts or gates."""
    states = projection.get("question_states", {})
    result = []
    for question in topic["questions"]:
        conditions = question.get("execution_conditions")
        state = states.get(question["id"], {})
        if not conditions or state.get("status") != "unanswered":
            continue
        result.append({
            "question_id": question["id"], "question": question["title"],
            "record_state": "not_recorded",
            "execution_requirements": conditions.get("requirements", []),
            "current_unmet_requirements": state.get("condition_blockers", []),
        })
    return result


def _question_targets(topic, question_ids, observations):
    questions = {q["id"]: q for q in topic["questions"]}
    answered = {item["question_id"] for item in observations if item.get("effective", True)}

    def raw_target(qid, seen=None):
        seen = set(seen or ())
        if qid in seen or qid not in questions:
            return None
        seen.add(qid)
        q = questions[qid]
        if q["answer_kind"] != "automatic_derived":
            return qid
        deps = q.get("dependency_question_ids", [])
        for dep in deps:
            target = raw_target(dep, seen)
            if target and target not in answered:
                return target
        for dep in deps:
            target = raw_target(dep, seen)
            if target:
                return target
        return None

    targets = []
    for qid in dict.fromkeys(question_ids):
        q = questions.get(qid)
        if not q:
            continue
        name = re.sub(r"^[A-Z]+-\d+\s*[·：]?\s*", "", q["title"])
        targets.append({"question_id": qid, "name": name,
                        "target_question_id": raw_target(qid)})
    return targets


def _gate(view, *, contract_version=OUTPUT_CONTRACT_VERSION):
    readiness = view["view"]["ai_readiness"]
    missing = view["view"]["synthesis"]["missing_question_ids"]
    missing_questions = _question_targets(view["topic"], missing, view["observations"])
    safety = view["plan"]["intake"]["safety_gate"]
    if safety == "stop_now":
        return {"allowed": False, "reason": "安全停止；不能请求继续危险操作", "missing_question_ids": missing,
                "missing_questions": missing_questions}
    if contract_version not in {PREVIOUS_OUTPUT_CONTRACT_VERSION, OUTPUT_CONTRACT_VERSION} and not readiness["ready_for_first_advice"]:
        return {"allowed": False, "reason": "本轮适用必需原始项尚未回应", "missing_question_ids": missing,
                "missing_questions": missing_questions}
    return {"allowed": True,
            "reason": ("可依据现有记录分析；未检查内容将作为未知，不代表已排除" if missing else
                       "允许请求病例建议，范围由已保存事实和资料限定"),
            "missing_question_ids": missing, "missing_questions": missing_questions}


