"""Frozen B01/B02 answer semantics; never applied solely because a question ID matches."""
import math

from app.domain.policies import DomainError


class LegacyAnswerRules:
    exclusive_options = ("none", "none_known")

    @staticmethod
    def validate_number(definition, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise DomainError("NUMBER_INVALID", f"{definition['label']}需要正数", 422)

    @staticmethod
    def validate_applicability(q, body):
        if q["id"] == "AIR-14" and "within_limit" not in body.option_ids and body.fields:
            raise DomainError("FIELD_NOT_APPLICABLE", "未执行或已安全停止时不能附带加压读数", 422)
        if q["id"] in {"PRS-02", "PRS-03"} and "signal_missing" in body.option_ids and body.fields:
            raise DomainError("FIELD_NOT_APPLICABLE", "信号缺失时不能附带压力读数", 422)

    @staticmethod
    def is_recorded(q, body, unavailable):
        return "recorded" in body.option_ids or (q["answer_kind"] == "conditional_operation" and not unavailable and (q["id"] != "AIR-14" or "within_limit" in body.option_ids))

    @staticmethod
    def validate_result(q, body, fields):
        if q["id"] == "AIR-14" and "within_limit" in body.option_ids and fields.get("pressureBar", {}).get("value", 1) > 0.5:
            raise DomainError("SAFETY_LIMIT", "专题演示检漏上限为0.5 bar；不能记录为安全完成", 422)
        if q["id"] == "RET-02" and "same_old_data" in body.option_ids:
            raise DomainError("RETEST_NEW_RECORD_REQUIRED", "复检不能沿用维修前数据", 422)

    @staticmethod
    def validate_retest(q, plan, rows, body, fields, effective):
        if q["id"] == "RET-04":
            expected_batch = plan["rounds"][-1]["batch_id"]
            if fields.get("new_batch_id") and fields["new_batch_id"]["value"] != expected_batch:
                raise DomainError("RETEST_BATCH_MISMATCH", "新复检批次与服务端轮次不一致", 409)
            fields["new_batch_id"] = {"value": expected_batch, "unit": None}
            if body.option_ids[0] in {"recovered", "still_underboost", "intermittent"}:
                if len(body.retest_frames) != 3:
                    raise DomainError("RETEST_FRAMES_REQUIRED", "请记录新的三帧可比测量", 422)
                comparable = effective(rows, "RET-03", plan["rounds"][-1]["id"])
                if comparable is None or "comparable" not in comparable["payload"]["option_ids"]:
                    raise DomainError("RETEST_COMPARABILITY_REQUIRED", "请先确认复检工况可比", 422)
                before = [effective(rows, f"PRS-{i:02}", None) for i in (8, 9, 10)]
                if not all(before) or any("recorded" not in row["payload"]["option_ids"] for row in before):
                    raise DomainError("BEFORE_FRAMES_REQUIRED", "维修前可比三帧不完整，不能形成前后比较", 422)
                gaps = []
                for frame in body.retest_frames:
                    for field in ("rpm", "load", "target", "actual"):
                        value = frame.get(field)
                        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                            raise DomainError("RETEST_FRAME_INVALID", f"复检帧缺少有效{field}", 422)
                    for field in ("request", "gear", "captured_at"):
                        if not isinstance(frame.get(field), str) or not frame[field].strip():
                            raise DomainError("RETEST_FRAME_INVALID", f"复检帧缺少{field}", 422)
                    gaps.append(frame["target"] - frame["actual"])
                if len({frame["gear"] for frame in body.retest_frames}) != 1 or len({frame["request"] for frame in body.retest_frames}) != 1:
                    raise DomainError("RETEST_FRAME_INCOMPARABLE", "三帧挡位与驾驶请求不一致", 422)
                classified = "recovered" if all(abs(gap) <= 150 for gap in gaps) else "still_underboost" if all(gap > 250 for gap in gaps) else "intermittent" if any(gap > 250 for gap in gaps) and any(abs(gap) <= 150 for gap in gaps) else None
                if classified != body.option_ids[0]:
                    raise DomainError("RETEST_CLASSIFICATION_MISMATCH", "所选结果与已记录三帧不一致；无法分类时请记录数据不可信或补充检查", 422)


def legacy_rules_for(topic):
    catalog = topic.get("calculation_catalog")
    if catalog is not None:
        from app.services.template_legacy_calculations import supports

        return LegacyAnswerRules if supports(topic) else None
    # Direct B01/B02 cases predate template snapshots and have no catalog.
    if (topic.get("topic_id") == "tanyue-dkvb-p0299-demo-v2"
            and topic.get("version") in {"2.2.0-b01", "2.2.1-b02"}):
        return LegacyAnswerRules
    return None


def effective_legacy_observation(rows, question_id, round_id):
    """Historical RET question instances are scoped to a treatment round."""
    superseded = {row["supersedes_id"] for row in rows if row["supersedes_id"]}
    matches = [row for row in rows if row["id"] not in superseded and
               row["payload"]["question_id"] == question_id and
               (row["payload"].get("round_id") if question_id.startswith("RET-") else None) == round_id]
    return matches[-1] if matches else None
