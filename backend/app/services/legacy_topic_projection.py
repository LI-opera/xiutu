"""B01 server projection. Never consumes browser drafts or demo defaults."""
from collections import defaultdict

from app.topics.dkvb_b01 import catalog
from app.services.workbench_b02_conditions import blockers, is_non_execution_answer


def _opt(record):
    if not record:
        return None
    options = record["payload"].get("option_ids") or []
    return options[0] if options else None


def _number(record, name):
    try:
        field = record["payload"]["fields"][name]
        return float(field["value"])
    except (KeyError, TypeError, ValueError):
        return None


def project(case, records, report_gate, topic=None):
    topic = topic or catalog()[0]
    b02 = topic["version"] == "2.2.1-b02"
    plan = (case["intake_snapshot"] or {})["topic_plan"]
    questions = {q["id"]: q for q in topic["questions"]}
    superseded = {r["supersedes_id"] for r in records if r["supersedes_id"]}
    current = {}
    for record in records:
        if record["id"] not in superseded:
            payload = record["payload"]
            # A pre-repair question is always the same question instance,
            # including legacy B01 observations created after RET-01 before
            # the round-id normalization fix. Only S6 is round-scoped.
            qid = payload["question_id"]
            current[(qid, payload.get("round_id") if questions[qid]["stage"] == "S6" else None)] = record
    latest_round = plan["rounds"][-1]["id"] if plan["rounds"] else None
    if b02 and latest_round:
        action = current.get(("RET-01", latest_round))
        if not action or action["payload"].get("option_ids") == ["none"]:
            # Keep the round and all original retest records in history, but
            # do not project them as a post-repair conclusion without repair.
            latest_round = None
    def fact(qid):
        q = questions[qid]
        if b02 and qid == "RET-01" and latest_round is None:
            actions = [row for (question_id, _), row in current.items() if question_id == "RET-01"]
            return max(actions, key=lambda row: row["created_revision"], default=None)
        return current.get((qid, latest_round if q["stage"] == "S6" else None))
    def derive(qid, option=None, reason="", deps=(), detail=None):
        return {"question_id": qid, "option_id": option, "reason": reason,
                "basis_observation_ids": [str(fact(dep)["id"]) for dep in deps if fact(dep)],
                "detail": detail or {}}

    derived = {}
    static_ids = ("PRS-01", "PRS-02", "PRS-03")
    static = [fact(qid) for qid in static_ids]
    static_values = [_number(row, "hpa") for row in static]
    static_batch = plan["capture_batches"]["engine_off_static"]
    valid_static = all(row and _opt(row) == "recorded" and value is not None and
                       row["payload"].get("batch_id") == static_batch and
                       row["payload"]["fields"]["hpa"]["unit"] == "hPa absolute"
                       for row, value in zip(static, static_values))
    static_state = None
    if valid_static:
        ambient, g31, g71 = static_values
        if max(static_values) - min(static_values) <= 30:
            static_state = "consistent"
        elif abs(g31 - ambient) > 30 and abs(g71 - ambient) <= 30:
            static_state = "g31_outlier"
        elif abs(g71 - ambient) > 30 and abs(g31 - ambient) <= 30:
            static_state = "g71_outlier"
        else:
            static_state = "multiple_outliers"
    static_responded = all(static)
    static_option = static_state if static_state else "unavailable" if b02 and static_responded else None
    static_reason = ("同一熄火静态批次、hPa absolute；30 hPa 是专题演示带宽。" if valid_static else
        "已回应静态原始项，但有无法取得、信号缺失、批次或单位不可信；不能判断正常，需补充/交接。" if b02 and static_responded else
        "缺少已保存的静态原始项；演示默认值不算事实。")
    derived["PRS-04"] = derive("PRS-04", static_option, static_reason,
        static_ids, {"batch_id": static_batch, "values_hpa": static_values if valid_static else None,
                     "evidence_state": "computed" if static_state else "insufficient" if static_responded else "awaiting_input"})

    frame_ids = ("PRS-08", "PRS-09", "PRS-10")
    frames = [fact(qid) for qid in frame_ids]
    load_batch = plan["capture_batches"]["comparable_load_frames"]
    valid_frames = _opt(fact("PRS-07")) == "comparable" and all(
        row and _opt(row) == "recorded" and row["payload"].get("batch_id") == load_batch and
        _number(row, "target") is not None and _number(row, "actual") is not None and
        row["payload"]["fields"]["target"]["unit"] == "hPa absolute" and
        row["payload"]["fields"]["actual"]["unit"] == "hPa absolute"
        for row in frames)
    trend = None
    gaps = []
    if valid_frames:
        gaps = [_number(row, "target") - _number(row, "actual") for row in frames]
        if all(abs(gap) <= 150 for gap in gaps):
            trend = "tracks_target"
        elif all(gap > 250 for gap in gaps):
            trend = "persistent_underboost"
        elif any(gap > 250 for gap in gaps) and any(abs(gap) <= 150 for gap in gaps):
            trend = "intermittent_drop"
    frames_responded = bool(fact("PRS-07")) and all(frames)
    trend_option = trend if trend else "unreliable" if b02 and frames_responded else None
    derived["PRS-11"] = derive("PRS-11", trend_option,
        "同批次可比三帧；250/150 hPa 仅为演示判别带宽。" if trend else
        "原始项均已回应，但无法取得、工况/批次不可信或资料无该趋势（含超调）判据；仅可补充检查/交接。" if b02 and frames_responded else
        "缺少已保存的负荷原始项；不能计算。",
        ("PRS-07", *frame_ids), {"batch_id": load_batch, "gaps_hpa": gaps,
                                   "evidence_state": "computed" if trend else "insufficient" if frames_responded else "awaiting_input"})
    # Trend and trustworthy evidence are distinct; a correction to a relevant
    # static reading alters confidence but never erases independent TUR facts.
    # A static outlier is unresolved even when connector appearance and a
    # wiggle check look benign. Those observations cannot certify a bad
    # absolute-pressure reading as trustworthy. Recorded signal faults also
    # veto otherwise consistent static readings.
    signal_ok = (static_state == "consistent" and
                 _opt(fact("PRS-05")) in (None, "normal") and
                 _opt(fact("PRS-06")) in (None, "stable"))
    pressure_credible = bool(signal_ok and trend and valid_frames)
    pressure_deps = (*static_ids, "PRS-05", "PRS-06", "PRS-07", *frame_ids)
    derived["D-PRESSURE-EVIDENCE"] = derive("D-PRESSURE-EVIDENCE",
        "credible" if pressure_credible else None,
        "静态可信度、信号复核及同批次负荷趋势均支持。" if pressure_credible else
        "读数趋势不能单独作为可信诊断证据；静态或信号复核不足。G71专项资料不足时需人工补充。",
        pressure_deps)
    groups = (
        ("TUR-01", "TUR-02", "TUR-05"), ("TUR-03", "TUR-04"),
        ("TUR-06",), ("TUR-07", "TUR-08"))
    evidence_classes = []
    for index, group in enumerate(groups):
        if any(fact(qid) and any(questions[qid]["options"][i]["outcome"] == "abnormal"
                   for i, option in enumerate(questions[qid]["options"])
                   if option["id"] in fact(qid)["payload"]["option_ids"]) for qid in group):
            evidence_classes.append(("external_structure", "fluids", "mechanical", "noise_smoke")[index])
    if pressure_credible and trend == "persistent_underboost":
        evidence_classes.append("credible_pressure_deficit")
    turbo_state = "multiple_supporting_facts" if len(evidence_classes) >= 2 else "weak_support" if evidence_classes else None
    derived["TUR-09"] = derive("TUR-09", turbo_state,
        "按独立外部证据类别去重；两次异常点击不构成两类线索。" if evidence_classes else
        "尚无足够的独立线索；缺失证据不是排除涡轮故障。",
        (*sum((tuple(g) for g in groups), ()), *pressure_deps),
        {"evidence_classes": evidence_classes})
    directions = []
    if _opt(fact("X-01")) not in (None, "none", "unavailable") and _opt(fact("X-05")) in ("moved_with_coil", "moved_with_plug"):
        directions.append("ignition")
    if _opt(fact("X-06")) not in (None, "none", "unavailable") and _opt(fact("X-09")) in ("low_level", "quality_suspect", "restriction_suspect"):
        directions.append("fuel")
    if _opt(fact("X-10")) in ("restriction_clue", "overheat_clue", "rattle"):
        directions.append("exhaust")
    if _opt(fact("X-11")) in ("limited", "implausible") or _opt(fact("X-12")) in ("dtc", "position_abnormal"):
        directions.append("intake_control")
    derived["X-13"] = derive("X-13", "multiple" if len(directions) > 1 else directions[0] if directions else None,
        "各方向独立求值，所有命中方向均保留；资料不足不等于无异常。",
        tuple(f"X-{n:02}" for n in range(1, 13)), {"supported_directions": directions})
    treatment_changed_after_retest = False
    if b02 and latest_round:
        action = fact("RET-01")
        treatment_changed_after_retest = bool(action and action["supersedes_id"] and any(
            fact(qid) and fact(qid)["created_revision"] < action["created_revision"]
            for qid in ("RET-02", "RET-03", "RET-04", "RET-05", "RET-06")))
    if latest_round:
        missing_retest = [qid for qid in ("RET-02", "RET-03", "RET-04", "RET-05", "RET-06") if not fact(qid)]
        gap = "critical" if missing_retest or treatment_changed_after_retest or any(_opt(fact(qid)) == "unavailable" for qid in ("RET-03", "RET-04", "RET-05", "RET-06")) else "none"
        derived["RET-07"] = derive("RET-07", gap, "处理事实更正晚于复检记录，原复检需复核；不得自动判通过。" if treatment_changed_after_retest else "仅评价已开启的新复检轮次；缺项不视为失败。",
            ("RET-01", "RET-02", "RET-03", "RET-04", "RET-05", "RET-06"), {"missing": missing_retest})
        ret_state = None
        if gap == "critical": ret_state = "handoff_unavailable"
        elif _opt(fact("RET-06")) == "returned": ret_state = "continue_boost"
        elif _opt(fact("RET-04")) == "recovered" and _opt(fact("RET-05")) == "resolved" and _opt(fact("RET-06")) == "not_returned" and _opt(fact("RET-03")) == "comparable": ret_state = "demo_pass"
        elif _opt(fact("RET-04")) == "recovered" and _opt(fact("RET-05")) in ("unchanged", "improved"): ret_state = "cross_system"
        elif _opt(fact("RET-04")) == "still_underboost": ret_state = "continue_boost"
        derived["RET-08"] = derive("RET-08", ret_state, "处理事实已更正，请复核原轮次记录；最终报告仍受原门禁约束。" if treatment_changed_after_retest else "只对独立处理后批次形成演示判断；最终报告仍受原门禁约束。",
            ("RET-01", "RET-02", "RET-03", "RET-04", "RET-05", "RET-06"))

    intake = plan["intake"]
    inherited = {"IN-01": "dkvb", "IN-02": intake["symptom_condition"],
                 "IN-04": "current", "IN-08": intake["safety_gate"]}
    # The persisted list is the case's initial scope plus any legacy manual
    # expansion. New applicability comes only from configured topic rules and
    # effective server facts; browsing or saving an optional answer adds none.
    required = set(plan["required_question_ids"])
    policy = {rule["id"]: rule for rule in topic["plan_policy"]["conditional_expansion"]}
    matched_rules = []
    def add_rule(rule_id, *, exclude=()):
        required.update(qid for qid in policy[rule_id]["add"] if qid not in exclude)
        matched_rules.append(rule_id)
    def abnormal(qid):
        record = fact(qid)
        if not record:
            return False
        outcomes = {option["id"]: option["outcome"] for option in questions[qid]["options"]}
        return any(outcomes.get(option) == "abnormal" for option in record["payload"].get("option_ids", []))
    if _opt(fact("AIR-13")) in {"available", "alternative_safe_tool"}:
        add_rule("P-LEAK", exclude=("AIR-16",) if not fact("AIR-15") else ())
    if static_state in {"g31_outlier", "g71_outlier", "multiple_outliers"} or \
            _opt(fact("PRS-02")) == "signal_missing" or _opt(fact("PRS-03")) == "signal_missing":
        add_rule("P-SIGNAL")
    credible_low_boost = pressure_credible and trend == "persistent_underboost"
    if credible_low_boost or _opt(fact("IN-05")) in {"p2261_family", "both"} or abnormal("ACT-01"):
        add_rule("P-ACT", exclude=("ACT-09", "ACT-10"))
    if credible_low_boost or any(abnormal(qid) for qid in ("TUR-01", "TUR-02", "TUR-03", "TUR-04", "TUR-05", "TUR-06", "TUR-07", "TUR-08")):
        add_rule("P-TUR", exclude=("TUR-09",))
    if _opt(fact("IN-06")) in {"misfire", "fuel", "exhaust", "multiple"} or \
            any(abnormal(qid) for qid in ("X-01", "X-02", "X-03", "X-04", "X-05", "X-06", "X-07", "X-08", "X-09", "X-10", "X-11", "X-12")):
        add_rule("P-X", exclude=("X-13",))
    question_states = {}
    facts, issues, unavailable, missing = [], [], [], []
    for q in topic["questions"]:
        qid = q["id"]
        record = fact(qid)
        calculation = derived.get(qid)
        inherited_option = inherited.get(qid)
        option_ids = record["payload"]["option_ids"] if record else ([calculation["option_id"]] if calculation and calculation["option_id"] else [inherited_option] if inherited_option else [])
        answered = bool((record and option_ids) or inherited_option or (calculation and calculation["option_id"]))
        status = "derived" if calculation else "inherited" if inherited_option else "saved" if record and option_ids else "unanswered"
        condition_blockers = []
        if b02 and q.get("execution_conditions"):
            answers = {ref: (fact(ref)["payload"]["option_ids"] if fact(ref) else [])
                       for ref in q["prerequisites"]["refs"] if ref != "IN-08"}
            condition_blockers = blockers(q, answers, plan["intake"], questions)
        question_states[qid] = {"status": status, "option_ids": option_ids,
                                "observation_id": str(record["id"]) if record else None,
                                "calculation": calculation, "required": qid in required,
                                "condition_blockers": condition_blockers}
        if qid in required and not answered: missing.append(qid)
        if record and option_ids and q["stage"] != "S6":
            entry = {"question_id": qid, "option_ids": option_ids,
                     "observation_id": str(record["id"]), "area_id": q["area_id"]}
            outcomes = {o["id"]: o["outcome"] for o in q["options"]}
            if any(outcomes.get(opt) == "unavailable" for opt in option_ids) or (
                    b02 and is_non_execution_answer(q, option_ids)):
                unavailable.append(entry)
            elif any(outcomes.get(opt) == "abnormal" for opt in option_ids): issues.append(entry)
            else: facts.append(entry)
    conflicts = []
    if _opt(fact("AIR-07")) == "seated" and _opt(fact("AIR-08")) == "pulls_out":
        conflicts.append({"id": "C-AIR-07-08", "question_ids": ["AIR-07", "AIR-08"], "reason": "座合与保持力记录冲突，需复核。"})
    if latest_round and _opt(fact("RET-04")) == "recovered" and _opt(fact("RET-06")) == "returned":
        conflicts.append({"id": "C-RET-04-06", "question_ids": ["RET-04", "RET-06"], "reason": "压力恢复但故障码复现，不得判断通过。"})
    if treatment_changed_after_retest:
        conflicts.append({"id": "C-RET-01-REVISION", "question_ids": ["RET-01", "RET-04"],
                          "reason": "处理动作在复检记录之后更正；原复检保留，但不能直接支持处理效果判断。"})
    areas = []
    for area in topic["areas"]:
        ids = [q["id"] for q in topic["questions"] if q["area_id"] == area["id"]]
        area_issues = [x for x in issues if x["area_id"] == area["id"]]
        areas.append({"area_id": area["id"], "priority": area["initialPriority"],
                      "recorded": sum(bool(fact(qid) and fact(qid)["payload"].get("option_ids")) for qid in ids),
                      "required": sum(qid in required for qid in ids),
                      "missing": [qid for qid in ids if qid in missing],
                      "unavailable": sum(x["area_id"] == area["id"] for x in unavailable),
                      "abnormal": len(area_issues),
                      "recommendation": "建议优先核对已发现的异常" if area_issues else "可独立记录；未检查不等于正常"})
    if b02:
        # Rule-backed recommendation affects ranks, never card order, scope or
        # independent observations. Without a match, keep the frozen baseline.
        focus = None
        reason = ""
        signal_clue = static_state in {"g31_outlier", "g71_outlier", "multiple_outliers"} or any(
            _opt(fact(qid)) == "signal_missing" for qid in ("PRS-02", "PRS-03")) or trend_option == "unreliable"
        air_clue = any(x["area_id"] == "boost-air" for x in issues)
        actuator_clue = credible_low_boost or any(abnormal(f"ACT-{n:02}") for n in range(1, 8)) or _opt(fact("IN-05")) in {"p2261_family", "both"}
        turbo_clue = turbo_state == "multiple_supporting_facts"
        powertrain_clue = bool(directions)
        for hit, target, explanation in (
            (signal_clue, "pressure", "静态/负荷压力或信号记录提示先核对可信度（R11—R13）。"),
            (air_clue, "boost-air", "已保存空气通路异常，建议先核对并定位（R03—R09）。"),
            (actuator_clue, "actuator", "可信低增压或调节机构线索，建议核对调节方向（R14—R18）。"),
            (turbo_clue, "turbo", "已保存涡轮外部线索；仅建议专业检测，不代表内部损坏（R21—R22）。"),
            (powertrain_clue, "powertrain", "已保存其他动力系统支持线索，建议对应专项确认（R23—R25）。")):
            if hit:
                focus, reason = target, explanation
                break
        order = [a["area_id"] for a in areas]
        if focus:
            order.remove(focus)
            order.insert(0, focus)
        for area in areas:
            area["priority"] = order.index(area["area_id"]) + 1
            if area["area_id"] == focus:
                area["recommendation"] = reason
            elif not focus:
                area["recommendation"] = "保持初始建议；当前无资料规则支持调整。可独立记录。"
        recommendation_rule = ("R11-R13" if focus == "pressure" else "R03-R09" if focus == "boost-air" else
                               "R14-R18" if focus == "actuator" else "R21-R22" if focus == "turbo" else
                               "R23-R25" if focus == "powertrain" else None)
    else:
        recommendation_rule = None
    unresolved = bool(unavailable or conflicts or not pressure_credible or static_option == "unavailable" or trend_option == "unreliable")
    ai_ready = not missing and intake["safety_gate"] != "stop_now"
    return {"question_states": question_states, "derived": derived,
            "plan_evaluation": {"required_question_ids": sorted(required), "matched_rule_ids": matched_rules},
            "areas": areas, "recommendation_rule": recommendation_rule,
            "synthesis": {"facts": facts, "issues": issues,
                "unavailable": unavailable, "conflicts": conflicts, "missing_question_ids": missing,
                "next_step": "可依据现有记录分析；未检查内容将作为未知，必要时再补充。" if missing else
                    "关键证据仍有缺项或冲突；只能提出补充检查或交接方向。" if unresolved else
                    "可整理已保存事实供首次建议审阅；不能直接形成换件结论。"},
            "ai_readiness": {"ready_for_first_advice": ai_ready,
                "repair_conclusion_supported": ai_ready and not unresolved,
                "advice_scope": "supplement_or_handoff" if ai_ready and unresolved else "fact_review" if ai_ready else "not_ready",
                "evidence": {"raw_required_responded": not any(qid in missing and questions[qid]["answer_kind"] != "automatic_derived" for qid in missing),
                             "derived_computable": static_state is not None and trend is not None,
                             "evidence_sufficient": ai_ready and not unresolved},
                "reasons": (["本轮适用必需项未完成"] if missing else []) +
                    (["关键证据不足或冲突，分析时应标明未知与待确认事项"] if unresolved else []) +
                    (["安全停止"] if intake["safety_gate"] == "stop_now" else [])},
            "final_report_gate": report_gate, "active_round_id": latest_round}
