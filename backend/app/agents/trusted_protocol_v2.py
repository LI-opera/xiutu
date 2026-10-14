"""Immutable conservative protocol v2 for the bounded DKVB demo."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Literal

from pydantic import Field, model_validator

from app.domain.schemas import InputModel, PersistedText


class ProtocolField(InputModel):
    name: PersistedText = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    label: PersistedText = Field(min_length=1, max_length=100)
    kind: Literal["text", "select", "decimal"]
    required: bool = True
    options: list[PersistedText] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def bounded(self):
        if self.kind == "select" and not self.options:
            raise ValueError("Select protocol field requires options")
        if self.kind != "select" and self.options:
            raise ValueError("Only select fields may publish options")
        return self


class ProtocolOption(InputModel):
    option_id: PersistedText = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_.-]*$")
    label: PersistedText = Field(min_length=1, max_length=200)
    fields: list[ProtocolField] = Field(default_factory=list, max_length=24)


class ProtocolInput(InputModel):
    kind: Literal["choice"] = "choice"
    options: list[ProtocolOption] = Field(min_length=1, max_length=8)


class DemoMeasurementPreset(InputModel):
    id: PersistedText = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    label: PersistedText
    explanation: PersistedText
    synthetic: Literal[True] = True
    option_id: PersistedText | None = None
    fields: dict[PersistedText, PersistedText]


class ProtocolPresentation(InputModel):
    task_summary: PersistedText
    why_summary: PersistedText
    operation_steps: list[PersistedText] = Field(min_length=1, max_length=8)
    completion_explanation: PersistedText
    evidence_summary: PersistedText
    evidence_scope: PersistedText
    evidence_limitations: PersistedText
    progress_completed: list[PersistedText] = Field(default_factory=list, max_length=12)
    progress_current: PersistedText
    progress_remaining: list[PersistedText] = Field(default_factory=list, max_length=12)
    demo_measurement_presets: list[DemoMeasurementPreset] = Field(default_factory=list, max_length=6)
    task_title: PersistedText | None = None
    question: PersistedText | None = None
    record_summary: PersistedText | None = None
    outcome_preview: PersistedText | None = None
    evidence_kind: PersistedText | None = None
    progress_phase: PersistedText | None = None


class ProtocolCheck(InputModel):
    check_id: PersistedText = Field(min_length=1, max_length=64)
    current_stage: PersistedText = Field(min_length=1, max_length=64)
    input_schema: ProtocolInput
    evidence_refs: list[PersistedText] = Field(min_length=1, max_length=12)
    completion_rule: PersistedText = Field(min_length=1, max_length=64)
    presentation: ProtocolPresentation


class ProtocolTransition(InputModel):
    transition_id: PersistedText = Field(min_length=1, max_length=100)
    current_check_id: PersistedText = Field(min_length=1, max_length=64)
    result_value: PersistedText = Field(min_length=1, max_length=100)
    decision: Literal["next_check", "need_input", "handoff", "area_summary"]
    next_check_id: PersistedText | None = Field(default=None, max_length=64)
    reason: PersistedText | None = Field(default=None, max_length=800)
    terminal_code: PersistedText | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def shape(self):
        if self.decision in {"next_check", "need_input"} and not self.next_check_id:
            raise ValueError("Continuing transition requires next_check_id")
        if self.decision in {"handoff", "area_summary"} and self.next_check_id:
            raise ValueError("Terminal transition cannot publish a next check")
        if self.decision in {"handoff", "area_summary"} and not self.terminal_code:
            raise ValueError("Terminal transition requires a code")
        return self


class TrustedProtocol(InputModel):
    protocol_id: PersistedText = Field(min_length=1, max_length=100)
    version: PersistedText = Field(min_length=1, max_length=32)
    synthetic: Literal[True]
    formal_usable: Literal[False]
    applicable_vehicle_profile: dict[PersistedText, PersistedText | int]
    start_check_id: PersistedText
    checks: list[ProtocolCheck] = Field(min_length=1, max_length=16)
    transitions: list[ProtocolTransition] = Field(min_length=1, max_length=64)
    max_supplement_rounds: int = Field(default=1, ge=0, le=3)

    @model_validator(mode="after")
    def graph_is_complete(self):
        validate_protocol_package(self)
        return self


def validate_protocol_package(protocol: TrustedProtocol) -> None:
    checks = {item.check_id: item for item in protocol.checks}
    if len(checks) != len(protocol.checks) or protocol.start_check_id not in checks:
        raise ValueError("Protocol check identities are invalid")
    option_ids = [option.option_id for check in protocol.checks for option in check.input_schema.options]
    if len(option_ids) != len(set(option_ids)):
        raise ValueError("Protocol option ids must be globally unique")
    transition_ids = [item.transition_id for item in protocol.transitions]
    if len(transition_ids) != len(set(transition_ids)):
        raise ValueError("Duplicate transition id")
    by_check = defaultdict(list)
    for transition in protocol.transitions:
        if transition.current_check_id not in checks or (
                transition.next_check_id and transition.next_check_id not in checks):
            raise ValueError("Transition references unknown check")
        by_check[transition.current_check_id].append(transition)
    legacy_results = {
        "CHK-05": {"leak.localized", "leak.not_found", "leak.inconclusive", "unavailable"},
        "CHK-05-SUPPLEMENT": {"leak.localized", "leak.inconclusive", "unavailable"},
        "CHK-06": {"repair.completed", "repair.not_completed", "unavailable"},
        "CHK-07": {"retest.recovered", "retest.residual_underboost", "retest.same_leak",
                   "retest.symptom_elsewhere", "retest.insufficient", "unavailable"},
        "CHK-11": {"final.passed", "final.incomplete", "unavailable"},
    }
    for check in protocol.checks:
        expected = (legacy_results.get(check.check_id) if protocol.version.startswith("2.") else
                    ({option.option_id for option in check.input_schema.options} | {"unavailable"}))
        values = [item.result_value for item in by_check.get(check.check_id, [])]
        if len(values) != len(set(values)) or not expected.issubset(set(values)):
            raise ValueError(f"Every visible result requires one exit for {check.check_id}")
    reached, queue = set(), deque([protocol.start_check_id])
    while queue:
        current = queue.popleft()
        if current in reached:
            continue
        reached.add(current)
        queue.extend(item.next_check_id for item in by_check[current] if item.next_check_id)
    if reached != set(checks):
        raise ValueError("Protocol contains unreachable checks")


PROFILE = {"model": "虚拟探岳 DKVB 演示台架", "year": 2020,
           "engine_family": "EA888 Gen3B DEMO", "engine_code": "DKVB-DEMO"}


def field(name, label, kind="text", options=None, required=True):
    return ProtocolField(name=name, label=label, kind=kind, options=options or [], required=required)


LOCATOR_FIELDS = [field("leak_object_id", "发现泄漏的对象"), field("leak_location", "泄漏位置"),
    field("evidence_kind", "定位依据", "select", ["visual", "touch", "leak_spray", "ultrasound"])]
PRESSURE_FIELDS = [field("measurement_run_id", "负荷记录编号", required=False),
    *[field(f"{side}_{index}_hpa", f"第{index}帧{label}绝对压力（hPa）", "decimal")
      for index in range(1, 4) for side, label in (("target", "目标"), ("actual", "实际"))]]
RETEST_FIELDS = [field("retest_run_id", "复检记录编号"),
    field("leak_result", "局部泄漏复查", "select", ["not_found", "localized", "inconclusive"]),
    *[field(f"{side}_{index}_hpa", f"第{index}帧{label}绝对压力（hPa）", "decimal", required=False)
      for index in range(1, 4) for side, label in (("target", "目标"), ("actual", "实际"))],
    field("symptom", "原症状", "select", ["absent", "present"])]
FINAL_FIELDS = [field("final_retest_run_id", "最终复检记录编号", required=False),
    field("final_stage", "最终复检阶段", required=False),
    field("source_observation_id", "引用观察", required=False),
    *[field(f"final_{side}_{index}_hpa", f"最终第{index}帧{label}绝对压力（hPa）", "decimal", required=False)
      for index in range(1, 4) for side, label in (("target", "目标"), ("actual", "实际"))],
    field("symptom", "原症状", "select", ["absent", "present"]),
    field("p0299", "P0299复检", "select", ["absent", "present"]),
    field("repairs_rechecked", "已处理问题复核", "select", ["completed", "incomplete"]),
    field("conflict", "未解决冲突", "select", ["none", "present"])]


def presentation(task, why, steps, completion, completed, current, remaining, presets=None):
    return ProtocolPresentation(
        task_summary=task, why_summary=why, operation_steps=steps,
        completion_explanation=completion,
        evidence_summary="受控演示资料共同支持当前检查的方法、位置、工况和可记录结果。",
        evidence_scope="仅适用于虚拟探岳 DKVB / P0299 合成演示台架。",
        evidence_limitations="资料为 synthetic/DEMO、formal_usable=false；不能证明真实车辆状态或完整故障树。",
        progress_completed=completed, progress_current=current, progress_remaining=remaining,
        demo_measurement_presets=presets or [],
    )


def check(check_id, stage, options, refs, rule, display):
    return ProtocolCheck(check_id=check_id, current_stage=stage,
                         input_schema=ProtocolInput(options=options),
                         evidence_refs=refs, completion_rule=rule, presentation=display)


def transition(tid, current, result, decision, next_check=None, code=None, reason=None):
    return ProtocolTransition(transition_id=tid, current_check_id=current,
        result_value=result, decision=decision, next_check_id=next_check,
        terminal_code=code, reason=reason)


DKVB_DEMO_PROTOCOL = TrustedProtocol(
    protocol_id="dkvb-p0299-guided-demo", version="2.1.0", synthetic=True,
    formal_usable=False, applicable_vehicle_profile=PROFILE, start_check_id="CHK-05",
    checks=[
        check("CHK-05", "localized_leak_check", [
            ProtocolOption(option_id="leak.localized", label="增压空气系统已定位局部泄漏。", fields=LOCATOR_FIELDS),
            ProtocolOption(option_id="leak.not_found", label="增压空气系统未发现局部泄漏。"),
            ProtocolOption(option_id="leak.inconclusive", label="增压空气系统局部泄漏结果无法确定。")], ["S02-P5", "S02-P6"], "localized_leak_result",
            presentation("检查增压空气系统是否存在可定位漏点。", "先确认有没有明确漏点，后续处理和复检才有可追踪的起点。",
                ["确认演示台架处于安全、可观察状态。", "沿增压空气软管和接头检查可定位漏点。", "按实际观察选择结果并保存。"],
                "系统会根据实际观察进入模拟处理、补充一次定位观察或明确交接；不会把未发现漏点解释为系统正常。",
                [], "定位局部泄漏", ["模拟处理", "处理后复检", "最终复核", "演示小结"])),
        check("CHK-05-SUPPLEMENT", "localized_leak_evidence", [
            ProtocolOption(option_id="supplement.localized", label="增压空气系统定位证据已定位局部泄漏。", fields=LOCATOR_FIELDS),
            ProtocolOption(option_id="supplement.inconclusive", label="增压空气系统定位证据局部泄漏结果无法确定。")], ["S02-P5", "S02-P6"], "single_supplement",
            presentation("补充一次局部泄漏定位观察。", "上一步结果仍不确定，本次只补充泄漏对象、位置和定位方式。",
                ["重新确认可观察部位。", "补充泄漏对象、位置和定位依据。", "按实际结果保存；本步骤不会无限重复。"],
                "系统会进入模拟处理或给出待补工具与条件的交接说明。",
                ["初次定位观察"], "补充定位", ["模拟处理", "处理后复检", "最终复核", "演示小结"])),
        check("CHK-06", "after_air_repair", [
            ProtocolOption(option_id="repair.completed", label="增压空气系统已完成模拟接头处理。", fields=[field("repair_object", "处理对象"), field("repair_action", "模拟处理动作")]),
            ProtocolOption(option_id="repair.not_completed", label="增压空气系统模拟接头处理尚未完成。", fields=[field("pending_reason", "未完成原因")])], ["S02-P2"], "repair_status",
            presentation("记录已定位接头的模拟处理状态。", "前一步已经记录明确漏点；只有处理完成后才适合进入处理后复检。",
                ["确认要处理的演示接头。", "记录模拟处理动作和完成状态。", "按实际状态保存。"],
                "系统只记录处理事实；处理完成不等于故障已经排除。",
                ["定位局部泄漏"], "模拟处理", ["处理后复检", "最终复核", "演示小结"])),
        check("CHK-07", "after_air_repair_retest", [
            ProtocolOption(option_id="retest.record", label="增压空气系统提交处理后复检记录。", fields=RETEST_FIELDS)], ["DS-02", "CHK-07"], "ds02_retest",
            presentation("检查已处理的增压空气软管接头，并完成一次处理后复检。", "上一步已经记录局部泄漏和模拟处理。本次复检用于确认漏点是否消失、增压数据是否恢复，以及原症状是否仍然存在。",
                ["确认已处理接头和软管连接状态。", "检查原位置是否仍有可定位泄漏。", "选择演示场景或录入处理后三帧增压数据。", "确认原症状是否仍然存在。", "保存复检结果。"],
                "系统会根据泄漏结果、三帧压力差和原症状选择下一步；不会仅凭一项数据宣布车辆已经修复。",
                ["定位局部泄漏", "模拟处理"], "处理后复检", ["最终复核", "演示小结"], [
                    DemoMeasurementPreset(id="recovered", label="复检恢复", explanation="未发现原位置漏点，三帧演示压力在协议带内，原症状未出现。", fields={"leak_result":"not_found", "symptom":"absent", "target_1_hpa":"2000", "actual_1_hpa":"1950", "target_2_hpa":"2050", "actual_2_hpa":"2000", "target_3_hpa":"2100", "actual_3_hpa":"2050"}),
                    DemoMeasurementPreset(id="residual_underboost", label="仍然增压不足", explanation="未发现原位置漏点，但三帧实际压力持续低于目标且原症状仍存在。", fields={"leak_result":"not_found", "symptom":"present", "target_1_hpa":"2000", "actual_1_hpa":"1700", "target_2_hpa":"2050", "actual_2_hpa":"1720", "target_3_hpa":"2100", "actual_3_hpa":"1750"}),
                    DemoMeasurementPreset(id="insufficient", label="数据不足", explanation="结果或工况无法判断；不填写缺失帧，服务端将给出待补交接。", fields={"leak_result":"inconclusive", "symptom":"present"}),
                ])),
        check("CHK-11", "final_demo_retest", [
            ProtocolOption(option_id="final.record", label="增压空气系统提交最终演示复检记录。", fields=FINAL_FIELDS)], ["DS-03", "CHK-11"], "ds03_final",
            presentation("确认最终演示复检新增事实。", "系统沿用最近一次有效处理后复检数据；本步只确认症状、故障码、处理复核和冲突。",
                ["核对页面引用的最近一次处理后复检数据。", "确认原症状和 P0299 是否再次出现。", "确认已处理问题是否复核，以及是否仍有冲突。", "保存最终确认。"],
                "系统会重新使用冻结协议判断是否形成演示小结；这仍不是实车修复证明或正式最终报告。",
                ["定位局部泄漏", "模拟处理", "处理后复检"], "最终复核", ["演示小结"])),
    ],
    transitions=[
        transition("CHK05_LOCALIZED_TO_CHK06", "CHK-05", "leak.localized", "next_check", "CHK-06"),
        transition("CHK05_NOT_FOUND_HANDOFF", "CHK-05", "leak.not_found", "handoff", code="HANDOFF_CONTROL_DIRECTION", reason="本项未发现局部漏点；下一方向是调节机构检查，不能据此写系统正常或故障排除。"),
        transition("CHK05_INCONCLUSIVE_TO_SUPPLEMENT", "CHK-05", "leak.inconclusive", "need_input", "CHK-05-SUPPLEMENT", reason="请补充泄漏对象、位置和定位依据。"),
        transition("CHK05_UNAVAILABLE_HANDOFF", "CHK-05", "unavailable", "handoff", code="HANDOFF_UNAVAILABLE", reason="当前检查无法完成；请补充所需工具或可观察部位后再继续。"),
        transition("SUPPLEMENT_LOCALIZED_TO_CHK06", "CHK-05-SUPPLEMENT", "leak.localized", "next_check", "CHK-06"),
        transition("SUPPLEMENT_INCONCLUSIVE_HANDOFF", "CHK-05-SUPPLEMENT", "leak.inconclusive", "handoff", code="HANDOFF_UNAVAILABLE", reason="一次补充后仍缺少可核验定位观察，转交补充工具或资料。"),
        transition("SUPPLEMENT_UNAVAILABLE_HANDOFF", "CHK-05-SUPPLEMENT", "unavailable", "handoff", code="HANDOFF_UNAVAILABLE", reason="补充定位仍无法完成，转交补充工具或资料。"),
        transition("CHK06_COMPLETED_TO_CHK07", "CHK-06", "repair.completed", "next_check", "CHK-07"),
        transition("CHK06_PENDING_HANDOFF", "CHK-06", "repair.not_completed", "handoff", code="HANDOFF_REPAIR_PENDING", reason="处理尚未完成，不能发布已修复或进入处理后复检。"),
        transition("CHK06_UNAVAILABLE_HANDOFF", "CHK-06", "unavailable", "handoff", code="HANDOFF_REPAIR_PENDING", reason="处理当前无法完成，保留待处理状态。"),
        transition("CHK07_RECOVERED_TO_CHK11", "CHK-07", "retest.recovered", "next_check", "CHK-11"),
        transition("CHK07_RESIDUAL_HANDOFF", "CHK-07", "retest.residual_underboost", "handoff", code="HANDOFF_CONTROL_DIRECTION", reason="已处理一个问题但仍有残余增压不足，下一方向为调节机构检查。"),
        transition("CHK07_SAME_LEAK_HANDOFF", "CHK-07", "retest.same_leak", "handoff", code="HANDOFF_REPAIR_RECHECK", reason="同处仍可定位泄漏；应带复查理由返回定位和处理，不自动循环。"),
        transition("CHK07_OTHER_HANDOFF", "CHK-07", "retest.symptom_elsewhere", "handoff", code="HANDOFF_OTHER_DIRECTION", reason="压力已在演示带内但原症状仍在，应转交其他故障方向。"),
        transition("CHK07_INSUFFICIENT_HANDOFF", "CHK-07", "retest.insufficient", "handoff", code="HANDOFF_RETEST_INCOMPLETE", reason="复检帧、单位、工况或结果不足，不能继续到最终复检。"),
        transition("CHK07_UNAVAILABLE_HANDOFF", "CHK-07", "unavailable", "handoff", code="HANDOFF_RETEST_INCOMPLETE", reason="处理后复检无法完成，保留待补项目。"),
        transition("CHK11_PASS_SUMMARY", "CHK-11", "final.passed", "area_summary", code="AREA_SUMMARY_DEMO_PASS", reason="演示病例最终复检条件已满足；这不是实车修复证明，最终报告仍需用户主动请求。"),
        transition("CHK11_INCOMPLETE_HANDOFF", "CHK-11", "final.incomplete", "handoff", code="HANDOFF_FINAL_RECHECK_INCOMPLETE", reason="最终复检条件未全部满足，转交未完成项目。"),
        transition("CHK11_UNAVAILABLE_HANDOFF", "CHK-11", "unavailable", "handoff", code="HANDOFF_FINAL_RECHECK_INCOMPLETE", reason="最终复检无法完成，转交未完成项目。"),
    ])

def _v3_option(option_id, label, fields=None):
    return ProtocolOption(option_id=option_id, label=label, fields=fields or [])


_V3_STAGES = ["接车确认", "症状与故障码", "静态数据可信度", "负荷增压记录", "空气路径外观",
              "局部泄漏定位", "模拟处理", "处理后复检", "调节机构观察", "受控执行", "交接说明",
              "最终复核", "演示小结"]


def _v3_display(index, presets=None):
    current = _V3_STAGES[index]
    return presentation(
        current, f"{current}是保守流程的受控检查点。",
        ["仅使用页面提供的合成演示数据或如实填写观察。", "确认单位、工况和记录属于同一次检查。", "保存后由冻结协议选择下一步。"],
        "系统只依据已保存事实推进；条件不足时会明确交接，不会猜测结论。",
        _V3_STAGES[:index], current, _V3_STAGES[index + 1:], presets)


def _v3_check(check_id, stage, options, index, presets=None):
    return ProtocolCheck(check_id=check_id, current_stage=stage,
        input_schema=ProtocolInput(options=options), evidence_refs=["R1-FLOW-01"],
        completion_rule=stage, presentation=_v3_display(index, presets))


_V3_CHECKS = [
    _v3_check("CHK-00", "intake_confirmation", [
        _v3_option("intake.confirmed", "已确认本次为 DKVB/P0299 合成演示，不形成维修结论。")], 0),
    _v3_check("CHK-01", "symptom_profile", [
        _v3_option("profile.recorded", "已记录车型、症状、P0299及补充背景。", [
            field("other_codes", "其他故障码", required=False),
            field("recent_pipe_work", "近期管路作业", "select", ["yes", "no", "unknown"]),
            field("symptom_note", "症状补充", required=False)])], 1),
    _v3_check("CHK-02", "static_credibility", [
        _v3_option("static.compatible", "静态读数相互吻合，可进入同次负荷记录。", [
            field("ambient_hpa", "环境绝对压力（hPa）", "decimal"), field("g31_static_hpa", "G31静态绝对压力（hPa）", "decimal")]),
        _v3_option("static.abnormal", "静态读数明显异常，当前测量链不可信。", [
            field("ambient_hpa", "环境绝对压力（hPa）", "decimal"), field("g31_static_hpa", "G31静态绝对压力（hPa）", "decimal")]),
        _v3_option("static.ambiguous", "静态读数或工况不足，无法确认可信度。", [field("ambiguity_note", "缺失或冲突说明")])], 2, [
            DemoMeasurementPreset(id="static_compatible", label="读数相容", explanation="环境与 G31 静态值接近。", option_id="static.compatible", fields={"ambient_hpa":"1005", "g31_static_hpa":"1008"}),
            DemoMeasurementPreset(id="static_abnormal", label="读数异常", explanation="G31 静态值与环境值明显不符。", option_id="static.abnormal", fields={"ambient_hpa":"1005", "g31_static_hpa":"1450"}),
            DemoMeasurementPreset(id="static_ambiguous", label="信息不足", explanation="记录条件不完整，保守交接。", option_id="static.ambiguous", fields={"ambiguity_note":"静态记录工况或单位无法核验"})]),
    _v3_check("CHK-03", "load_underboost", [
        _v3_option("load.record", "提交同次三帧负荷增压记录。", PRESSURE_FIELDS + [field("symptom", "原症状", "select", ["absent", "present"])])], 3, [
            DemoMeasurementPreset(id="load_underboost", label="稳定增压不足", explanation="DEMO_LOAD_STABLE；三帧实际压力持续低于目标。", fields={"symptom":"present","target_1_hpa":"2000","actual_1_hpa":"1700","target_2_hpa":"2050","actual_2_hpa":"1720","target_3_hpa":"2100","actual_3_hpa":"1750"}),
            DemoMeasurementPreset(id="load_in_band", label="压力在带内但症状仍在", explanation="同次记录压力在演示带内。", fields={"symptom":"present","target_1_hpa":"2000","actual_1_hpa":"1950","target_2_hpa":"2050","actual_2_hpa":"2000","target_3_hpa":"2100","actual_3_hpa":"2050"}),
            DemoMeasurementPreset(id="load_mixed", label="混合或不足", explanation="帧间趋势不一致。", fields={"symptom":"present","target_1_hpa":"2000","actual_1_hpa":"1700","target_2_hpa":"2050","actual_2_hpa":"2020","target_3_hpa":"2100","actual_3_hpa":"2300"})]),
    _v3_check("CHK-04", "air_path_visual", [
        _v3_option("air.seating_suspect", "发现接头就位可疑。", [field("object", "对象"), field("location", "位置"), field("photo_ref", "照片引用", required=False), field("note", "备注", required=False)]),
        _v3_option("air.wall_damage", "发现管壁损伤。", [field("object", "对象"), field("location", "位置"), field("photo_ref", "照片引用", required=False), field("note", "备注", required=False)]),
        _v3_option("air.oil_trace_only", "仅见油迹，尚不能定位泄漏。", [field("object", "对象"), field("location", "位置"), field("note", "备注", required=False)]),
        _v3_option("air.none", "未见明确外观异常。", [field("note", "备注", required=False)])], 4),
    _v3_check("CHK-05", "localized_leak_check", [
        _v3_option("leak.localized", "已定位局部泄漏。", LOCATOR_FIELDS), _v3_option("leak.not_found", "未发现局部泄漏。"),
        _v3_option("leak.inconclusive", "局部泄漏结果无法确定。")], 5),
    _v3_check("CHK-05-SUPPLEMENT", "localized_leak_evidence", [
        _v3_option("supplement.localized", "补充观察已定位局部泄漏。", LOCATOR_FIELDS),
        _v3_option("supplement.inconclusive", "补充后仍无法确定。")], 5),
    _v3_check("CHK-06", "after_air_repair", [
        _v3_option("repair.completed", "已完成模拟接头处理。", [field("repair_object", "处理对象"), field("repair_action", "模拟处理动作")]),
        _v3_option("repair.not_completed", "模拟处理尚未完成。", [field("pending_reason", "未完成原因")])], 6),
    _v3_check("CHK-07", "after_air_repair_retest", [_v3_option("retest.record", "提交处理后复检记录。", RETEST_FIELDS)], 7, [
        DemoMeasurementPreset(id="recovered", label="复检恢复", explanation="漏点消失、压力在带内且症状未出现。", fields={"leak_result":"not_found","symptom":"absent","target_1_hpa":"2000","actual_1_hpa":"1950","target_2_hpa":"2050","actual_2_hpa":"2000","target_3_hpa":"2100","actual_3_hpa":"2050"}),
        DemoMeasurementPreset(id="residual_underboost", label="仍然增压不足", explanation="漏点未再发现，但仍持续增压不足。", fields={"leak_result":"not_found","symptom":"present","target_1_hpa":"2000","actual_1_hpa":"1700","target_2_hpa":"2050","actual_2_hpa":"1720","target_3_hpa":"2100","actual_3_hpa":"1750"}),
        DemoMeasurementPreset(id="insufficient", label="数据不足", explanation="结果不足，保守交接。", fields={"leak_result":"inconclusive","symptom":"present"})]),
    _v3_check("CHK-08", "control_visual", [
        _v3_option("control.continue", "调节机构观察可继续受控执行。", [field("connector_status", "插头状态", "select", ["secure", "loose", "unknown"]), field("linkage_status", "连接机构状态", "select", ["free", "restricted", "unknown"]), field("prior_guided_result", "既有引导结果", "select", ["none", "consistent", "conflict"]), field("note", "备注", required=False)]),
        _v3_option("control.conflict", "观察存在冲突或不能支持继续。", [field("note", "冲突说明")])], 8),
    _v3_check("CHK-09", "controlled_setup", [
        _v3_option("setup.not_run", "受控执行尚未运行。"), _v3_option("setup.needed", "受控执行条件尚未就绪。", [field("pending_reason", "所需条件")]),
        _v3_option("setup.completed", "已完成合成受控执行设置。"), _v3_option("setup.failed", "受控执行失败。", [field("failure_note", "失败说明")])], 9),
    _v3_check("CHK-10", "handoff_record", [_v3_option("handoff.acknowledged", "已查看并确认当前交接说明。")], 10),
    _v3_check("CHK-11", "final_demo_retest", [_v3_option("final.record", "提交最终演示复检记录。", FINAL_FIELDS)], 11, [
        DemoMeasurementPreset(id="control_final_recovered", label="控制设置后恢复", explanation="新建 after_control_setup 三帧记录；不覆盖此前残余增压不足。", fields={"symptom":"absent","p0299":"absent","repairs_rechecked":"completed","conflict":"none","final_target_1_hpa":"2000","final_actual_1_hpa":"1950","final_target_2_hpa":"2050","final_actual_2_hpa":"2000","final_target_3_hpa":"2100","final_actual_3_hpa":"2050"})])]


_V3_TRANSITIONS = []
def _v3_transition(current, result, decision, next_check=None, code=None, reason=None):
    token = f"{current.replace('-', '')}_{result.replace('.', '_').upper()}"
    _V3_TRANSITIONS.append(transition(token, current, result, decision, next_check, code, reason))


_v3_transition("CHK-00", "intake.confirmed", "next_check", "CHK-01"); _v3_transition("CHK-00", "unavailable", "next_check", "CHK-10", reason="接车确认无法完成。")
_v3_transition("CHK-01", "profile.recorded", "next_check", "CHK-02"); _v3_transition("CHK-01", "unavailable", "next_check", "CHK-10", reason="车型、症状或故障码背景无法确认。")
_v3_transition("CHK-02", "static.compatible", "next_check", "CHK-03"); _v3_transition("CHK-02", "static.abnormal", "next_check", "CHK-10", reason="静态读数明显异常，测量链不可信；请核对传感器、单位、工况和采集链。")
_v3_transition("CHK-02", "static.ambiguous", "next_check", "CHK-10", reason="静态读数或工况不足；请补充可信静态记录后再继续。"); _v3_transition("CHK-02", "unavailable", "next_check", "CHK-10", reason="静态可信度检查无法完成。")
_v3_transition("CHK-03", "load.record", "next_check", "CHK-04"); _v3_transition("CHK-03", "load.underboost", "next_check", "CHK-04")
_v3_transition("CHK-03", "load.symptom_elsewhere", "next_check", "CHK-10", reason="负荷压力在演示带内但症状仍存在，应转交其他方向。"); _v3_transition("CHK-03", "load.insufficient", "next_check", "CHK-10", reason="同次三帧负荷记录混合或不足。")
_v3_transition("CHK-03", "load.overboost", "next_check", "CHK-10", reason="记录呈过增压方向，不应沿 P0299 保守路径继续。"); _v3_transition("CHK-03", "unavailable", "next_check", "CHK-10", reason="负荷记录无法完成。")
for _result in ("air.seating_suspect", "air.wall_damage", "air.oil_trace_only", "air.none"):
    _v3_transition("CHK-04", _result, "next_check", "CHK-05")
_v3_transition("CHK-04", "unavailable", "next_check", "CHK-10", reason="空气路径外观无法观察。")
_v3_transition("CHK-05", "leak.localized", "next_check", "CHK-06"); _v3_transition("CHK-05", "leak.not_found", "next_check", "CHK-08")
_v3_transition("CHK-05", "leak.inconclusive", "need_input", "CHK-05-SUPPLEMENT", reason="仅允许补充一次定位观察。"); _v3_transition("CHK-05", "unavailable", "next_check", "CHK-10", reason="局部泄漏定位无法完成。")
_v3_transition("CHK-05-SUPPLEMENT", "supplement.localized", "next_check", "CHK-06"); _v3_transition("CHK-05-SUPPLEMENT", "supplement.inconclusive", "next_check", "CHK-10", reason="补充后仍无可核验定位观察。"); _v3_transition("CHK-05-SUPPLEMENT", "unavailable", "next_check", "CHK-10", reason="补充定位无法完成。")
_v3_transition("CHK-06", "repair.completed", "next_check", "CHK-07"); _v3_transition("CHK-06", "repair.not_completed", "next_check", "CHK-10", reason="模拟处理尚未完成。"); _v3_transition("CHK-06", "unavailable", "next_check", "CHK-10", reason="模拟处理无法完成。")
_v3_transition("CHK-07", "retest.record", "next_check", "CHK-11"); _v3_transition("CHK-07", "retest.recovered", "next_check", "CHK-11")
_v3_transition("CHK-07", "retest.residual_underboost", "next_check", "CHK-08"); _v3_transition("CHK-07", "retest.same_leak", "next_check", "CHK-10", reason="原位置仍可定位泄漏，应返回处理复查。")
_v3_transition("CHK-07", "retest.symptom_elsewhere", "next_check", "CHK-10", reason="压力恢复但症状仍在，应转交其他方向。"); _v3_transition("CHK-07", "retest.insufficient", "next_check", "CHK-10", reason="处理后复检记录不足。"); _v3_transition("CHK-07", "unavailable", "next_check", "CHK-10", reason="处理后复检无法完成。")
_v3_transition("CHK-08", "control.continue", "next_check", "CHK-09"); _v3_transition("CHK-08", "control.conflict", "next_check", "CHK-10", reason="调节机构观察存在冲突。"); _v3_transition("CHK-08", "unavailable", "next_check", "CHK-10", reason="调节机构观察无法完成。")
_v3_transition("CHK-09", "setup.not_run", "need_input", "CHK-09", reason="请完成或明确记录受控执行条件。"); _v3_transition("CHK-09", "setup.needed", "need_input", "CHK-09", reason="受控执行条件尚未就绪。")
_v3_transition("CHK-09", "setup.completed", "next_check", "CHK-11"); _v3_transition("CHK-09", "setup.failed", "next_check", "CHK-10", reason="受控执行失败，保留失败原因并交接。"); _v3_transition("CHK-09", "unavailable", "next_check", "CHK-10", reason="受控执行无法完成。")
_v3_transition("CHK-10", "handoff.acknowledged", "handoff", code="HANDOFF_CONSERVATIVE", reason="当前流程已保守交接；已保存事实不会被解释为确诊、排除或修复完成。"); _v3_transition("CHK-10", "unavailable", "handoff", code="HANDOFF_CONSERVATIVE", reason="交接确认无法完成；已保存事实仍保留。")
_v3_transition("CHK-11", "final.record", "area_summary", code="AREA_SUMMARY_DEMO_PASS", reason="全流程演示最终复检条件已满足；这不是实车修复证明。"); _v3_transition("CHK-11", "final.passed", "area_summary", code="AREA_SUMMARY_DEMO_PASS", reason="全流程演示最终复检条件已满足；这不是实车修复证明。")
_v3_transition("CHK-11", "final.incomplete", "handoff", code="HANDOFF_FINAL_RECHECK_INCOMPLETE", reason="最终复检条件未全部满足。"); _v3_transition("CHK-11", "unavailable", "handoff", code="HANDOFF_FINAL_RECHECK_INCOMPLETE", reason="最终复检无法完成。")


DKVB_DEMO_PROTOCOL_V3 = TrustedProtocol(protocol_id="dkvb-p0299-guided-demo", version="3.0.0",
    synthetic=True, formal_usable=False, applicable_vehicle_profile=PROFILE,
    start_check_id="CHK-00", checks=_V3_CHECKS, transitions=_V3_TRANSITIONS)

_V31_CONTENT = {
    "CHK-01": ("补充本次故障背景", "本次故障在什么条件下出现，是否还有其他故障码或近期管路作业？", "病例信息已经由接诊页冻结；这里只补充本次现象背景。", ["选择症状出现条件。", "补充其他故障码和近期管路作业。", "必要时填写症状说明并保存。"], "保存后进入静态测量可信度核对。", "病例信息 / 用户补充", "病例与测量确认"),
    "CHK-02": ("确认静态压力读数是否可信", "环境绝对压力与 G31 静态绝对压力是否相容？", "记录同一静态工况下的两项绝对压力。", ["确认车辆处于静态演示工况。", "读取环境与 G31 的 hPa absolute 数值。", "选择相容、异常或信息不足并保存。"], "可信时进入负荷记录；异常或不足时形成保守交接。", "G31 位置事实 + DS-01 合成判断", "病例与测量确认"),
    "CHK-03": ("记录同次负荷下的增压表现", "三帧实际压力是否持续低于目标，并且原症状是否出现？", "记录同一次 run 的三帧目标/实际绝对压力。", ["选择演示场景或逐帧录入。", "核对三帧都属于同一次负荷记录。", "确认原症状并保存。"], "稳定不足才进入增压系统检查；其他结果明确交接。", "症状方向资料 + DS-02 合成判断", "故障现象与数据确认"),
    "CHK-04": ("检查增压空气软管和接头外观", "是否存在接头未到位、管壁损伤或仅有油迹等可记录现象？", "记录对象、位置以及可选照片或备注。", ["沿空气软管和接头观察。", "区分就位可疑、管壁损伤、仅油迹和未见异常。", "按实际观察保存。"], "保存后进入局部泄漏定位，外观观察本身不等于泄漏结论。", "S02 空气软管装配事实", "系统检查"),
    "CHK-05": ("定位增压空气系统局部泄漏", "本项是否发现可定位的漏点？", "如已定位，记录对象、位置和定位方式。", ["按受控资料检查可观察部位。", "选择已定位、未发现或无法确定。", "已定位时补齐定位字段并保存。"], "定位后进入模拟处理；未发现转向调节机构；不确定只补充一次。", "S02-P5/P6 方法事实", "系统检查"),
    "CHK-05-SUPPLEMENT": ("补充一次泄漏定位观察", "补充后能否给出可核验的泄漏对象和位置？", "本步骤只允许一次补充，不形成循环。", ["补充观察对象、位置与定位方式。", "选择已定位或仍无法确定。", "保存补充事实。"], "仍无法确定时形成有内容交接。", "S02-P5/P6 方法事实", "系统检查"),
    "CHK-06": ("记录已定位问题的处理状态", "已定位的软管或接头是否完成模拟处理？", "记录处理对象、动作或未完成原因。", ["核对前一步定位对象。", "记录实际模拟处理状态。", "保存后再决定是否复检。"], "完成才进入处理后复检；未完成保留待办。", "S02-P2 装配事实", "处理与复检"),
    "CHK-07": ("完成处理后复检", "原漏点是否消失，压力是否恢复，原症状是否仍出现？", "生成新的 after_air_repair 三帧复检记录。", ["复查原泄漏位置。", "选择场景或录入三帧数据。", "确认原症状并保存。"], "恢复时进入最终复核；残余不足转向调节机构。", "DS-02 合成复检规则", "处理与复检"),
    "CHK-08": ("观察增压调节机构", "连接器、连接机构和既有引导结果是否支持继续受控执行？", "分别记录插头、连接机构和既有引导结果。", ["观察 V465 连接器与连接机构。", "记录是否存在松动、卡滞、未知或冲突。", "保存结构化观察。"], "可继续时进入受控设置；冲突时保守交接。", "S03-P2/P8 位置与连接事实", "系统检查"),
    "CHK-09": ("记录受控执行设置结果", "合成受控设置是否完成，或还缺什么条件？", "记录未运行、条件不足、完成或失败。", ["确认演示设置条件。", "记录执行状态及必要原因。", "保存本次结果。"], "完成后必须新建 after_control_setup 最终复检；失败不伪装成功。", "S03-P8/P9 受控执行参考", "处理与复检"),
    "CHK-10": ("整理当前保守交接", "你是否已了解当前交接事项和仍需补充的条件？", "交接保留触发原因、已保存事实和下一建议。", ["阅读当前触发原因。", "核对仍需补充的工具、数据或条件。", "确认已了解交接事项。"], "确认只表示已阅读，不代表诊断观察或维修结论。", "流程交接说明（非维修证据）", "小结或交接"),
    "CHK-11": ("完成最终演示复检", "最新阶段的压力、症状、P0299、处理复核和冲突是否同时满足？", "引用最近有效复检并记录最终新增事实。", ["核对页面引用的复检数据。", "确认症状、P0299、处理复核与冲突。", "保存最终演示复检。"], "全部满足形成演示小结，否则形成未完成交接。", "DS-03 合成组合规则", "小结或交接"),
}

_V31_EVIDENCE = {"CHK-01":["CASE_INTAKE","USER_REPORTED"], "CHK-02":["S02-P4","DS-01"],
    "CHK-03":["S04","DS-02"], "CHK-04":["S02-P2"], "CHK-05":["S02-P5","S02-P6"],
    "CHK-05-SUPPLEMENT":["S02-P5","S02-P6"], "CHK-06":["S02-P2"], "CHK-07":["DS-02"],
    "CHK-08":["S03-P2","S03-P8"], "CHK-09":["S03-P8","S03-P9"],
    "CHK-10":["EDITORIAL_HANDOFF"], "CHK-11":["DS-03"]}

def _v31_check(old):
    title, question, record, steps, outcome, kind, phase = _V31_CONTENT[old.check_id]
    display = old.presentation.model_copy(update={
        "task_summary": title, "why_summary": question, "operation_steps": steps,
        "completion_explanation": outcome, "task_title": title, "question": question,
        "record_summary": record, "outcome_preview": outcome, "evidence_kind": kind,
        "progress_phase": phase,
    })
    schema = old.input_schema
    if old.check_id == "CHK-01":
        schema = ProtocolInput(options=[_v3_option("profile.recorded", "保存本次故障背景。", [
            field("symptom_conditions", "症状出现条件", "select", ["acceleration", "high_load", "intermittent", "unknown"]),
            field("other_codes", "其他故障码", required=False),
            field("recent_pipe_work", "近期管路作业", "select", ["yes", "no", "unknown"]),
            field("symptom_note", "症状补充", required=False)])])
    return old.model_copy(update={"input_schema": schema, "evidence_refs": _V31_EVIDENCE[old.check_id],
                                  "presentation": display})

_V31_CHECKS = [_v31_check(item) for item in _V3_CHECKS if item.check_id != "CHK-00"]
_V31_TRANSITIONS = [item for item in _V3_TRANSITIONS if item.current_check_id != "CHK-00"]
DKVB_DEMO_PROTOCOL = TrustedProtocol(protocol_id="dkvb-p0299-guided-demo", version="3.1.0",
    synthetic=True, formal_usable=False, applicable_vehicle_profile=PROFILE,
    start_check_id="CHK-01", checks=_V31_CHECKS, transitions=_V31_TRANSITIONS)

REGISTRY = {(item.protocol_id, item.version): item for item in (DKVB_DEMO_PROTOCOL_V3, DKVB_DEMO_PROTOCOL)}
APPROVED_PROTOCOLS = frozenset({("dkvb-p0299-guided-demo", "2.0.0"),
                                ("dkvb-p0299-guided-demo", "2.1.0"), *REGISTRY})


def build_demo_candidates(cite):
    purpose = "增压空气系统局部泄漏检查用于确认有无可定位漏点，而不是用整个系统压降推断泄漏。"
    location = "增压空气系统位置见 S02-P5/P6 装配图。"
    prerequisite = "演示操作只填写已给出的模拟结果，不操作真实气源。"
    action = "检查 增压空气系统 外观。"
    bounded_choice = "增压空气系统外观完好。"
    result = {}
    for item in DKVB_DEMO_PROTOCOL.checks:
        result[item.check_id] = {"type": "propose_step", "component_key": "增压空气系统",
            "title": f"{item.presentation.task_title or item.presentation.progress_current}（DEMO）", "purpose": cite(purpose), "location": cite(location),
            "prerequisites": [cite(prerequisite)],
            "actions": [{**cite(action), "operation": "read" if action.startswith("读取") else "inspect"}],
            "input": {"kind": "choice", "choices": [cite(bounded_choice) for _ in item.input_schema.options]},
            "interpretation": []}
    return result


def required_demo_material_texts():
    """Return every exact source fragment needed to bind the public R1 protocol."""
    texts = []

    def collect(text):
        texts.append(text)
        return {"text": text, "references": []}

    build_demo_candidates(collect)
    return tuple(dict.fromkeys(texts))
