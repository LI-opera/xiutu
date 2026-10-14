"""C19 checks shape and navigation data, not AI technical conclusions."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.services.case_analysis_context import OUTPUT_CONTRACT_VERSION, PROMPT_VERSION
from app.legacy_execution.case_analysis import (assemble_proposal, model_payload,
                                                proposal_instruction, proposal_schema,
                                                validate_advice)
from app.services.case_analysis_projection import _conditional_question_context, _gate


def frozen():
    return {
        "output_contract_version": "case-advice-open-c19-v1",
        "prompt_version": "dkvb-c19-v1", "allowed_scope": "supplement_or_handoff",
        "source_context": {"version": "test", "hash": "test", "boundary": "DEMO",
                           "excerpts": [{"id": "P1", "text": "摘录", "source_ref": "manual",
                                         "asset_ids": []}], "missing_body_source_refs": []},
        "observations": [{"id": "fact-1", "question_id": "AIR-07", "question": "AIR-07 · 接头",
                          "note": "测试剧本模拟，非用户实测", "source_refs": []}],
        "synthesis": {"facts": [], "issues": [], "missing_question_ids": []},
        "question_catalog": [{"id": "AIR-07", "title": "接头", "answer_kind": "single"}],
        "action_catalog": {"actions": {}},
    }


def proposal():
    return {
        "summary": "根据接头现象，可能存在连接处问题；执行器与基本设置前提仍需现场核对。",
        "directions": [{"title": "接头连接异常可能影响增压", "explanation": "并非已经确诊。",
                        "basis_observation_ids": ["fact-1"], "source_ids": ["P1"]}],
        "missing": [{"question_id": "AIR-07", "missing": "补充卡箍位置",
                     "reason": "影响对连接状态的判断"}],
        "steps": [{"kind": "repair", "action": "在满足现场条件后处理接头并复核。",
                   "question_ids": ["AIR-07"], "basis_observation_ids": ["fact-1"],
                   "source_ids": ["P1"]}],
        "precautions": [], "verification": "处理后另行记录复检。",
    }


def test_open_path_has_no_action_or_content_approval():
    snapshot = frozen()
    assert proposal_schema(snapshot)["title"] == "case-advice-open-c19-v1"
    assert "action_id" not in str(proposal_schema(snapshot))
    assert "action_catalog" not in model_payload(snapshot)
    assert "allowed_scope" not in model_payload(snapshot)
    assert "不需要 action_id" in proposal_instruction(snapshot)
    result = assemble_proposal(snapshot, proposal())
    assert result["steps"][0]["action"].startswith("在满足")
    assert result["publication"] == {"contract_version": "case-advice-open-c19-v1"}
    assert validate_advice(snapshot, result) == result


def test_v2_prompt_guides_optional_checks_without_changing_v1_or_contract():
    old = frozen()
    old_instruction = proposal_instruction(old)
    current = deepcopy(old)
    current["prompt_version"] = "dkvb-c19-v2"
    instruction = proposal_instruction(current)
    assert PROMPT_VERSION == "dkvb-c19-v5"
    assert instruction.startswith(old_instruction)
    for phrase in ("补充检查是可选的判断手段", "不可见", "未执行", "无法取得",
                   "新检查与原记录的区别", "设备与安全前提", "先给针对性定位方法",
                   "若检查发现", "摘要与步骤次序一致", "不机械复用资料中的演示病例结局"):
        assert phrase in instruction
        assert phrase not in old_instruction
    assert proposal_schema(current) == proposal_schema(old)


def test_v3_contract_separates_current_steps_and_conditional_branches():
    old = frozen()
    current = deepcopy(old)
    current["prompt_version"] = "dkvb-c19-v3"
    current["output_contract_version"] = OUTPUT_CONTRACT_VERSION
    instruction = proposal_instruction(current)
    for phrase in ("conditional_branches", "trigger", "不同接头结构", "未满足条件不可执行",
                   "摘要所述当前任务必须与 steps 一致"):
        assert phrase in instruction
    assert "conditional_branches" not in proposal_schema(old)["properties"]
    assert "conditional_branches" in proposal_schema(current)["properties"]
    raw = proposal()
    raw["steps"] = [{"kind": "check", "action": "定位检查", "source_ids": ["P1"]}]
    raw["conditional_branches"] = [{"trigger": "检查确认特定结构的连接异常",
                                    "steps": [{"kind": "repair", "action": "按适用结构处理",
                                               "source_ids": ["P1"]}]}]
    result = assemble_proposal(current, raw)
    assert result["steps"][0]["kind"] == "check"
    assert result["conditional_branches"][0]["trigger"] == "检查确认特定结构的连接异常"
    assert result["publication"]["contract_version"] == OUTPUT_CONTRACT_VERSION
    assert validate_advice(current, result) == result
    with pytest.raises(ValidationError):
        assemble_proposal(old, raw)


def test_v4_adds_check_cleanup_and_consistent_fallback_only_for_future_requests():
    previous = frozen()
    previous["prompt_version"] = "dkvb-c19-v3"
    previous["output_contract_version"] = OUTPUT_CONTRACT_VERSION
    current = deepcopy(previous)
    current["prompt_version"] = "dkvb-c19-v4"
    old_instruction = proposal_instruction(previous)
    new_instruction = proposal_instruction(current)
    assert new_instruction.startswith(old_instruction)
    for phrase in ("卸压", "恢复测试连接", "不代表已完成故障维修", "不要再次要求补做同一检查"):
        assert phrase in new_instruction
        assert phrase not in old_instruction
    assert proposal_schema(current) == proposal_schema(previous)


def test_v5_uses_whole_case_priority_without_area_anchor_or_new_content_gate():
    snapshot = frozen()
    snapshot.update(prompt_version=PROMPT_VERSION, output_contract_version=OUTPUT_CONTRACT_VERSION)
    snapshot["source_context"]["version"] = "air-reference-1.0-c19"
    text = proposal_instruction(snapshot)
    assert "先依据全病例已保存事实选择当前优先方向" in text
    assert "资料覆盖范围限制的是" in text
    assert "前提尚未满足的未答题不自动成为必须补做项目" in text
    assert "本次仅扩充气路" not in text
    assert "ACT-01" not in text  # No scenario-specific answer injected.
    raw = proposal()
    raw["summary"] = "优先核对执行器反馈，不以气路为主线。"
    result = assemble_proposal(snapshot, raw)
    assert validate_advice(snapshot, result)["summary"] == raw["summary"]


@pytest.mark.parametrize("actual,unmet", [("未发现响应", True), ("软管", False), ("未记录", True)])
def test_conditional_context_preserves_unanswered_state_and_existing_prerequisites(actual, unmet):
    requirement = {"ref": "AIR-15", "allowed": ["hose"], "label": "已定位"}
    topic = {"questions": [{"id": "AIR-16", "title": "泄漏证据强度",
                             "execution_conditions": {"requirements": [requirement]}},
                            {"id": "AIR-01", "title": "空滤"}]}
    blockers = [{"ref": "AIR-15", "actual": actual, "expected": ["hose"]}] if unmet else []
    projection = {"question_states": {"AIR-16": {"status": "unanswered", "condition_blockers": blockers}}}
    before = deepcopy(projection)
    result = _conditional_question_context(topic, projection)
    assert result == [{"question_id": "AIR-16", "question": "泄漏证据强度", "record_state": "not_recorded",
                       "execution_requirements": [requirement], "current_unmet_requirements": blockers}]
    assert projection == before
    snapshot = frozen()
    snapshot["prompt_version"] = PROMPT_VERSION
    snapshot["conditional_question_context"] = result
    assert model_payload(snapshot)["conditional_question_context"] == result
    projection["question_states"]["AIR-16"]["status"] = "saved"
    assert _conditional_question_context(topic, projection) == []


def test_bad_references_remain_model_text_not_publication_gates():
    raw = proposal()
    raw["missing"][0]["question_id"] = "NOT-A-QUESTION"
    raw["directions"][0]["source_ids"] = ["NOT-A-SOURCE"]
    raw["steps"][0]["basis_observation_ids"] = ["NOT-A-FACT"]
    assert assemble_proposal(frozen(), raw)["missing"][0]["question_id"] == "NOT-A-QUESTION"


def test_invalid_structure_still_fails_without_silent_repair():
    raw = proposal()
    raw["steps"][0]["action"] = 123
    with pytest.raises(ValidationError):
        assemble_proposal(frozen(), raw)
    raw = proposal()
    raw["steps"][0]["action_id"] = "OLD_CONTROLLED_ACTION"
    with pytest.raises(ValidationError):
        assemble_proposal(frozen(), raw)


def test_incomplete_checks_allow_c19_request_without_claiming_readiness():
    view = {
        "topic": {"questions": [{"id": "AIR-01", "title": "AIR-01 · 空滤壳",
                                 "answer_kind": "single_choice"}]},
        "observations": [],
        "plan": {"intake": {"safety_gate": "none"}},
        "view": {"ai_readiness": {"ready_for_first_advice": False},
                 "synthesis": {"missing_question_ids": ["AIR-01"]}},
    }
    gate = _gate(view)
    assert gate["allowed"] is True
    assert gate["missing_question_ids"] == ["AIR-01"]
    assert gate["missing_questions"][0]["target_question_id"] == "AIR-01"
    assert "未检查内容将作为未知" in gate["reason"]
    assert view["view"]["ai_readiness"]["ready_for_first_advice"] is False
    assert _gate(view, contract_version="case-advice-proposal-c17-v1")["allowed"] is False
    view["plan"]["intake"]["safety_gate"] = "stop_now"
    assert _gate(view)["allowed"] is False
