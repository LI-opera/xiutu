"""C09 section boundaries using frozen synthetic data; no network/model calls."""

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.case_analysis import CaseAdviceProposalV4
from app.domain.policies import DomainError
from app.legacy_execution.case_analysis import assemble_proposal, proposal_schema, substitute_advice, validate_advice
from app.services.case_analysis_read_service import CaseAnalysisReadService
from app.topics import dkvb_b02
from test_case_analysis_c07 import frozen


def snapshot():
    value = frozen()
    value["output_contract_version"] = "case-advice-proposal-c09-v1"
    value["editorial_thresholds"] = [
        {"question_id": "PRS-04", "id": "static_delta_max", "value": 30,
         "unit": "hPa", "kind": "editorial_demo", "source_id": "EDITORIAL_DEMO"},
        {"question_id": "PRS-11", "id": "persistent_gap", "value": 250,
         "unit": "hPa", "kind": "editorial_demo", "source_id": "EDITORIAL_DEMO"},
        {"question_id": "PRS-11", "id": "follow_gap_max", "value": 150,
         "unit": "hPa", "kind": "editorial_demo", "source_id": "EDITORIAL_DEMO"}]
    return value


def proposal():
    return {"summary": "模拟病例记录了接头未完全座合及静态压力 1000 hPa，不能据此确诊。",
            "supported_directions": [{"type": "observed_pattern", "title": "已记录的接头异常值得复核",
                "basis_observation_ids": ["air-fact"], "source_ids": [],
                "limit": "仅为观察所示方向，尚无泄漏结论。"}],
            "unconfirmed_directions": ["压力信号仍需核对。"],
            "steps": [{"type": "controlled", "action_id": "CHECK_CHARGE_AIR_HOSE_SEATING_LEAK",
                       "basis_observation_ids": ["air-fact"]},
                      {"type": "record", "question_ids": ["PRS-02"],
                       "request": "补充保存这道题的实际结果或未执行原因。",
                       "reason": "原始静态记录缺失。", "missing_question_ids": ["PRS-02"]}],
            "retest_plan": "仅实际处理后开启独立复检；当前没有维修后事实。",
            "uncertainty": "30 hPa 只是演示带宽，不是厂家标准。",
            "safety_notice": "synthetic DEMO，禁止拆卸或加压；条件不足时交接。",
            "safety_source_ids": []}


def test_direction_record_and_frozen_controlled_action():
    value = snapshot()
    schema = proposal_schema(value)
    assert schema["title"].startswith("case-advice-proposal-c09-v1")
    result = assemble_proposal(value, proposal())
    assert result["publication"]["state"] == "complete"
    assert result["supported_directions"][0]["type"] == "observed_pattern"
    assert result["steps"][0]["source_ids"] == ["C01-SRC-CHARGE-AIR-P1"]
    assert result["steps"][1]["kind"] == "record"
    assert result["steps"][1]["question_ids"] == ["PRS-02"]
    assert validate_advice(value, result)["publication"]["state"] == "complete"


def test_question_title_is_navigation_not_execution_but_free_pressure_action_rejected():
    value = snapshot()
    value["unresolved_questions"].append({"question_id": "AIR-14", "name": "加压过程是否遵守最大0.5 bar"})
    good = proposal()
    good["steps"][1].update(question_ids=["AIR-14"], missing_question_ids=["AIR-14"])
    good["steps"][1]["request"] = "补充记录 AIR-14（加压过程是否遵守最大 0.5 bar）的实际情况或未执行原因。"
    assert assemble_proposal(value, good)["steps"][1]["question_ids"] == ["AIR-14"]
    bad = deepcopy(good)
    bad["steps"][1]["request"] = "请对增压空气管路加压检漏。"
    with pytest.raises(DomainError) as error:
        assemble_proposal(value, bad)
    assert error.value.details["field_path"] == "steps[1].request"
    bad["steps"][1]["request"] = "对增压空气管路加压检漏。"
    with pytest.raises(DomainError):
        assemble_proposal(value, bad)
    bad = deepcopy(good)
    bad["steps"][1] = {"type": "handoff", "action": "交由专业人员加压检漏。",
                       "reason": "当前条件不足。", "missing_question_ids": ["AIR-14"]}
    with pytest.raises(DomainError):
        assemble_proposal(value, bad)


def test_partial_never_silently_claims_complete_and_global_contamination_fails():
    value = snapshot()
    bad = proposal()
    bad["steps"][1]["question_ids"] = ["FAKE"]
    result = assemble_proposal(value, bad)
    assert result["publication"]["state"] == "partial"
    assert result["publication"]["rejected_sections"]
    contaminated = deepcopy(bad)
    contaminated["safety_notice"] = "建议加压至 2 bar。"
    with pytest.raises(DomainError):
        assemble_proposal(value, contaminated)
    contaminated["safety_notice"] = proposal()["safety_notice"]
    contaminated["retest_plan"] = "可在相同负荷条件下重新采集压力帧。"
    result = assemble_proposal(value, contaminated)
    assert result["publication"]["state"] == "partial"
    assert result["retest_plan"] is None
    assert {item["field_path"] for item in result["publication"]["rejected_sections"]} == {
        "steps[1].question_ids", "retest_plan"}


def test_no_unsupported_cause_or_certain_repair():
    value = snapshot()
    bad = proposal()
    bad["supported_directions"][0]["type"] = "technical_cause"
    result = assemble_proposal(value, bad)
    assert result["publication"]["state"] == "partial"
    assert result["publication"]["rejected_sections"][0]["rule_id"] == "direction.causal_source_missing"
    bad = proposal()
    bad["summary"] = "目前不能确诊，但已确定需要更换涡轮。"
    with pytest.raises(DomainError) as error:
        assemble_proposal(value, bad)
    assert error.value.details["rule_id"] == "text.unsupported_certainty"


def test_numeric_provenance_and_safety_source_not_operation_permission():
    value = snapshot()
    labeled = proposal()
    labeled["uncertainty"] = "PRS-11 的 250/150 hPa 仅为专题演示阈值，不是厂家标准。"
    assert assemble_proposal(value, labeled)["publication"]["state"] == "complete"
    bad = proposal()
    bad["uncertainty"] = "30 hPa 是厂家诊断标准。"
    with pytest.raises(DomainError):
        assemble_proposal(value, bad)
    bad = proposal()
    bad["safety_notice"] = "压力不得超过 0.5 bar。"
    with pytest.raises(DomainError):
        assemble_proposal(value, bad)
    bad["safety_source_ids"] = ["C01-SRC-CHARGE-AIR-P1"]
    with pytest.raises(DomainError):
        assemble_proposal(value, bad)
    bad["safety_source_ids"] = ["C01-SRC-CHARGE-AIR-P5"]
    assert assemble_proposal(value, bad)["publication"]["state"] == "complete"
    bad["safety_notice"] = "请加压至 0.5 bar。"
    with pytest.raises(DomainError):
        assemble_proposal(value, bad)


def test_extra_controlled_fields_and_missing_proposal_text_rejected():
    bad = proposal()
    bad["steps"][0]["source_ids"] = ["C01-SRC-CHARGE-AIR-P1"]
    with pytest.raises(ValidationError):
        CaseAdviceProposalV4.model_validate(bad)


def test_substitute_uses_same_c09_frozen_publication_path():
    value = snapshot()
    value["synthesis"] = {"unavailable": [], "missing_question_ids": ["PRS-02"], "conflicts": []}
    result = substitute_advice(value)
    assert result["publication"]["state"] == "complete"
    assert result["steps"][-1]["kind"] == "record"
    bad = proposal()
    del bad["steps"][1]["request"]
    with pytest.raises(ValidationError):
        CaseAdviceProposalV4.model_validate(bad)


def test_fixed_partial_stub_rejects_unlisted_action_but_keeps_independent_analysis(monkeypatch):
    value = snapshot()
    value["fault_description"] = "【C09-PARTIAL-STUB-ONLY · 分层发布固定测试】全部为模拟观察。"
    monkeypatch.setenv("APP_MODE", "test")
    result = substitute_advice(value)
    assert result["publication"]["state"] == "partial"
    assert result["publication"]["rejected_sections"] == [{
        "field_path": "steps[0].action_id", "rule_id": "action.known",
        "reason": "操作必须来自本次冻结清单"}]
    assert result["supported_directions"][0]["basis_observation_ids"] == ["air-fact"]
    assert result["steps"] == []
    assert validate_advice(value, result) == result
    monkeypatch.setenv("APP_MODE", "dev")
    assert substitute_advice(value)["publication"]["state"] == "complete"


def test_published_c09_result_is_stale_after_a_revision_change_without_reanalysis():
    value = snapshot()
    value["synthesis"] = {"missing_question_ids": [], "unavailable": []}
    value["plan"] = {"rounds": []}
    content = assemble_proposal(value, proposal())
    row = {"id": uuid4(), "case_id": uuid4(), "run_id": uuid4(), "input_revision": 42,
           "topic_hash": "frozen-topic", "status": "current", "snapshot_json": value,
           "mode": "stub", "provider": "model_substitute", "model": "test",
           "prompt_version": "dkvb-c09-v1", "allowed_scope": "supplement_or_handoff",
           "content_json": content, "error_code": None, "created_at": datetime.now(timezone.utc)}
    case = {"revision": 43, "intake_snapshot": {"topic_binding": {"content_hash": "frozen-topic"},
                                               "topic_plan": {"rounds": []}}}
    topic, _ = dkvb_b02.catalog()
    current = {"topic": topic, "observations": [], "view": {"derived": {}}}
    result = CaseAnalysisReadService._body(None, row, {"status": "succeeded", "error_json": None}, case, current)
    assert result["status"] == "stale"
    assert result["stale"] is True
    assert result["content"] == content
