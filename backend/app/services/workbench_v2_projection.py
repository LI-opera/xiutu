"""Read-only V2 view projection from a formal case and its saved observations."""

from app.topics.dkvb_v2 import WIRED


def _area_order(case, effective):
    """Freeze the initial topic ordering to saved intake facts, not later checks."""
    default = ["boost-air", "pressure", "actuator", "turbo", "powertrain"]
    intake = next((item for item in effective if item["payload"].get("check_id") == "CHK-01"), None)
    if not intake or intake["kind"] == "unavailable":
        return default
    fields = intake["payload"].get("protocol_fields") or {}
    codes = set(case.get("fault_codes") or [])
    # Only the pressure/air entry directions are wired to the current formal
    # protocol. Other codes remain recorded context, not an actionable route.
    if "P0236" in codes or fields.get("symptom_conditions") == "intermittent":
        first = "pressure"
    else:
        first = "boost-air"
    return [first, *(area for area in default if area != first)]


def project(topic, case, diagnosis, observations):
    questions = {question["id"]: question for question in topic["questions"]}
    cards = {card["id"]: card for card in topic["cards"]}
    effective = [item for item in observations["items"] if item["effective"]]
    topic_facts = [item for item in effective if item["payload"].get("topic_question_id") in questions]
    current = diagnosis.get("current_step") or {}
    protocol = (current.get("validation") or {}).get("protocol") or {}
    current_check = protocol.get("next_check_id")
    active_question = next((question for (check, _), (question, _) in WIRED.items()
                            if check == current_check), None)
    areas = []
    order = _area_order(case, effective)
    for area in topic["areas"]:
        question_ids = {question_id for component_id in area["componentIds"]
                        for question_id in cards[component_id]["questionIds"]}
        rows = [item for item in topic_facts if item["payload"]["topic_question_id"] in question_ids]
        recorded = {item["payload"]["topic_question_id"] for item in rows}
        needs_review = any(item.get("supersedes_id") for item in rows)
        areas.append({"area_id": area["id"], "priority": order.index(area["id"]) + 1,
                      "recorded_questions": len(recorded), "total_questions": len(question_ids),
                      "recorded_question_ids": sorted(recorded),
                      "status": "current" if active_question in question_ids else
                                "needs_review" if needs_review else
                                "recorded" if recorded else "configured",
                      "needs_review": needs_review})
    facts = []
    for item in topic_facts:
        payload = item["payload"]
        question = questions[payload["topic_question_id"]]
        option = next((option for option in question["options"]
                       if option["id"] == payload["topic_option_id"]), None)
        facts.append({"observation_id": item["id"], "question_id": question["id"],
                      "option_id": payload["topic_option_id"],
                      "label": option["label"] if option else payload["option_label"],
                      "outcome": option["outcome"] if option else "unknown"})
    by_question = {fact["question_id"]: fact for fact in facts}
    completed_connector_path = all(
        by_question.get(question_id, {}).get("option_id") == option_id
        for question_id, option_id in (
            ("AIR-07", "partially_seated"), ("AIR-15", "connector"),
            ("RET-01", "reseat"), ("RET-04", "recovered"),
        )
    )
    explanation = (protocol.get("presentation") or {}).get("completion_explanation")
    if completed_connector_path:
        explanation = (
            "已记录接头未完全座合及该处局部泄漏；接头复位处理与同工况三帧恢复复检分别保存。"
            "这是合成演示小结，仍须遵守原协议最终复核与报告门禁，不能视为实车确诊。"
        )
    cited_id = protocol.get("observation_id")
    if completed_connector_path:
        cited_id = by_question["RET-04"]["observation_id"]
    if cited_id not in {item["id"] for item in effective}:
        cited_id = None
    return {"areas": areas, "current_check_id": current_check,
            "active_question_id": active_question,
            "synthesis": {"confirmed_facts": facts,
                          "issues": [fact for fact in facts if fact["question_id"].startswith("AIR-")
                                     and fact["outcome"] in {"abnormal", "unavailable"}],
                          "pending_area_ids": [area["area_id"] for area in areas if not area["recorded_questions"]][:3],
                          "current_explanation": explanation if case["status"] != "analyzing"
                              else "服务端正在重新计算下一步。",
                          "supporting_observation_id": cited_id}}
