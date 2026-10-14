"""Server-derived conservative workbench projection.

This is a read model over persisted case, protocol, observation and terminal
facts.  It deliberately stores no parallel workflow state.
"""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import select

from app.domain.policies import DomainError
from app.infrastructure.orm import cases, diagnosis_area_conclusions, diagnosis_steps
from app.infrastructure.uow import UnitOfWork
from app.repositories.observations import ObservationRepository


AREA_DEFINITIONS = (
    ("measurement-confirmation", "病例与测量确认", 1, "这是后续增压判断的前置条件", (
        ("case-background", "病例背景", (("CHK-00", "冻结病例接诊信息"), ("CHK-01", "补充症状与故障背景"))),
        ("static-pressure", "静态压力可信度", (("CHK-02", "确认静态压力读数是否可信"),)),
        ("load-record", "负荷增压记录", (("CHK-03", "记录同次负荷增压数据"),)),
    )),
    ("charge-air-path", "增压空气通路", 2, "由测量确认结果和冻结协议顺序开放", (
        ("air-path-visual", "空气软管和接头外观", (("CHK-04", "检查空气通路外观"),)),
        ("local-leak", "局部泄漏定位", (("CHK-05", "定位局部泄漏"), ("CHK-05-SUPPLEMENT", "补充一次定位观察"))),
        ("confirmed-repair", "已确认问题处理", (("CHK-06", "记录已确认问题的处理"),)),
        ("post-repair-retest", "处理后复检", (("CHK-07", "取得处理后的复检记录"),)),
    )),
    ("boost-control", "增压调节机构", 3, "仅在空气通路处理后仍有残余增压不足时开放", (
        ("control-observation", "调节器连接器与连接机构", (("CHK-08", "观察调节机构"),)),
        ("guided-setup", "模拟引导设置", (("CHK-09", "记录受控设置结果"),)),
    )),
    ("conservative-handoff", "其他方向与保守交接", 4, "资料、测量或执行条件不足时进入", (
        ("handoff", "专题边界与补充条件", (("CHK-10", "整理当前保守交接"),)),
    )),
    ("final-verification", "最终复核", 5, "仅在当前路径具备最终复检条件时开放", (
        ("final-retest", "最终复检与演示小结", (("CHK-11", "完成最终演示复检"),)),
    )),
)

CHECK_TO_AREA = {
    check_id: area_id
    for area_id, _title, _priority, _reason, components in AREA_DEFINITIONS
    for _component_id, _component_title, actions in components
    for check_id, _action_title in actions
}
CHECK_ORDER = [
    "CHK-00", "CHK-01", "CHK-02", "CHK-03", "CHK-04", "CHK-05",
    "CHK-05-SUPPLEMENT", "CHK-06", "CHK-07", "CHK-08", "CHK-09", "CHK-10", "CHK-11",
]


def _option(payload):
    return str(payload.get("option_id") or "")


def _fact_text(row):
    payload = row["payload"] or {}
    check_id = payload.get("check_id")
    label = payload.get("option_label") or payload.get("fact_kind") or row["kind"]
    return f"{check_id or '病例'}：{label}"


class WorkbenchViewService:
    def __init__(self, engine):
        self.engine = engine

    def get(self, actor: UUID, case_id: UUID):
        with UnitOfWork(self.engine) as uow:
            c = uow.connection
            case = c.execute(select(cases).where(
                cases.c.id == case_id, cases.c.owner_id == actor,
            )).mappings().one_or_none()
            if case is None:
                raise DomainError("NOT_FOUND", "Case not found", 404)

            current = c.execute(select(diagnosis_steps).where(
                diagnosis_steps.c.case_id == case_id,
                diagnosis_steps.c.status == "waiting_input",
            )).mappings().one_or_none()
            protocol = ((current or {}).get("validation_json") or {}).get("protocol") or {}
            current_check = protocol.get("next_check_id")
            terminal_card = c.execute(select(diagnosis_area_conclusions).where(
                diagnosis_area_conclusions.c.case_id == case_id,
                diagnosis_area_conclusions.c.graph_epoch == case["graph_epoch"],
            ).order_by(diagnosis_area_conclusions.c.created_revision.desc())).mappings().first()
            terminal = ((terminal_card or {}).get("content_json") or {}).get("protocol_terminal") or {}
            terminal_code = terminal.get("terminal_code")

            effective = [dict(row) for row in ObservationRepository(c).read(
                case_id, None, case["revision"],
            )]
            # A correction starts a new graph epoch.  Observations that were
            # downstream of the corrected check remain audit history, but must
            # not keep projected completion alive.
            replacements = [row for row in effective if row.get("supersedes_id")]
            if replacements:
                latest = max(replacements, key=lambda row: row["created_revision"])
                corrected_check = (latest["payload"] or {}).get("check_id")
                if corrected_check in CHECK_ORDER:
                    cutoff = CHECK_ORDER.index(corrected_check)
                    effective = [row for row in effective if not (
                        row["created_revision"] < latest["created_revision"]
                        and (row["payload"] or {}).get("check_id") in CHECK_ORDER
                        and CHECK_ORDER.index((row["payload"] or {}).get("check_id")) > cutoff
                    )]

            by_check = defaultdict(list)
            for row in effective:
                check_id = (row["payload"] or {}).get("check_id")
                if check_id:
                    by_check[check_id].append(row)
            completed = set(by_check)
            options = {check_id: _option(rows[-1]["payload"] or {}) for check_id, rows in by_check.items()}
            abnormal_options = {
                "static.abnormal", "load.underboost", "visual.suspect", "leak.localized",
                "retest.residual_underboost", "control.conflict", "setup.failed",
            }
            abnormal_checks = {check_id for check_id, option in options.items() if option in abnormal_options}
            handoff = bool(terminal) and terminal.get("decision") == "handoff"
            demo_complete = terminal_code == "AREA_SUMMARY_DEMO_PASS"

            areas = []
            for area_id, title, priority, priority_reason, component_defs in AREA_DEFINITIONS:
                area_checks = [check_id for _cid, _ctitle, actions in component_defs for check_id, _ in actions]
                completed_count = len(set(area_checks) & completed)
                current_here = current_check in area_checks
                available, locked_reason = self._availability(area_id, current_check, completed, options, terminal_code)
                status = self._area_status(
                    area_id, current_here, completed, options, abnormal_checks, handoff, demo_complete,
                )
                components = []
                for component_id, component_title, action_defs in component_defs:
                    actions = []
                    for check_id, action_title in action_defs:
                        action_status = "completed" if check_id in completed else "current" if check_id == current_check else "not_started" if available else "locked"
                        actions.append({"check_id": check_id, "title": action_title,
                                        "status": action_status, "available": check_id == current_check})
                    component_status = "current" if any(a["status"] == "current" for a in actions) else "completed" if actions and all(a["status"] == "completed" for a in actions) else "not_started" if available else "locked"
                    components.append({"component_id": component_id, "title": component_title,
                                       "status": component_status, "actions": actions})
                areas.append({"area_id": area_id, "title": title, "priority": priority,
                              "priority_reason": priority_reason, "status": status,
                              "completed_checks": completed_count, "required_checks": len(area_checks),
                              "has_abnormality": bool(set(area_checks) & abnormal_checks),
                              "available": available, "locked_reason": locked_reason,
                              "components": components})

            selected_area_id = CHECK_TO_AREA.get(current_check) or (
                "final-verification" if demo_complete else "conservative-handoff" if handoff else "measurement-confirmation"
            )
            selected = next(area for area in areas if area["area_id"] == selected_area_id)
            current_component = next((item for item in selected["components"]
                                      if item["status"] == "current"), None)
            intake = case["intake_snapshot"] or {}
            symptom = (by_check.get("CHK-01") or [{}])[-1].get("payload", {}).get("protocol_fields", {})
            vehicle = dict(intake.get("vehicle") or case["vehicle_json"])
            vehicle.setdefault("vin", None)
            confirmed = [f"故障码：{'、'.join(intake.get('fault_codes') or case['fault_codes']) or '未提供'}"]
            confirmed.extend(_fact_text(row) for row in effective if row["kind"] != "intake_snapshot")
            handled = ["已记录并保存局部泄漏处理"] if "CHK-06" in completed else []
            remaining = []
            if "CHK-02" in abnormal_checks:
                remaining.append("静态压力测量链不可信")
            if options.get("CHK-07") == "retest.residual_underboost" and not demo_complete:
                remaining.append("处理后仍存在残余增压不足")
            if handoff and terminal.get("reason"):
                remaining.append(terminal["reason"])
            unchecked = [
                action["title"] for area in areas for component in area["components"] for action in component["actions"]
                if action["status"] in {"locked", "not_started"}
            ]
            if demo_complete:
                recommendations = ["保留本次 synthetic 演示小结；正式最终报告仍受门禁控制"]
            elif handoff:
                recommendations = [terminal.get("reason") or "补充当前检查条件后重新开始"]
            else:
                recommendations = [protocol.get("presentation", {}).get("task_title") or
                                   (current or {}).get("candidate_json", {}).get("title") or "完成当前检查"]
            status_label = "演示诊断已完成" if demo_complete else "等待补充条件" if handoff else (
                f"正在检查{selected['title']}" if current_check else "正在恢复病例"
            )
            saved_facts = [{"id": str(row["id"]), "kind": row["kind"],
                            "check_id": (row["payload"] or {}).get("check_id"),
                            "summary": _fact_text(row), "created_revision": row["created_revision"]}
                           for row in effective]
            return {
                "case_summary": {"id": str(case_id), "title": "DKVB/P0299 诊断工作台",
                    "mode": case["diagnosis_mode"] or "conservative", "status_label": status_label,
                    "vehicle": vehicle, "fault_description": intake.get("fault_description") or case["fault_description"],
                    "fault_codes": intake.get("fault_codes") or case["fault_codes"],
                    "symptom_context": symptom, "synthetic": bool(intake.get("synthetic", True)),
                    "formal_usable": False},
                "areas": areas, "selected_area_id": selected_area_id,
                "current_component": current_component,
                "current_action": None if current is None else {
                    "step_id": str(current["id"]), "check_id": current_check,
                    "candidate": current["candidate_json"], "protocol": protocol,
                },
                "saved_facts": saved_facts,
                "synthesis": {"status": "demo_complete" if demo_complete else "handoff" if handoff else "in_progress",
                    "confirmed_facts": confirmed, "handled_issues": handled,
                    "remaining_abnormalities": remaining, "unchecked_items": unchecked,
                    "next_recommendations": recommendations,
                    "can_generate_demo_summary": demo_complete},
            }

    @staticmethod
    def _availability(area_id, current_check, completed, options, terminal_code):
        if area_id == "measurement-confirmation":
            return True, None
        if area_id == "charge-air-path":
            ready = "CHK-03" in completed or current_check in {"CHK-04", "CHK-05", "CHK-05-SUPPLEMENT", "CHK-06", "CHK-07"}
            return (ready, None if ready else "需先完成病例与测量确认")
        if area_id == "boost-control":
            ready = current_check in {"CHK-08", "CHK-09"} or "CHK-08" in completed or "CHK-09" in completed or options.get("CHK-07") == "retest.residual_underboost"
            return (ready, None if ready else "需先确认空气通路处理后仍有残余增压不足")
        if area_id == "conservative-handoff":
            ready = current_check == "CHK-10" or bool(terminal_code and terminal_code != "AREA_SUMMARY_DEMO_PASS")
            return (ready, None if ready else "仅在资料、测量或执行条件不足时开放")
        ready = current_check == "CHK-11" or "CHK-11" in completed or terminal_code == "AREA_SUMMARY_DEMO_PASS"
        return (ready, None if ready else "需先满足当前路径的最终复检条件")

    @staticmethod
    def _area_status(area_id, current_here, completed, options, abnormal_checks, handoff, demo_complete):
        if current_here:
            return "current"
        if area_id == "measurement-confirmation":
            if handoff and not {"CHK-03", "CHK-04"} & completed:
                return "handed_off"
            if {"CHK-00", "CHK-01", "CHK-02", "CHK-03"} <= completed:
                return "completed"
        if area_id == "charge-air-path" and "CHK-07" in completed:
            return "completed" if options.get("CHK-07") in {"retest.recovered", "retest.residual_underboost"} else "abnormal"
        if area_id == "boost-control" and {"CHK-08", "CHK-09"} <= completed:
            return "completed" if demo_complete else "abnormal"
        if area_id == "conservative-handoff" and handoff:
            return "handed_off"
        if area_id == "final-verification" and demo_complete:
            return "completed"
        area_checks = {check for check, mapped in CHECK_TO_AREA.items() if mapped == area_id}
        if area_checks & abnormal_checks:
            return "abnormal"
        available, _ = WorkbenchViewService._availability(area_id, None, completed, options, None)
        return "available" if available else "locked"
