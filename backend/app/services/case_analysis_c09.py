"""C09 frozen-snapshot publication policy. No model calls or mutable topic lookups."""

import re
from decimal import Decimal

from app.domain.case_analysis import CaseAdviceProposalV4, PublishedAdviceV4
from app.domain.policies import DomainError

CLAIM = re.compile(r"确诊|已排除|更换|换件|根因已明确|故障根因明确")
CAUSE = re.compile(r"导致|造成|根因是|故障位于|可归因于")
OPERATION = re.compile(r"加压|拆卸|拆装|安装|紧固|修理|修复|维修|更换|换件|基本设置|执行匹配|复位|"
                       r"清除故障码|检漏|重新采集|采集.{0,10}压力|测量.{0,10}压力|测试.{0,10}压力")
EXECUTE = re.compile(r"执行|实施|进行|开展|安排|尝试|直接|建议|应当|应该|请|需要|可在|可对|可将")
NUMBER = re.compile(r"(?i)(?<![\d.])(\d+(?:\.\d+)?)(?:\s*/\s*(\d+(?:\.\d+)?))?\s*"
                    r"(bar|hpa|kpa|rpm|n[·.\s]*m|%)(?![\w])")
LIMIT = re.compile(r"不得超过|不能超过|不应超过|上限|限值|阈值|控制在|设置为|设定为|加压至|加压到|扭矩|必须达到|应达到")
NEGATIVE = re.compile(r"(?:不能|不得|禁止|不应|无法|尚未|未|不|非).{0,10}$")
SPLIT = re.compile(r"[，。；;,：:!?！？]|(?<!\d)\.(?!\d)|但|却|然而|不过")
AREA_PREFIX = {"AIR": "boost-air", "PRS": "pressure", "ACT": "actuator",
               "TUR": "turbo", "IGN": "powertrain", "FUE": "powertrain",
               "EXH": "powertrain", "X": "powertrain"}
DIRECT_FIELD_ACTION = re.compile(r"重新采集|采集.{0,10}压力|测量.{0,10}压力|测试.{0,10}压力")
EDITORIAL_CAVEAT = re.compile(r"只是|仅为|仅是|仅用于|非厂家|非手册|不是|不作为|不能作为")
ADJACENT_CAVEAT = re.compile(r"^(?:非厂家|非手册|不是(?:厂家|手册)|不作为|不能作为|仅说明|仅用于|仅表示)")
EDITORIAL_MISUSE = re.compile(r"加压至|设置为|控制在|应达到|必须达到|"
                              r"(?:用作|作为|用于|当作|据此|足以|证明|判定).{0,12}"
                              r"(?:故障|确诊|维修|换件|安全|操作|厂家|手册|上限|标准|限值)|"
                              r"(?:实际|实车).{0,8}(?:操作|维修|诊断).{0,8}(?:上限|阈值|标准|限值)|"
                              r"(?:操作|加压|维修).{0,8}(?:上限|阈值|标准|限值)")


def reject(code, path, rule, reason, snapshot, actual=None):
    raise DomainError(code, reason, 502, details={
        "rule_id": rule, "field_path": path, "allowed_scope": snapshot["allowed_scope"],
        "expected": reason[:240], "actual": str(actual)[:160] if actual is not None else None})


def _clauses(text):
    return [part.strip() for part in SPLIT.split(text) if part.strip()]


def _numbers(snapshot):
    saved = set()
    for item in snapshot["observations"]:
        for field in item.get("fields", {}).values():
            if isinstance(field, dict) and isinstance(field.get("value"), (int, float)) and field.get("unit"):
                saved.add((Decimal(str(field["value"])), str(field["unit"]).split()[0].lower()))
    for result in snapshot.get("derived", {}).values():
        if not isinstance(result, dict) or result.get("detail", {}).get("evidence_state") != "computed":
            continue
        for key in ("values_hpa", "gaps_hpa"):
            for value in result.get("detail", {}).get(key, []):
                if isinstance(value, (int, float)):
                    saved.add((Decimal(str(value)), "hpa"))
    editorial = {(Decimal(str(item["value"])), item["unit"].lower())
                 for item in snapshot.get("editorial_thresholds", []) if item.get("kind") == "editorial_demo"}
    return saved, editorial


def _editorial_explained(clauses, index):
    clause = clauses[index]
    if "演示" not in clause:
        return False
    if EDITORIAL_CAVEAT.search(clause):
        return True
    return any(ADJACENT_CAVEAT.search(clauses[near]) and not EDITORIAL_MISUSE.search(clauses[near])
               for near in (index - 1, index + 1) if 0 <= near < len(clauses))


def _normalized_quote(text):
    return re.sub(r"[^\w\d]", "", text).lower()


def _cited_safety_clause(snapshot, clause, full_text, safety_sources, excerpts):
    # Citation is explanation only. It never creates a new executable action.
    if not re.search(r"引用.{0,8}摘录", full_text) or not re.search(
            r"(?:不代表|不能|并非|不等于).{0,16}(?:授权|执行|实施)", full_text):
        return False
    normalized_text, normalized_clause = _normalized_quote(full_text), _normalized_quote(clause)
    if not normalized_clause:
        return False
    action_sources = {sid for rule in snapshot.get("action_catalog", {}).get("actions", {}).values()
                      for sid in rule.get("required_excerpt_ids", [])}
    for sid in safety_sources:
        item = excerpts.get(sid)
        if not item or item["kind"] != "local_manual":
            continue
        source_text = _normalized_quote(item["text"])
        restrictive_safety = "不得超过" in item["text"] and "步骤" not in item["text"]
        if (sid in action_sources or restrictive_safety) and source_text in normalized_text and (
                normalized_clause in source_text):
            return True
    return False


def _pure_safety_disclaimer(clause):
    return bool(re.search(r"^(?:不代表|并非|不等于|不能|不得|禁止|不应|未获授权).{0,80}"
                          r"(?:授权执行|执行|实施).{0,80}(?:操作|行为|步骤)$", clause)) and not bool(
        re.search(r"(?:但|却|仍|并且|同时).{0,12}(?:建议|应|请|可|必须|执行|实施)", clause))


def _record_evidence_mention(clause, match):
    if match.group() != "检漏":
        return False
    before, after = clause[:match.start()], clause[match.end():]
    return bool(re.search(r"(?:补充|完善|核对)?(?:记录|补录|保存)|缺少|缺乏|尚无|未记录", before)) and (
        not EXECUTE.search(before)) and bool(re.search(r"结果|证据|记录", after[:12]))


def _record_question_limit(snapshot, clause, full_text, quantity, question_ids, excerpts):
    """A past-result question may repeat its frozen safety limit, not authorize a test."""
    if not question_ids or not re.search(r"(?:补充记录|补录|核对记录)", full_text) or not re.search(
            r"是否(?:已|曾).{0,32}执行", clause):
        return False
    if re.search(r"请|建议|应按|应以|应将|必须|加压至|设置为|控制在|进行|开展|实施", clause):
        return False
    questions = {item["question_id"]: item.get("name", "") for item in snapshot.get("unresolved_questions", [])}
    title_has_limit = any(any((Decimal(match.group(1)), match.group(3).lower()) == quantity
                                  for match in NUMBER.finditer(questions.get(qid, ""))) for qid in question_ids)
    manual_has_limit = any(item["kind"] == "local_manual" and "不得超过" in item["text"] and
                           any((Decimal(match.group(1)), match.group(3).lower()) == quantity
                               for match in NUMBER.finditer(item["text"])) for item in excerpts.values())
    return title_has_limit and manual_has_limit


def check_text(snapshot, path, value, *, role, safety_sources=(), record_question_ids=(),
               context=None, clause_index=None):
    """Role and frozen provenance precede conservative clause-level language checks."""
    saved, editorial = _numbers(snapshot)
    excerpts = {item["id"]: item for item in snapshot["source_context"]["excerpts"]}
    full_text = context if context is not None else value
    if role == "record":
        # Exact structured question citations are navigation labels, not execution text.
        # Any words before/after the exact title are still scanned.
        for target in snapshot.get("unresolved_questions", []):
            if target.get("name"):
                title_pattern = (re.escape(target["question_id"]) + r"[（(]\s*" +
                                 r"\s*".join(re.escape(char) for char in target["name"]) + r"\s*[）)]")
                value = re.sub(title_pattern, target["question_id"], value)
    clauses = _clauses(full_text)
    checks = [(clause_index, value)] if clause_index is not None else list(enumerate(_clauses(value)))
    for index, clause in checks:
        cited_safety = role == "safety" and _cited_safety_clause(
            snapshot, clause, full_text, safety_sources, excerpts)
        disclaimer = role == "safety" and _pure_safety_disclaimer(clause)
        for match in CLAIM.finditer(clause):
            if cited_safety or disclaimer:
                continue
            if not NEGATIVE.search(clause[:match.start()]):
                reject("ANALYSIS_UNSUPPORTED_CERTAINTY", path, "text.unsupported_certainty",
                       "不能发布肯定确诊、排除或换件断言", snapshot, clause)
        for match in CAUSE.finditer(clause):
            if cited_safety or disclaimer:
                continue
            if not NEGATIVE.search(clause[:match.start()]):
                reject("ANALYSIS_UNSUPPORTED_CAUSE", path, "text.unsupported_cause",
                       "自由文字不能代替有资料支持的结构化因果方向", snapshot, clause)
        for match in OPERATION.finditer(clause):
            if cited_safety or disclaimer or role in {"record", "handoff"} and _record_evidence_mention(clause, match):
                continue
            if NEGATIVE.search(clause[:match.start()]):
                continue
            if (EXECUTE.search(clause[:match.start()]) or re.match(r"^(?:应|须|必须|可|将)", clause)
                    or role in {"record", "handoff"}
                    or DIRECT_FIELD_ACTION.fullmatch(match.group())):
                reject("ANALYSIS_UNSUPPORTED_OPERATION", path, "text.unsupported_operation",
                       "具体技术操作只能由冻结 action_id 装配", snapshot, clause)
        for match in NUMBER.finditer(clause):
            unit = re.sub(r"[·.\s]", "", match.group(3)).lower()
            quantities = [(Decimal(part), unit) for part in (match.group(1), match.group(2)) if part is not None]
            if (role == "record" and len(quantities) == 1 and _record_question_limit(
                    snapshot, clause, full_text, quantities[0], record_question_ids, excerpts)):
                continue
            neighboring = " ".join(clauses[max(0, index - 1): min(len(clauses), index + 2)])
            if (all(quantity in editorial for quantity in quantities)
                    and role in {"uncertainty", "direction_limit"}
                    and _editorial_explained(clauses, index)
                    and not EDITORIAL_MISUSE.search(neighboring)):
                continue
            if LIMIT.search(clause):
                if role == "safety" and safety_sources and ("不得" in clause or "禁止" in clause):
                    supported = any(item["kind"] == "local_manual" and
                                    NUMBER.search(item["text"]) and
                                    (Decimal(NUMBER.search(item["text"]).group(1)),
                                     NUMBER.search(item["text"]).group(3).lower()) == quantities[0] and
                                    len(quantities) == 1 and
                                    "不得超过" in item["text"]
                                    for sid in safety_sources if (item := excerpts.get(sid)))
                    if supported and not EXECUTE.search(clause):
                        continue
                reject("ANALYSIS_UNSUPPORTED_PARAMETER", path, "number.operation_limit",
                       "手册限值不是独立操作授权；安全引用须有对应冻结摘录", snapshot, clause)
            if all(quantity in saved for quantity in quantities):
                continue
            reject("ANALYSIS_UNSUPPORTED_PARAMETER", path, "number.provenance",
                   "数值必须对应冻结测量、派生结果或明确标识的演示阈值", snapshot, clause)


def _refs(snapshot, path, facts=(), sources=(), missing=()):
    fact_ids = {item["id"] for item in snapshot["observations"]}
    source_ids = {item["id"] for item in snapshot["source_context"]["excerpts"]}
    missing_ids = {item["question_id"] for item in snapshot.get("unresolved_questions", [])}
    for name, values, allowed in (("basis_observation_ids", facts, fact_ids),
                                  ("source_ids", sources, source_ids),
                                  ("missing_question_ids", missing, missing_ids)):
        if len(values) != len(set(values)) or not set(values) <= allowed:
            reject("ANALYSIS_INVALID_REFERENCE", f"{path}.{name}", f"reference.{name}",
                   "引用必须属于本次冻结的有效事实、正文摘录或缺项", snapshot, values)


def _global(snapshot, data):
    _refs(snapshot, "safety_notice", sources=data.get("safety_source_ids", []))
    for field in ("summary", "retest_plan", "uncertainty", "safety_notice"):
        if field == "retest_plan" and data[field] is None:
            continue
        check_text(snapshot, field, data[field], role="safety" if field == "safety_notice" else
                   "uncertainty" if field == "uncertainty" else "explanation",
                   safety_sources=data.get("safety_source_ids", []) if field == "safety_notice" else ())
    for index, value in enumerate(data["unconfirmed_directions"]):
        check_text(snapshot, f"unconfirmed_directions[{index}]", value, role="explanation")


def _direction(snapshot, item, path):
    _refs(snapshot, path, item["basis_observation_ids"], item["source_ids"])
    if not item["basis_observation_ids"]:
        reject("ANALYSIS_UNSUPPORTED_DIRECTION", path + ".basis_observation_ids", "direction.fact_required",
               "可能方向至少引用一条有效事实", snapshot)
    if item["type"] == "technical_cause":
        # No frozen excerpt currently establishes a DKVB/P0299 causal diagnosis.
        reject("ANALYSIS_UNSUPPORTED_CAUSE", path + ".type", "direction.causal_source_missing",
               "本次冻结资料没有可发布的因果判断映射", snapshot, item["title"])
    check_text(snapshot, path + ".title", item["title"], role="direction")
    check_text(snapshot, path + ".limit", item["limit"], role="direction_limit")


def _controlled(snapshot, item, path):
    from app.services.case_analysis_actions import action_case_applicable, action_facts_satisfied
    action_id = item["action_id"]
    rule = snapshot.get("action_catalog", {}).get("actions", {}).get(action_id)
    if rule is None:
        reject("ANALYSIS_ACTION_NOT_SUPPORTED", path + ".action_id", "action.known",
               "操作必须来自本次冻结清单", snapshot, action_id)
    if snapshot["allowed_scope"] not in rule["allowed_scopes"]:
        reject("ANALYSIS_SCOPE_EXCEEDED", path + ".action_id", "action.scope",
               "操作不属于本次允许范围", snapshot, action_id)
    if not action_case_applicable(rule, snapshot.get("vehicle", {})):
        reject("ANALYSIS_ACTION_SCOPE_MISMATCH", path + ".action_id", "action.vehicle_applicability",
               "车型年款不在冻结手册操作的已核对适用范围", snapshot, action_id)
    excerpts = {entry["id"]: entry for entry in snapshot["source_context"]["excerpts"]}
    required = rule["required_excerpt_ids"]
    if not required or any(sid not in excerpts or excerpts[sid]["kind"] != "local_manual" for sid in required) or (
            excerpts[required[0]]["text"] != rule["required_excerpt_text"]):
        reject("ANALYSIS_ACTION_SOURCE_MISMATCH", path + ".action_id", "action.source_missing",
               "冻结手册正文与操作清单不匹配", snapshot, action_id)
    basis = item["basis_observation_ids"]
    _refs(snapshot, path, basis)
    facts = {fact["id"]: fact for fact in snapshot["observations"]}
    if not action_facts_satisfied(rule, [facts[fid] for fid in basis]):
        reject("ANALYSIS_ACTION_FACT_MISSING", path + ".basis_observation_ids", "action.fact",
               "操作缺少满足全部前提选项的有效事实", snapshot, basis)
    return {"kind": rule["kind"], "action_id": action_id, "action": rule["action"],
            "prerequisites": rule["prerequisites"], "basis_observation_ids": basis,
            "source_ids": required, "retest": rule["retest"], "stop_condition": rule["stop_condition"]}


def _step(snapshot, item, path):
    if item["type"] == "controlled":
        return _controlled(snapshot, item, path)
    facts, missing = item["basis_observation_ids"], item["missing_question_ids"]
    _refs(snapshot, path, facts, item.get("source_ids", []), missing)
    if not facts and not missing:
        reject("ANALYSIS_FREE_STEP_INCOMPLETE", path, "step.basis_required",
               "补记录或交接必须引用有效事实或服务端缺项", snapshot)
    if item["type"] == "record":
        qids = item["question_ids"]
        available = {fact["question_id"] for fact in snapshot["observations"]} | {
            target["question_id"] for target in snapshot.get("unresolved_questions", [])}
        if len(qids) != len(set(qids)) or not set(qids) <= available:
            reject("ANALYSIS_INVALID_REFERENCE", path + ".question_ids", "reference.question",
                   "补记录只可导航本次冻结的已有问题", snapshot, qids)
        for field in ("request", "reason"):
            check_text(snapshot, path + "." + field, item[field], role="record",
                       record_question_ids=qids)
        return {"kind": "record", "action": item["request"], "reason": item["reason"],
                "question_ids": qids, "basis_observation_ids": facts,
                "missing_question_ids": missing, "source_ids": []}
    for field in ("action", "reason"):
        check_text(snapshot, path + "." + field, item[field], role="handoff")
    # A citation attached to an entire handoff must not imply that a narrow
    # manual excerpt supports every area in a mixed-area summary. Use only the
    # scope of operations frozen with this analysis, not a current catalog.
    facts_by_id = {fact["id"]: fact for fact in snapshot["observations"]}
    for source_id in item["source_ids"]:
        scoped_areas = {AREA_PREFIX.get(qid.split("-")[0])
                        for rule in snapshot.get("action_catalog", {}).get("actions", {}).values()
                        if source_id in rule.get("required_excerpt_ids", [])
                        for qid in rule.get("required_question_options", {})}
        if scoped_areas and any(AREA_PREFIX.get(facts_by_id[fid]["question_id"].split("-")[0])
                                not in scoped_areas for fid in facts):
            reject("ANALYSIS_SOURCE_APPLICABILITY_UNCONFIRMED", path + ".source_ids",
                   "source.applicability_unconfirmed",
                   "该摘录只支持部分区域，不能作为跨区域交接内容的整体资料依据", snapshot, source_id)
    return {"kind": "handoff", "action": item["action"], "reason": item["reason"],
            "basis_observation_ids": facts, "missing_question_ids": missing,
            "source_ids": item["source_ids"]}


def _reason(exc, path):
    details = exc.details or {}
    return {"field_path": details.get("field_path", path), "rule_id": details.get("rule_id", exc.code),
            "reason": exc.message[:160]}


def _retest_independent(snapshot, proposal):
    """Fail closed when an unsupported retest supplies evidence or safeguards.

    This is a bounded dependency check, not a general natural-language proof.
    Safety limits in the discarded plan, or another section asking for that
    same new measurement, require rejection of the whole proposal.
    """
    plan = proposal["retest_plan"]
    if re.search(r"安全|停止|不得|禁止|不应|必须|前提|才能|应先|先确认|上限|限值", plan):
        reject("ANALYSIS_PARTIAL_DEPENDENCY", "retest_plan", "publication.retest_safety_dependency",
               "复检方案含可能必要的安全限制，不能单独移除", snapshot)
    retained = [proposal["summary"], proposal["uncertainty"], proposal["safety_notice"],
                *proposal["unconfirmed_directions"]]
    for direction in proposal["supported_directions"]:
        retained.extend((direction["title"], direction["limit"]))
    for step in proposal["steps"]:
        retained.extend(step[key] for key in ("request", "action", "reason") if key in step)
    dependent = re.compile(r"重新采集|采集.{0,10}压力|测量.{0,10}压力|测试.{0,10}压力|"
                           r"复检(?:后|结果|证明)|复测(?:后|结果|证明)|新(?:采集|测量).{0,12}(?:后|结果)")
    if any(dependent.search(text) for text in retained):
        reject("ANALYSIS_PARTIAL_DEPENDENCY", "retest_plan", "publication.retest_content_dependency",
               "其他内容仍引用未获支持的复检或其结果，不能单独发布", snapshot)


def assemble(snapshot, raw):
    proposal = CaseAdviceProposalV4.model_validate(raw).model_dump(mode="json")
    # All global content other than retest must pass before any partial result.
    _global(snapshot, {**proposal, "retest_plan": None})
    directions, steps, rejected = [], [], []
    retest_plan = proposal["retest_plan"]
    try:
        check_text(snapshot, "retest_plan", retest_plan, role="explanation")
    except DomainError as exc:
        if (exc.details or {}).get("rule_id") != "text.unsupported_operation":
            raise
        retest_plan = None
        rejected.append(_reason(exc, "retest_plan"))
    for index, item in enumerate(proposal["supported_directions"]):
        path = f"supported_directions[{index}]"
        try:
            _direction(snapshot, item, path)
            directions.append(item)
        except DomainError as exc:
            if (exc.details or {}).get("rule_id", "").startswith("text."):
                raise  # Unsafe free prose may contaminate the whole explanation.
            rejected.append(_reason(exc, path))
    for index, item in enumerate(proposal["steps"]):
        path = f"steps[{index}]"
        try:
            steps.append(_step(snapshot, item, path))
        except DomainError as exc:
            if (exc.details or {}).get("rule_id", "").startswith("text."):
                raise
            rejected.append(_reason(exc, path))
    if retest_plan is None:
        retained = {**proposal, "supported_directions": directions,
                    "steps": [proposal["steps"][index] for index, item in enumerate(proposal["steps"])
                              if not any(re.match(rf"steps\[{index}\](?:\.|$)", failure["field_path"])
                                         for failure in rejected)]}
        _retest_independent(snapshot, retained)
    if rejected:
        global_text = " ".join([proposal["summary"], retest_plan or "", proposal["uncertainty"],
                                proposal["safety_notice"], *proposal["unconfirmed_directions"]])
        for failure in rejected:
            match = re.match(r"(steps|supported_directions)\[(\d+)\]", failure["field_path"])
            if not match:
                continue
            item = proposal[match.group(1)][int(match.group(2))]
            markers = ([item["action_id"]] if item.get("action_id") else
                       [item["title"]] if item.get("title") else item.get("question_ids", []))
            if any(marker in global_text for marker in markers):
                reject("ANALYSIS_PARTIAL_DEPENDENCY", "summary", "publication.dependency",
                       "整体说明依赖未通过的方向或建议", snapshot, failure["field_path"])
        if not steps and not directions:
            reject("ANALYSIS_NO_SAFE_SECTION", "steps", "publication.empty",
                   "没有可独立展示的合格方向或建议", snapshot)
    content = {key: proposal[key] for key in ("summary", "unconfirmed_directions", "retest_plan",
                                              "uncertainty", "safety_notice")}
    content["retest_plan"] = retest_plan
    content.update(supported_directions=directions, steps=steps,
                   publication={"contract_version": "case-advice-proposal-c09-v1",
                                "state": "partial" if rejected else "complete",
                                "rejected_sections": rejected,
                                "safety_source_ids": proposal["safety_source_ids"]})
    return validate(snapshot, content)


def validate(snapshot, content):
    draft = PublishedAdviceV4.model_validate(content)
    value = draft.model_dump(mode="json")
    publication = value["publication"]
    if publication.get("contract_version") != "case-advice-proposal-c09-v1" or (
            publication.get("state") == "complete") != (not publication.get("rejected_sections")) or (
                publication.get("state") not in {"complete", "partial"}):
        reject("ANALYSIS_PUBLICATION_INVALID", "publication", "publication.state",
               "发布状态须与被拒绝类别一致", snapshot)
    retest_rejected = any(section.get("field_path") == "retest_plan" and
                          section.get("rule_id") == "text.unsupported_operation"
                          for section in publication.get("rejected_sections", []))
    if (value["retest_plan"] is None) != retest_rejected:
        reject("ANALYSIS_PUBLICATION_INVALID", "retest_plan", "publication.retest_state",
               "仅明确拒绝且独立的复检方案可从部分发布内容中省略", snapshot)
    _global(snapshot, {**value, "safety_source_ids": publication.get("safety_source_ids", [])})
    for index, item in enumerate(value["supported_directions"]):
        _direction(snapshot, item, f"supported_directions[{index}]")
    for index, item in enumerate(value["steps"]):
        path = f"steps[{index}]"
        if item["action_id"]:
            if item["question_ids"] or item["missing_question_ids"]:
                reject("ANALYSIS_PUBLICATION_INVALID", path, "publication.controlled_extra",
                       "受控操作不得夹带补记录目标", snapshot)
            expected = _controlled(snapshot, item, path)
            if any(item.get(key) != expected.get(key) for key in
                   ("kind", "action", "prerequisites", "retest", "stop_condition", "source_ids")):
                reject("ANALYSIS_ACTION_TEXT_MISMATCH", path, "action.controlled_text",
                       "受控操作必须与冻结清单逐项相同", snapshot)
        elif item["kind"] == "record":
            if item["source_ids"] or item["prerequisites"] or item["retest"] or item["stop_condition"]:
                reject("ANALYSIS_PUBLICATION_INVALID", path, "publication.record_extra",
                       "补记录步骤不得夹带操作条件或资料授权", snapshot)
            _step(snapshot, {"type": "record", "request": item["action"], "reason": item["reason"],
                             "question_ids": item["question_ids"], "basis_observation_ids": item["basis_observation_ids"],
                             "missing_question_ids": item["missing_question_ids"]}, path)
        elif item["kind"] == "handoff":
            if item["question_ids"] or item["prerequisites"] or item["retest"] or item["stop_condition"]:
                reject("ANALYSIS_PUBLICATION_INVALID", path, "publication.handoff_extra",
                       "交接步骤不得夹带操作条件", snapshot)
            _step(snapshot, {"type": "handoff", "action": item["action"], "reason": item["reason"],
                             "basis_observation_ids": item["basis_observation_ids"],
                             "missing_question_ids": item["missing_question_ids"],
                             "source_ids": item["source_ids"]}, path)
        else:
            reject("ANALYSIS_PUBLICATION_INVALID", path + ".kind", "publication.step_kind",
                   "未登记的自由执行步骤不得发布", snapshot, item["kind"])
    return value
