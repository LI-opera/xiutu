"""Owner-checked, read-only C15 response review. Never calls a model or publishes advice."""

import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import select

from scripts.wp15_workbench import STATE, TEST_TOKEN, environment
from app.domain.case_analysis import CaseAdviceProposalV5, CaseAdviceProposalV6
from app.domain.policies import DomainError
from app.infrastructure.orm import case_analyses
from app.infrastructure.uow import make_engine
from app.services import case_analysis_c14
from app.legacy_execution.case_analysis import assemble_proposal

CASE_ID = "1dd92a6c-c84e-41e5-bfa8-8676d8847342"
ANALYSIS_ID = "2063ccde-50e2-4b24-9514-ca6385dc39e2"
EXPECTED_SHA = "bcb3259c47b410d118815d6704c2b3f3fde4f8527d746e23c833c61379ff8c89"
PREVIEW = Path(__file__).resolve().parents[1] / ".local-data" / "c16-preview.md"


def retained():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    engine = make_engine(environment(state)["DATABASE_URL"])
    try:
        with httpx.Client(base_url="http://127.0.0.1:8215", trust_env=False, timeout=20) as client:
            login = client.post("/api/v2/auth/login", json={"token": TEST_TOKEN},
                                headers={"Origin": "http://localhost:5215"})
            login.raise_for_status()
            actor = UUID(login.json()["actor_id"])
            response = client.get(f"/api/v2/cases/{CASE_ID}/analyses/{ANALYSIS_ID}/diagnostic")
            response.raise_for_status()
            payload = response.json()
            assert payload["availability"] == "retained"
            diagnostic = payload["diagnostic"]
            assert not diagnostic["truncated"] and not diagnostic["credentials_redacted"]
            raw = diagnostic["raw_response"]
            assert hashlib.sha256(raw.encode("utf-8")).hexdigest() == diagnostic["sha256"] == EXPECTED_SHA
            with engine.connect() as conn:
                row = conn.execute(select(case_analyses).where(
                    case_analyses.c.id == UUID(ANALYSIS_ID),
                    case_analyses.c.case_id == UUID(CASE_ID),
                    case_analyses.c.owner_id == actor)).mappings().one()
                assert row["status"] == "failed" and row["mode"] == "real"
                assert row["input_revision"] == 60 and not row["content_json"]
                return row["snapshot_json"], json.loads(raw), diagnostic
    finally:
        engine.dispose()


def _issue(path, work):
    try:
        work()
    except DomainError as exc:
        detail = exc.details or {}
        return {"field_path": detail.get("field_path", path),
                "rule_id": detail.get("rule_id", exc.code),
                "actual_excerpt": str(detail.get("actual") or "")[:100]}
    except Exception as exc:
        return {"field_path": path, "uncheckable": type(exc).__name__}
    return None


def probes(snapshot, proposal):
    """Independent probes do not replace whole-publication dependency checking."""
    issues = []
    for key in ("summary", "uncertainty", "safety_notice", "retest_plan"):
        value = proposal.get(key)
        if not value:
            continue
        role = "safety" if key == "safety_notice" else "retest" if key == "retest_plan" else "analysis"
        for index, sentence in enumerate(case_analysis_c14._sentences(value)):
            issue = _issue(f"{key}[sentence:{index}]", lambda s=sentence, k=key, r=role:
                           case_analysis_c14._text(snapshot, k, s, role=r,
                               source_ids=proposal.get("safety_source_ids", []) if k == "safety_notice" else ()))
            if issue:
                issues.append(issue)
    for index, value in enumerate(proposal.get("unconfirmed_directions", [])):
        for part, sentence in enumerate(case_analysis_c14._sentences(value)):
            issue = _issue(f"unconfirmed_directions[{index}][sentence:{part}]",
                           lambda s=sentence, i=index:
                           case_analysis_c14._text(snapshot, f"unconfirmed_directions[{i}]", s, role="analysis"))
            if issue:
                issues.append(issue)
    for index, value in enumerate(proposal.get("supported_directions", [])):
        issue = _issue(f"supported_directions[{index}]", lambda v=value, i=index:
                       case_analysis_c14._direction(snapshot, v, f"supported_directions[{i}]"))
        if issue:
            issues.append(issue)
    for index, value in enumerate(proposal.get("steps", [])):
        issue = _issue(f"steps[{index}]", lambda v=value, i=index:
                       case_analysis_c14._step(snapshot, v, f"steps[{i}]"))
        if issue:
            issues.append(issue)
    return issues


def outcome(snapshot, proposal):
    try:
        result = assemble_proposal(snapshot, proposal)
        return {"state": result.get("publication", {}).get("state", "complete"),
                "directions": len(result["supported_directions"]), "steps": len(result["steps"]),
                "rejected": result.get("publication", {}).get("rejected_sections", [])}
    except DomainError as exc:
        detail = exc.details or {}
        return {"state": "rejected", "rule_id": detail.get("rule_id", exc.code),
                "field_path": detail.get("field_path"), "code": exc.code}


def safety_mapping(snapshot, proposal):
    """Identify, not rewrite, old model safety prose now owned by frozen actions."""
    cited = set(proposal.get("safety_source_ids", []))
    excerpts = {item["id"]: item for item in snapshot["source_context"]["excerpts"]}
    selected = {item["action_id"]: snapshot["action_catalog"]["actions"][item["action_id"]]
                for item in proposal.get("steps", []) if item.get("type") == "controlled"
                and item.get("action_id") in snapshot["action_catalog"]["actions"]}
    def norm(value):
        return re.sub(r"[\s。；，,!！:：]", "", value).lower()
    mapping = []
    for index, sentence in enumerate(case_analysis_c14._sentences(proposal.get("safety_notice") or "")):
        matches = []
        for sid in cited:
            excerpt = excerpts.get(sid)
            if not excerpt or excerpt["kind"] != "local_manual" or norm(sentence) not in norm(excerpt["text"]):
                continue
            for action_id, rule in selected.items():
                if sid not in rule["required_excerpt_ids"]:
                    continue
                numbers = {(m.group(1), m.group(3).lower())
                           for m in case_analysis_c14.NUMBER.finditer(sentence)}
                controlled = " ".join(rule.get(key, "") for key in
                                      ("action", "prerequisites", "retest", "stop_condition"))
                if all(part in controlled and unit in controlled for part, unit in numbers):
                    matches.append({"source_id": sid, "action_id": action_id})
        mapping.append({"field_path": f"safety_notice[sentence:{index}]", "frozen_mappings": matches})
    return mapping


def compatible_candidate(snapshot, proposal):
    mapping = safety_mapping(snapshot, proposal)
    if any(not item["frozen_mappings"] for item in mapping):
        return None, None, mapping, []
    revised = deepcopy(snapshot)
    revised["output_contract_version"] = "case-advice-proposal-c16-v1"
    revised["prompt_version"] = "dkvb-c16-v1"
    converted = deepcopy(proposal)
    omitted = [key for key in ("safety_notice", "safety_source_ids", "retest_plan") if key in converted]
    for key in omitted:
        converted.pop(key)
    candidate = CaseAdviceProposalV6.model_validate(converted).model_dump(mode="json")
    return revised, candidate, mapping, omitted


def compatible_evaluation(snapshot, proposal):
    revised, candidate, mapping, omitted = compatible_candidate(snapshot, proposal)
    if candidate is None:
        return {"state": "not_directly_verifiable", "reason": "旧安全说明存在未能映射到冻结资料和受控操作的内容",
                "safety_mapping": mapping}
    return {"conversion": [f"{key}: 旧提案字段不属于 C16 模型输入；安全/复检由冻结 action 装配"
                           for key in omitted],
            "safety_mapping": mapping,
            "outcome": outcome(revised, candidate)}


def _escape(value):
    return str(value).replace("<", "&lt;").replace(">", "&gt;")


def preview(snapshot, proposal, diagnostic):
    revised, candidate, mapping, omitted = compatible_candidate(snapshot, proposal)
    if candidate is None:
        raise RuntimeError("C16_PREVIEW_UNMAPPED_SAFETY")
    content = assemble_proposal(revised, candidate)
    facts = {item["id"]: item for item in snapshot["observations"]}
    sources = {item["id"]: item for item in snapshot["source_context"]["excerpts"]}
    parts = [
        "# C15 历史真实回复的离线验证预览",
        "",
        "> **不是新模型生成，未发布为正式病例建议。** 模拟病例，非实车事实；下列受控内容仅供理解冻结资料，不能在本预览中执行或记录为已维修。",
        "",
        f"- 病例：[{CASE_ID}](http://localhost:5215/workbench/{CASE_ID}) · 历史 revision 60 · 原分析 {ANALYSIS_ID} 保持 `failed`。",
        f"- 原响应 SHA-256：`{diagnostic['sha256']}`；完整、未截断。原契约 `case-advice-proposal-c14-v1` 整体拒绝；C16 兼容评估为 **{content['publication']['state']}**，不是 C16 原生模型输出。",
        "- 转换仅移除旧提案中的 `safety_notice`、`safety_source_ids`、`retest_plan`；前两者逐句映射到已引用的冻结手册与所选受控 action，后者原为 `null`。模型其余字句、事实 ID、来源 ID、action ID 原样保留。受控正文按旧冻结清单装配。",
        "",
        "## 1. 离线评估可独立保留的分析与指导",
        "",
        "### 模型原文：情况概述",
        "",
        _escape(content["summary"]), "",
        "### 模型原文：有依据的观察方向（非确诊）", "",
    ]
    for index, direction in enumerate(content["supported_directions"], 1):
        parts.extend([f"{index}. **{_escape(direction['title'])}** — {_escape(direction['limit'])}",
                      f"   事实：{', '.join(facts[fid]['question_id'] + '（' + fid + '）' for fid in direction['basis_observation_ids'])}；"
                      f"摘录：{', '.join(direction['source_ids']) or '无技术因果摘录，仅陈述已存观察'}。"])
    parts.extend(["", "### 模型原文：仍不能确认", ""])
    parts.extend(f"- {_escape(value)}" for value in content["unconfirmed_directions"])
    parts.extend(["", "### 按顺序的建议：标明内容归属", ""])
    for index, step in enumerate(content["steps"], 1):
        if step["action_id"]:
            parts.extend([f"{index}. **服务端从冻结 action `{step['action_id']}` 装配（模型只选 ID 与事实）**：{_escape(step['action'])}",
                          f"   前提：{_escape(step['prerequisites'])}",
                          f"   复检说明：{_escape(step['retest'])}",
                          f"   停止条件：{_escape(step['stop_condition'])}"])
        else:
            parts.append(f"{index}. **模型原文·{'补记录' if step['kind'] == 'record' else '交接'}**：{_escape(step['action'])} 原因：{_escape(step['reason'])}")
        parts.append(f"   事实：{', '.join(facts[fid]['question_id'] + '（' + fid + '）' for fid in step['basis_observation_ids']) or '无'}；"
                     f"资料：{', '.join(step['source_ids']) or '未援引手册正文'}。")
    parts.extend(["", "### 模型原文：不确定性", "", _escape(content["uncertainty"]), "",
                  "## 2. 未获正式发布的内容与原因", "",
                  "- **整份 C15 正式分析仍为 failed**：旧 C14 校验在全局 `safety_notice` 把 P1 手册前置检查的重述当作清单外操作；独立探针还把‘维修人员’这一交接对象误判为维修操作。",
                  "- 旧安全字段的 P1 检查提示及 P5 压力上限并非新的独立操作授权；本预览不把这些模型自由字句显示成可执行步骤。对应安全、操作前提及复检只显示上方**冻结清单的服务端内容**。",
                  "- 没有现场适用性核实、实际处理或处理后复检事实；因此不显示‘已修复’、复检通过或最终报告结论。离线兼容评估完整通过也不改变正式发布状态。",
                  "",
                  "<details><summary>受限诊断片段（默认折叠；拒绝内容，不是建议）</summary>", "",
                  "原拒绝：`safety_notice` / `text.unlisted_operation`。必要片段：‘进行测试或修理前，检查所有空气软管和管路的座合是否牢固以及是否泄漏’。",
                  "另一个旧规则误拦：`steps[3].action` 中‘交接给……维修人员’；该字段没有要求实施维修。完整原响应仍只在原受限诊断记录中。",
                  "", "</details>", "", "## 3. 冻结依据（仅供核对）", "",
                  "观察 ID 均来自本次 revision 60 的 59 条有效模拟事实；点击上方病例链接后可在原题查看。下列资料正文为原冻结摘录，不是模型撰写的维修手册。", ""])
    referenced = {sid for direction in content["supported_directions"] for sid in direction["source_ids"]}
    referenced.update(sid for step in content["steps"] for sid in step["source_ids"])
    for sid in sorted(referenced):
        item = sources[sid]
        parts.extend([f"<details><summary>{sid} · 手册 PDF 第 {item['page']} 页（展开查看冻结摘录）</summary>", "",
                      _escape(item["text"]), "", "</details>", ""])
    parts.extend(["图片仅供页面查看，模型未读取图片。", ""])
    PREVIEW.parent.mkdir(exist_ok=True)
    if PREVIEW.exists():
        raise RuntimeError("C16_PREVIEW_ALREADY_EXISTS")
    PREVIEW.write_text("\n".join(parts), encoding="utf-8")
    return {"preview_path": str(PREVIEW), "state": content["publication"]["state"],
            "directions": len(content["supported_directions"]), "steps": len(content["steps"]),
            "mapped_safety_sentences": len(mapping), "omitted_legacy_fields": omitted}


def main():
    snapshot, proposal, diagnostic = retained()
    parsed = CaseAdviceProposalV5.model_validate(proposal).model_dump(mode="json")
    excerpts = {item["id"]: item for item in snapshot["source_context"]["excerpts"]}
    safety_sentences = case_analysis_c14._sentences(proposal.get("safety_notice") or "")
    report = {
        "response_complete": not diagnostic["truncated"], "sha256": diagnostic["sha256"],
        "contract": snapshot["output_contract_version"], "scope": snapshot["allowed_scope"],
        "original": outcome(snapshot, proposal), "independent_issues": probes(snapshot, parsed),
        "compatible_evaluation": compatible_evaluation(snapshot, proposal),
        "safety_sources": proposal.get("safety_source_ids", []),
        "safety_sentence_sources": [
            {"sentence": index, "exact_frozen_excerpt_ids": [sid for sid in proposal.get("safety_source_ids", [])
              if sentence == excerpts[sid]["text"].strip().rstrip("。")],
             "contained_in_frozen_excerpt_ids": [sid for sid in proposal.get("safety_source_ids", [])
              if sentence in excerpts[sid]["text"]]}
            for index, sentence in enumerate(safety_sentences)],
        "direction_count": len(proposal.get("supported_directions", [])),
        "step_types": [item["type"] for item in proposal.get("steps", [])],
        "action_ids": [item.get("action_id") for item in proposal.get("steps", [])],
    }
    if "--write-preview" in sys.argv:
        report["preview"] = preview(snapshot, proposal, diagnostic)
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
