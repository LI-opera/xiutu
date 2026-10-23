"""Data-driven observation and treatment workflow for a frozen topic."""
from uuid import uuid4

from app.domain.policies import DomainError


class ObservationWorkflow:
    def __init__(self, topic):
        self.topic = topic
        config = topic.get("observation_workflow") or {}
        self.repair_id = config.get("repair_question_id")
        self.retest_stage = config.get("retest_stage")
        self.none_options = set(config.get("no_action_options", []))
        self.safety_id = config.get("safety_question_id")
        self.batch_start_config = config.get("new_batch_on_answer")
        self.before_batch_kind = config.get("before_batch_kind")
        if not self.repair_id and self.retest_stage or self.repair_id and not self.retest_stage:
            raise DomainError("TEMPLATE_WORKFLOW_INVALID", "实际处理与复检轮次须一同配置", 409)
        if self.repair_id:
            starter = next((q for q in topic["questions"] if q["id"] == self.repair_id), None)
            if not starter or starter["stage"] != self.retest_stage:
                raise DomainError("TEMPLATE_WORKFLOW_INVALID", "实际处理题目不属于配置的复检阶段", 409)

    def round_scoped(self, question):
        return bool(self.retest_stage and question["stage"] == self.retest_stage)

    def effective(self, rows, question_id, round_id):
        questions = {q["id"]: q for q in self.topic["questions"]}
        question = questions.get(question_id)
        if not question:
            return None
        superseded = {row["supersedes_id"] for row in rows if row["supersedes_id"]}
        matches = [row for row in rows if row["id"] not in superseded and
                   row["payload"]["question_id"] == question_id and
                   (row["payload"].get("round_id") if self.round_scoped(question) else None) == round_id]
        return matches[-1] if matches else None

    def initial_round(self, question, plan, body):
        current = plan["rounds"][-1]["id"] if plan["rounds"] else None
        if self.round_scoped(question) and question["id"] != self.repair_id:
            if not current or body.round_id != current:
                raise DomainError("RETEST_ROUND_REQUIRED", "请先记录实际处理并开始独立复检轮次", 409)
        elif not self.round_scoped(question) and body.round_id:
            raise DomainError("ROUND_MISMATCH", "处理前观察不能写入复检轮次", 422)
        return current if self.round_scoped(question) else None

    def allow_new_record(self, question, existing, plan, body):
        if existing and question["id"] != self.repair_id:
            raise DomainError("ALREADY_RECORDED", "此题已有有效记录，请使用更正入口", 409)

    def begin_round(self, plan, existing, option_ids, original_id):
        previous = existing["payload"].get("round_id") if existing else None
        actual_repair = any(option not in self.none_options for option in option_ids)
        if actual_repair and (original_id is None or not previous):
            round_id = str(uuid4())
            entry = {"id": round_id, "batch_id": str(uuid4())}
            if self.before_batch_kind:
                entry["before_batch_id"] = plan["capture_batches"][self.before_batch_kind]
            plan["rounds"].append(entry)
            return round_id
        return previous if original_id else plan["rounds"][-1]["id"] if plan["rounds"] else None

    def prerequisites(self, question, plan, rows, body):
        if question["answer_kind"] != "conditional_operation":
            return []
        conditions = question.get("execution_conditions")
        if conditions:
            if len(body.option_ids) == 1 and body.option_ids[0] in conditions["bypass_options"]:
                return []
            missing = []
            for requirement in conditions["requirements"]:
                intake_key = requirement.get("intake_key")
                ref = requirement.get("ref") or f"intake:{intake_key}"
                if intake_key:
                    value = plan.get("intake", {}).get(intake_key)
                    actual = [value] if value else []
                else:
                    record = self.effective(rows, ref, None)
                    actual = record["payload"]["option_ids"] if record else []
                if not set(actual) & set(requirement["allowed"]):
                    actual_text = "、".join(actual) if actual else "未记录"
                    missing.append({"ref": ref, "expected": requirement["allowed"],
                                    "actual": actual_text,
                                    "reason": f"{ref}：需{requirement['label']}；当前为{actual_text}"})
            return missing
        if set(body.option_ids) & set(question.get("bypass_options", [])):
            return []
        missing = []
        for ref in question["prerequisites"]["refs"]:
            if not self.effective(rows, ref, None):
                missing.append(ref + " 尚未记录")
        return missing

    def after_answer(self, question, body, plan):
        if question["id"] == self.safety_id:
            plan["intake"]["safety_gate"] = body.option_ids[0]
        if self.batch_start_config:
            rule = self.batch_start_config
            if question["id"] == rule["question_id"] and rule["option_id"] in body.option_ids:
                plan["capture_batches"][rule["batch_kind"]] = str(uuid4())


def workflow_for(topic):
    return ObservationWorkflow(topic)
