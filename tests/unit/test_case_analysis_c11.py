"""C11 frozen-provenance boundaries; artificial samples, never model calls."""

from copy import deepcopy

import pytest

from app.domain.policies import DomainError
from app.services.case_analysis_c09 import check_text
from app.legacy_execution.case_analysis import assemble_proposal
from test_case_analysis_c09 import proposal, snapshot


@pytest.mark.parametrize("text", [
    "静态 30 hPa 与 250/150 hPa 均为演示判别带宽，非手册限值。",
    "静态 30 hPa 与 250/150 hPa 均为演示判别带宽；非手册限值。",
    "30 hPa 为专题演示带宽。仅说明静态读数彼此一致。",
])
def test_frozen_editorial_caveat_may_be_in_adjacent_clause(text):
    check_text(snapshot(), "uncertainty", text, role="uncertainty")


def test_editorial_label_does_not_create_a_number_or_authorize_diagnosis():
    value = snapshot()
    for text in ("47 hPa 只是演示带宽，不是厂家标准。",
                 "30 hPa 是演示值，可作为实车诊断标准。",
                 "30 hPa 仅为演示值，可作为操作限值。",
                 "30 hPa 只是演示带宽；实际操作上限就是该数值。"):
        with pytest.raises(DomainError):
            check_text(value, "uncertainty", text, role="uncertainty")


def test_saved_measurement_and_sourced_prohibition_are_not_execution_permission():
    value = snapshot()
    check_text(value, "summary", "已保存静态压力 1000 hPa。", role="explanation")
    check_text(value, "safety_notice", "压力不得超过 0.5 bar。", role="safety",
               safety_sources=["C01-SRC-CHARGE-AIR-P5"])
    with pytest.raises(DomainError):
        check_text(value, "safety_notice", "压力不得超过 0.5 bar。", role="safety",
                   safety_sources=["C01-SRC-CHARGE-AIR-P1"])
    with pytest.raises(DomainError):
        check_text(value, "safety_notice", "请加压至 0.5 bar。", role="safety",
                   safety_sources=["C01-SRC-CHARGE-AIR-P5"])


def test_cited_safety_text_is_context_not_a_new_action():
    value = snapshot()
    good = ("引用冻结摘录：进行测试或修理前，检查所有空气软管和管路的座合是否牢固以及是否泄漏；"
            "因压力设定过高造成的损坏风险，压力不得超过 0.5 bar。"
            "以上为资料摘录提示，不代表已授权执行任何拆装、加压、维修或换件操作。")
    check_text(value, "safety_notice", good, role="safety",
               safety_sources=["C01-SRC-CHARGE-AIR-P1", "C01-SRC-CHARGE-AIR-P5"])
    for bad, ids in ((good.replace("不代表已授权执行", "已经授权执行"),
                      ["C01-SRC-CHARGE-AIR-P1", "C01-SRC-CHARGE-AIR-P5"]),
                     (good, ["C01-SRC-CHARGE-AIR-P5"]),
                     (good + "但应拆卸涡轮。",
                      ["C01-SRC-CHARGE-AIR-P1", "C01-SRC-CHARGE-AIR-P5"])):
        with pytest.raises(DomainError):
            check_text(value, "safety_notice", bad, role="safety", safety_sources=ids)


def test_record_existing_question_result_not_recast_as_pressure_instruction():
    value = snapshot()
    value["unresolved_questions"].append({"question_id": "AIR-14", "name": "加压过程是否遵守最大0.5 bar"})
    request = ("补充记录增压空气系统检漏相关结果：是否已按不超过 0.5 bar 的压力执行、"
               "泄漏响应出现的位置、以及泄漏证据强度。")
    check_text(value, "steps[0].request", request, role="record", record_question_ids=["AIR-14"])
    check_text(value, "steps[0].reason", "缺少检漏证据，不能确认泄漏。", role="record")
    without_source = deepcopy(value)
    without_source["source_context"]["excerpts"] = [entry for entry in value["source_context"]["excerpts"]
                                                   if entry["id"] != "C01-SRC-CHARGE-AIR-P5"]
    for frozen, qids, text in ((value, [], request), (without_source, ["AIR-14"], request),
                               (value, ["AIR-14"], "请按不超过 0.5 bar 的压力加压检漏。")):
        with pytest.raises(DomainError):
            check_text(frozen, "steps[0].request", text, role="record", record_question_ids=qids)


def test_unsupported_new_measurement_in_global_retest_plan_still_rejects():
    value = snapshot()
    text = "按同一工况重新采集三帧目标/实际压力，与旧记录对照。"
    with pytest.raises(DomainError) as error:
        check_text(value, "retest_plan", text, role="explanation")
    assert error.value.details["rule_id"] == "text.unsupported_operation"
    check_text(value, "retest_plan", "尚未重新采集压力；未有维修后复检记录。", role="explanation")


def test_independent_bad_section_is_partial_but_global_action_is_not():
    value = snapshot()
    bad_step = proposal()
    bad_step["steps"][1]["question_ids"] = ["UNKNOWN"]
    result = assemble_proposal(value, bad_step)
    assert result["publication"]["state"] == "partial"
    assert result["publication"]["rejected_sections"][0]["rule_id"] == "reference.question"
    contaminated = deepcopy(bad_step)
    contaminated["retest_plan"] = "按同一工况重新采集三帧压力。"
    result = assemble_proposal(value, contaminated)
    assert result["publication"]["state"] == "partial"
    assert result["retest_plan"] is None
    assert {item["field_path"] for item in result["publication"]["rejected_sections"]} == {
        "steps[1].question_ids", "retest_plan"}


def test_bad_fact_source_and_action_are_still_rejected():
    value = snapshot()
    for mutate in (
        lambda p: p["supported_directions"][0].update(basis_observation_ids=["not-a-frozen-fact"]),
        lambda p: p["supported_directions"][0].update(source_ids=["not-a-frozen-source"]),
        lambda p: p["steps"][0].update(action_id="not-a-frozen-action"),
    ):
        item = proposal()
        mutate(item)
        result = assemble_proposal(value, item)
        assert result["publication"]["state"] == "partial"
        assert result["publication"]["rejected_sections"]
