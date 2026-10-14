"""Current C14 publication policy; older frozen contracts keep their own policies.

One semantic pass assigns each model field its responsibility. Final validation
checks publication invariants only; it does not rescan prose with a second,
possibly inconsistent, keyword policy. This is deliberately bounded language
screening, not a proof about arbitrary natural language.
"""

import re
from decimal import Decimal

from app.services.case_analysis_actions import action_case_applicable
from app.domain.case_analysis import (CaseAdviceProposalV5, CaseAdviceProposalV6,
                                      CaseAdviceProposalV7, PublishedAdviceV5, PublishedAdviceV7)
from app.domain.policies import DomainError
from app.services import case_analysis_c09 as legacy

VERSION = "case-advice-proposal-c14-v1"
C16_VERSION = "case-advice-proposal-c16-v1"
CURRENT_VERSION = "case-advice-proposal-c17-v1"
NUMBER = legacy.NUMBER
CERTAINTY = re.compile(r"确诊|已排除|故障根因明确|根因已明确|必须更换|需要更换|直接换件")
OPERATION = re.compile(r"加压|拆卸|拆装|紧固|修理|修复|维修|更换|换件|基本设置|执行匹配|"
                       r"清除故障码|重新采集|重新测量|重新测试|采集.{0,10}压力|测量.{0,10}压力|"
                       r"测试.{0,10}压力|检漏")
DIRECTIVE = re.compile(r"请|建议|应当|应该|应|必须|需要|执行|实施|进行|开展|安排|尝试|可在|可对|可将")
NEGATION = re.compile(r"不需要|不能|不得|禁止|不应|不可|无法|尚未|未|不|非")
AFFIRMATIVE = re.compile(r"建议|应当|应该|需要|请|可在|可对|可将")
RECORD_INTENT = re.compile(r"补充|补录|核对|完善|保存|记录|未记录|缺少|缺乏")
LIMIT = re.compile(r"不得超过|不能超过|不应超过|上限|限值|阈值|控制在|设置为|设定为|加压至|加压到|扭矩|必须达到|应达到")
EDITORIAL_LABEL = re.compile(r"演示|编辑性|非厂家|非手册")
EDITORIAL_AS_STANDARD = re.compile(r"(?:作为|用作|据此|按此).{0,12}(?:厂家|手册|安全|维修|操作|换件|确诊)|"
                                   r"(?<!不)(?<!非)(?:是|属于)(?:厂家|手册).{0,10}(?:标准|限值)|"
                                   r"足以.{0,8}(?:判断故障|确诊|换件)")
NEW_TEST = re.compile(r"重新采集|重新测量|重新测试|采集.{0,10}压力|测量.{0,10}压力|测试.{0,10}压力")
SENTENCE = re.compile(r"[。；;!?！？\n]|但|却|然而|不过")


def reject(snapshot, path, rule, reason, value=None, code="ANALYSIS_SCOPE_EXCEEDED"):
    raise DomainError(code, reason, 502, details={
        "rule_id": rule, "field_path": path, "allowed_scope": snapshot["allowed_scope"],
        "expected": reason[:240], "actual": str(value)[:160] if value is not None else None})


def _sentences(text):
    return [part.strip() for part in SENTENCE.split(text) if part.strip()]


def _negated(sentence, position):
    prefix = re.split(r"[，,]", sentence[max(0, position - 50):position])[-1]
    if re.search(r"不(?:代表|构成|意味着).{0,20}(?:授权|允许|要求).{0,10}(?:执行|实施)?", prefix):
        return True
    matches = list(NEGATION.finditer(prefix))
    if not matches:
        return False
    # A subsequent affirmative instruction overrides an earlier caveat.
    tail = prefix[matches[-1].end():]
    return not (AFFIRMATIVE.search(tail) or re.search(r"、(?:实施|进行|执行)", tail))


def _frozen_numbers(snapshot):
    saved, editorial = legacy._numbers(snapshot)
    manual = {}
    for excerpt in snapshot["source_context"]["excerpts"]:
        if excerpt["kind"] != "local_manual":
            continue
        for match in NUMBER.finditer(excerpt["text"]):
            unit = re.sub(r"[·.\s]", "", match.group(3)).lower()
            for part in (match.group(1), match.group(2)):
                if part is not None:
                    manual.setdefault((Decimal(part), unit), set()).add(excerpt["id"])
    return saved, editorial, manual


def _recorded_question_limit(snapshot, quantities, question_ids):
    if not question_ids:
        return False
    names = {item["question_id"]: item.get("name", "")
             for item in snapshot.get("unresolved_questions", [])}
    for qid in question_ids:
        title = names.get(qid, "")
        found = {(Decimal(part), re.sub(r"[·.\s]", "", match.group(3)).lower())
                 for match in NUMBER.finditer(title) for part in (match.group(1), match.group(2))
                 if part is not None}
        if quantities <= found:
            return True
    return False


def _text(snapshot, path, text, *, role, source_ids=(), question_ids=()):
    """Screen actual assertions/requests in their field role and sentence context."""
    if text is None:
        return
    saved, editorial, manual = _frozen_numbers(snapshot)
    for sentence in _sentences(text):
        for match in CERTAINTY.finditer(sentence):
            if not _negated(sentence, match.start()):
                reject(snapshot, path, "claim.unsupported_certainty",
                       "不能将推测表述为已确诊、已排除或直接换件", sentence,
                       "ANALYSIS_UNSUPPORTED_CERTAINTY")
        for match in OPERATION.finditer(sentence):
            if _negated(sentence, match.start()):
                continue
            if (snapshot.get("output_contract_version") in {C16_VERSION, CURRENT_VERSION}
                    and match.group() == "维修"
                    and re.match(r"(?:人员|技师|机构|单位|部门|车间|站|手册)",
                                 sentence[match.end():])):
                # A professional or document noun is not a request to repair.
                # The remainder of the handoff is still screened for actions.
                continue
            if role == "safety" and sentence.startswith("引用冻结摘录") and any(
                    (excerpt["id"] in source_ids and excerpt["kind"] == "local_manual"
                     and (quote := excerpt["text"].strip().rstrip("。"))
                     and (start := sentence.find(quote)) >= 0
                     and start <= match.start() < start + len(quote))
                    for excerpt in snapshot["source_context"]["excerpts"]):
                # Exact attributed manual quotation is provenance, not a
                # model-authored request to perform it. New text outside the
                # quoted span remains subject to the operation gate.
                continue
            local = sentence[max(0, match.start() - 24):match.start()]
            # A directive in a preceding comma clause must not turn a later
            # hazard description into an instruction to perform that action.
            directive_clause = re.split(r"[，,：:]", local)[-1]
            explicit_new_test = bool(NEW_TEST.fullmatch(match.group()))
            record_mention = role == "record" and question_ids and RECORD_INTENT.search(local) and (
                "是否" in sentence[match.end():match.end() + 12] or "结果" in sentence or "记录" in sentence)
            if record_mention and not explicit_new_test and not re.search(r"请|应|必须|进行|实施|开展", local[-10:]):
                continue
            if (explicit_new_test or (DIRECTIVE.search(directive_clause) and not record_mention)
                    or role in {"record", "handoff"} and not record_mention):
                reject(snapshot, path, "text.unlisted_operation",
                       "新现场技术操作必须使用冻结受控 action_id；题目引用只授权补记录", sentence,
                       "ANALYSIS_UNSUPPORTED_OPERATION")
        for match in NUMBER.finditer(sentence):
            unit = re.sub(r"[·.\s]", "", match.group(3)).lower()
            quantities = {(Decimal(part), unit) for part in (match.group(1), match.group(2)) if part is not None}
            # Numeric provenance is per measurement, not per whole sentence:
            # a saved pressure and an editorial bandwidth may be explained
            # together without turning the saved reading into a limit.
            local_clause = re.split(r"[，,]", sentence[:match.start()])[-1] + match.group() + (
                re.split(r"[，,]", sentence[match.end():])[0])
            # A structured record request may repeat a frozen question's limit
            # as a *past-result* question, never as permission to perform it.
            if (role == "record" and RECORD_INTENT.search(sentence) and "是否" in sentence
                    and _recorded_question_limit(snapshot, quantities, question_ids)):
                continue
            if quantities <= editorial:
                if not EDITORIAL_LABEL.search(sentence) or any(
                        not _negated(sentence, misuse.start())
                        for misuse in EDITORIAL_AS_STANDARD.finditer(sentence)):
                    reject(snapshot, path, "number.editorial_context",
                           "演示规则须就地标明性质，且不能作为厂家标准或操作授权", sentence,
                           "ANALYSIS_UNSUPPORTED_PARAMETER")
                continue
            if quantities <= saved and not re.search(
                    r"加压至|加压到|控制在|设置为|设定为|不得超过|不能超过|必须达到|应达到|上限|限值|扭矩",
                    local_clause):
                continue
            if LIMIT.search(local_clause):
                supported = bool(source_ids) and all(set(source_ids) & manual.get(q, set()) for q in quantities)
                if role == "safety" and supported and re.search(r"不得|不能|禁止|不应", sentence) and not DIRECTIVE.search(sentence):
                    continue
                reject(snapshot, path, "number.operation_limit",
                       "数值限制不能脱离适用手册来源或变成执行授权", sentence,
                       "ANALYSIS_UNSUPPORTED_PARAMETER")
            if quantities <= saved:
                continue
            if source_ids and all(set(source_ids) & manual.get(q, set()) for q in quantities):
                continue
            reject(snapshot, path, "number.provenance",
                   "数值须来自冻结观察、派生结果、明示演示规则或适用摘录", sentence,
                   "ANALYSIS_UNSUPPORTED_PARAMETER")


def _refs(snapshot, path, *, facts=(), sources=(), missing=()):
    legacy._refs(snapshot, path, facts, sources, missing)


def _direction(snapshot, item, path):
    _refs(snapshot, path, facts=item["basis_observation_ids"], sources=item["source_ids"])
    counters = item.get("counter_observation_ids", [])
    if counters:
        _refs(snapshot, path + ".counter_observation_ids", facts=counters)
        if set(counters) & set(item["basis_observation_ids"]):
            reject(snapshot, path + ".counter_observation_ids", "direction.counter_distinct",
                   "同一事实不能同时作为本方向的支持与反证")
    if not item["basis_observation_ids"]:
        reject(snapshot, path + ".basis_observation_ids", "direction.fact_required",
               "可能方向至少引用一条当前有效观察")
    if item["type"] != "observed_pattern":
        reject(snapshot, path + ".type", "direction.causal_source_missing",
               "当前摘录不支持发布技术因果判断")
    facts = {entry["id"]: entry for entry in snapshot["observations"]}
    for sid in item["source_ids"]:
        related = [rule for rule in snapshot.get("action_catalog", {}).get("actions", {}).values()
                   if action_case_applicable(rule, snapshot.get("vehicle", {})) and
                   sid in rule.get("explanation_excerpt_ids", rule.get("required_excerpt_ids", []))]
        if not related or not any(
                facts[fid]["question_id"] in rule["required_question_options"]
                for rule in related for fid in item["basis_observation_ids"]):
            reject(snapshot, path + ".source_ids", "source.explanation_scope",
                   "该摘录不支持本方向所引用事实的技术解释", sid,
                   "ANALYSIS_SOURCE_APPLICABILITY_UNCONFIRMED")
    known = {entry["id"] for entry in snapshot.get("editorial_thresholds", [])}
    ids = item["editorial_rule_ids"]
    if len(ids) != len(set(ids)) or not set(ids) <= known:
        reject(snapshot, path + ".editorial_rule_ids", "reference.editorial_rule",
               "演示规则 ID 必须存在于本次冻结快照", ids)
    _text(snapshot, path + ".title", item["title"], role="analysis", source_ids=item["source_ids"])
    _text(snapshot, path + ".limit", item["limit"], role="analysis", source_ids=item["source_ids"])


def _step(snapshot, item, path):
    if item["type"] == "controlled":
        return legacy._controlled(snapshot, item, path)
    facts, missing = item["basis_observation_ids"], item["missing_question_ids"]
    _refs(snapshot, path, facts=facts, sources=item.get("source_ids", []), missing=missing)
    if not facts and not missing:
        reject(snapshot, path, "step.basis_required", "补记录或交接须引用有效事实或缺项")
    if item["type"] == "record":
        qids = item["question_ids"]
        available = {fact["question_id"] for fact in snapshot["observations"]} | {
            target["question_id"] for target in snapshot.get("unresolved_questions", [])}
        if len(qids) != len(set(qids)) or not set(qids) <= available:
            reject(snapshot, path + ".question_ids", "reference.question",
                   "只能导航本次冻结的已有问题", qids, "ANALYSIS_INVALID_REFERENCE")
        if snapshot.get("output_contract_version") == CURRENT_VERSION:
            unresolved = {entry["question_id"] for entry in snapshot.get("unresolved_questions", [])}
            answered = {fact["question_id"] for fact in snapshot["observations"]} - unresolved
            if set(qids) & answered and not item.get("recheck_reason"):
                reject(snapshot, path + ".recheck_reason", "record.recheck_reason",
                       "已保存的有效结果只有说明具体复核原因后才能要求重查")
        _text(snapshot, path + ".request", item["request"], role="record", question_ids=qids)
        _text(snapshot, path + ".reason", item["reason"], role="analysis")
        if item.get("recheck_reason"):
            _text(snapshot, path + ".recheck_reason", item["recheck_reason"], role="analysis")
        return {"kind": "record", "action": item["request"], "reason": item["reason"],
                "recheck_reason": item.get("recheck_reason"),
                "question_ids": qids, "basis_observation_ids": facts,
                "missing_question_ids": missing, "source_ids": []}
    _text(snapshot, path + ".action", item["action"], role="handoff", source_ids=item["source_ids"])
    _text(snapshot, path + ".reason", item["reason"], role="analysis", source_ids=item["source_ids"])
    # A narrow air-hose excerpt cannot support an entire cross-area handoff.
    facts_by_id = {fact["id"]: fact for fact in snapshot["observations"]}
    for source_id in item["source_ids"]:
        scoped_areas = {legacy.AREA_PREFIX.get(qid.split("-")[0])
                        for rule in snapshot.get("action_catalog", {}).get("actions", {}).values()
                        if source_id in rule.get("required_excerpt_ids", [])
                        for qid in rule.get("required_question_options", {})}
        if scoped_areas and any(legacy.AREA_PREFIX.get(facts_by_id[fid]["question_id"].split("-")[0])
                                not in scoped_areas for fid in facts):
            reject(snapshot, path + ".source_ids", "source.applicability_unconfirmed",
                   "该摘录不能作为跨区域交接内容的整体资料依据", source_id,
                   "ANALYSIS_SOURCE_APPLICABILITY_UNCONFIRMED")
    return {"kind": "handoff", "action": item["action"], "reason": item["reason"],
            "basis_observation_ids": facts, "missing_question_ids": missing,
            "source_ids": item["source_ids"]}


def _reason(exc, path):
    detail = exc.details or {}
    return {"field_path": detail.get("field_path", path),
            "rule_id": detail.get("rule_id", exc.code), "reason": exc.message[:160]}


def _independent(snapshot, proposal, rejected, kept_direction_indexes, kept_step_indexes):
    """Fail closed on explicit dependency or a necessary discarded safeguard."""
    remaining = [proposal["summary"], proposal["uncertainty"], proposal.get("safety_notice") or "",
                 *proposal["unconfirmed_directions"]]
    remaining += [value for index, item in enumerate(proposal["supported_directions"])
                  if index in kept_direction_indexes
                  for value in (item["title"], item["limit"])]
    remaining += [value for index, item in enumerate(proposal["steps"])
                  if index in kept_step_indexes
                  for key in ("request", "action", "reason") if (value := item.get(key))]
    text = " ".join(remaining)
    for failure in rejected:
        path = failure["field_path"]
        if path.startswith("retest_plan"):
            plan = proposal.get("retest_plan") or ""
            if re.search(r"安全|停止|不得|禁止|不应|必须|前提|才能|应先|上限|限值", plan):
                reject(snapshot, path, "publication.safety_dependency",
                       "被拒绝方案含可能必要的安全限制，不能单独移除")
            if re.search(r"复检(?:后|结果|证明)|复测(?:后|结果|证明)|新(?:采集|测量).{0,12}(?:后|结果)", text):
                reject(snapshot, path, "publication.content_dependency",
                       "保留内容依赖未获支持的复检结果")
            continue
        match = re.match(r"(steps|supported_directions)\[(\d+)\]", path)
        if not match:
            reject(snapshot, path, "publication.global_dependency",
                   "无法安全隔离不合格的全局说明")
        item = proposal[match.group(1)][int(match.group(2))]
        markers = [item["action_id"]] if item.get("action_id") else (
            [item["title"]] if item.get("title") else item.get("question_ids", []))
        global_text = " ".join([proposal["summary"], proposal["uncertainty"],
                                proposal.get("safety_notice") or "", *proposal["unconfirmed_directions"]])
        if any(marker and re.search(
                rf"(?:待|完成|执行|依据|根据).{{0,14}}{re.escape(marker)}.{{0,16}}(?:后|结果|证明|才能)|"
                rf"{re.escape(marker)}.{{0,12}}(?:已完成|已证明|后才能)", global_text)
               for marker in markers):
            reject(snapshot, path, "publication.content_dependency",
                   "整体说明仍依赖未通过的方向或步骤")


def assemble(snapshot, raw):
    version = snapshot.get("output_contract_version")
    if version == CURRENT_VERSION:
        proposal = CaseAdviceProposalV7.model_validate(raw).model_dump(mode="json")
        proposal.update(safety_notice=None, safety_source_ids=[], retest_plan=None)
    elif version == C16_VERSION:
        proposal = CaseAdviceProposalV6.model_validate(raw).model_dump(mode="json")
        proposal.update(safety_notice=None, safety_source_ids=[], retest_plan=None)
    elif version == VERSION:
        proposal = CaseAdviceProposalV5.model_validate(raw).model_dump(mode="json")
    else:
        reject(snapshot, "output_contract_version", "contract.known", "未知输出契约", version)
    _refs(snapshot, "safety_notice", sources=proposal["safety_source_ids"])
    for field in ("summary", "uncertainty", "safety_notice"):
        _text(snapshot, field, proposal[field], role="safety" if field == "safety_notice" else "analysis",
              source_ids=proposal["safety_source_ids"] if field == "safety_notice" else ())
    for index, text in enumerate(proposal["unconfirmed_directions"]):
        _text(snapshot, f"unconfirmed_directions[{index}]", text, role="analysis")
    rejected = []
    retest = proposal["retest_plan"]
    if retest is not None:
        try:
            _text(snapshot, "retest_plan", retest, role="retest")
        except DomainError as exc:
            rejected.append(_reason(exc, "retest_plan"))
            retest = None
    directions, steps = [], []
    kept_direction_indexes, kept_step_indexes = set(), set()
    for index, item in enumerate(proposal["supported_directions"]):
        path = f"supported_directions[{index}]"
        try:
            _direction(snapshot, item, path)
            directions.append(item)
            kept_direction_indexes.add(index)
        except DomainError as exc:
            rejected.append(_reason(exc, path))
    for index, item in enumerate(proposal["steps"]):
        path = f"steps[{index}]"
        try:
            steps.append(_step(snapshot, item, path))
            kept_step_indexes.add(index)
        except DomainError as exc:
            rejected.append(_reason(exc, path))
    if rejected:
        _independent(snapshot, proposal, rejected, kept_direction_indexes, kept_step_indexes)
    if not directions and not steps:
        reject(snapshot, "steps", "publication.empty",
               "没有可独立展示的合格分析方向或建议")
    result = {key: proposal[key] for key in
              ("summary", "unconfirmed_directions", "uncertainty", "safety_notice")}
    result.update(supported_directions=directions, steps=steps, retest_plan=retest,
                  publication={"contract_version": version,
                               "state": "partial" if rejected else "complete",
                               "rejected_sections": rejected,
                               "safety_source_ids": proposal["safety_source_ids"]})
    return validate(snapshot, result)


def validate(snapshot, content):
    """Publication shape/invariants only; prose was checked once during assemble."""
    model = PublishedAdviceV7 if snapshot.get("output_contract_version") == CURRENT_VERSION else PublishedAdviceV5
    value = model.model_validate(content).model_dump(mode="json")
    pub = value["publication"]
    if (pub.get("contract_version") != snapshot.get("output_contract_version")
            or pub.get("state") not in {"complete", "partial"}
            or (pub["state"] == "complete") != (not pub.get("rejected_sections"))):
        reject(snapshot, "publication", "publication.state", "发布状态须与未通过项目一致")
    for item in value["steps"]:
        if item["action_id"]:
            rule = snapshot.get("action_catalog", {}).get("actions", {}).get(item["action_id"])
            if rule is None or any(item.get(key) != rule.get(key) for key in
                                   ("kind", "action", "prerequisites", "retest", "stop_condition")) or (
                                       item["source_ids"] != rule["required_excerpt_ids"]):
                reject(snapshot, "steps", "publication.controlled_text",
                       "受控操作只能由同一冻结清单确定")
    return value
