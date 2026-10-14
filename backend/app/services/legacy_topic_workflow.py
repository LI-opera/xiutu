"""Frozen B01/B02 observation, prerequisite and treatment-round semantics."""
from uuid import uuid4

from app.domain.policies import DomainError
from app.services.workbench_b02_conditions import blockers, is_non_execution_answer
from app.services.workbench_topic_workflow import ObservationWorkflow
from app.topics import dkvb_b02


class LegacyObservationWorkflow(ObservationWorkflow):
    def __init__(self, topic, *, template_bound=False):
        super().__init__({**topic, "observation_workflow": {}}, template_bound=template_bound)
        self.repair_id = "RET-01"
        self.retest_stage = "S6"
        self.none_options = {"none"}
        self.safety_id = "IN-08" if template_bound else None
        self.before_batch_kind = "comparable_load_frames"

    def allow_new_record(self, question, existing, plan, body):
        direct_b02 = self.topic['version'] == dkvb_b02.TOPIC_VERSION and not self.template_bound
        if existing and (question["id"] != self.repair_id or
                         direct_b02 and (not plan["rounds"] or body.option_ids == ["none"])):
            raise DomainError("ALREADY_RECORDED", "此题已有有效记录，请使用更正入口", 409)

    def prerequisites(self, question, plan, rows, body, *, show_labels=True):
        if question["answer_kind"] != "conditional_operation":
            return []
        if question.get("execution_conditions"):
            if is_non_execution_answer(question, body.option_ids):
                return []
            answers = {}
            for ref in question["prerequisites"]["refs"]:
                if ref != "IN-08":
                    record = self.effective(rows, ref, None)
                    answers[ref] = record["payload"]["option_ids"] if record else []
            return blockers(question, answers, plan["intake"],
                            {item["id"]: item for item in self.topic["questions"]} if show_labels else None)
        if any(o in {"unavailable", "not_performed", "not_accessible", "unsafe_stop"} for o in body.option_ids):
            return []
        missing = []
        for ref in question["prerequisites"]["refs"]:
            if ref == "IN-08":
                if plan["intake"]["safety_gate"] in {"stop_now", "unavailable"}:
                    missing.append("IN-08：安全条件未确认")
                continue
            record = self.effective(rows, ref, None)
            if not record:
                missing.append(ref + " 尚未记录")
        if question["id"] in {"AIR-14", "AIR-15"}:
            prior = self.effective(rows, "AIR-13", None)
            if prior and not set(prior["payload"]["option_ids"]) & {"available", "alternative_safe_tool"}:
                missing.append("AIR-13：缺少安全检漏工具")
        if question["id"] == "ACT-10":
            prior = self.effective(rows, "ACT-09", None)
            if prior and "completed" not in prior["payload"]["option_ids"]:
                missing.append("ACT-09：设置尚未完成")
        return missing

    def after_answer(self, question, body, plan):
        if question["id"] == self.safety_id:
            plan["intake"]["safety_gate"] = body.option_ids[0]
        if question["id"] == "ACT-09" and "completed" in body.option_ids:
            plan["capture_batches"]["after_setting_new_batch"] = str(uuid4())

    def retest_frames(self, question, body):
        return body.retest_frames if question["id"] == "RET-04" else []
