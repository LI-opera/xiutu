"""Answer validation driven only by the frozen template: options, fields, units, conditions."""
import math

from app.domain.policies import DomainError


def validate_number(definition, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise DomainError("NUMBER_INVALID", f"{definition['label']}需要有效数字", 422)
    if (definition.get("minimum") is not None and value < definition["minimum"]) or (definition.get("maximum") is not None and value > definition["maximum"]):
        raise DomainError("NUMBER_INVALID", f"{definition['label']}超出字段允许范围", 422)


def is_non_execution_answer(question, option_ids):
    """The single chosen option says the operation was not carried out (a bypass option)."""
    conditions = question.get("execution_conditions")
    return bool(conditions and len(option_ids) == 1 and
                option_ids[0] in conditions["bypass_options"])


def validate_answer(topic, plan, rows, body, original=None, *, effective):
    questions = {q["id"]: q for q in topic["questions"]}
    q = questions.get(body.question_id)
    if q is None:
        raise DomainError("QUESTION_UNKNOWN", "专题问题不存在", 422)
    if q["answer_kind"] == "automatic_derived":
        raise DomainError("QUESTION_DERIVED", "本问题由已保存的原始事实自动计算，不能手工提交", 422)
    if body.topic_version != topic["version"]:
        raise DomainError("TOPIC_VERSION_MISMATCH", "专题版本已变化，请重新加载", 409)
    if len(set(body.option_ids)) != len(body.option_ids) or (not body.option_ids and q["answer_kind"] != "multi_choice"):
        raise DomainError("OPTION_INVALID", "请选择有效的检查结果", 422)
    valid = {item["id"]: item for item in q["options"]}
    if any(option not in valid for option in body.option_ids):
        raise DomainError("OPTION_INVALID", "选项不属于此问题", 422)
    if q["answer_kind"] != "multi_choice" and len(body.option_ids) != 1:
        raise DomainError("OPTION_CARDINALITY", "此题只能选择一项", 422)
    if q["answer_kind"] == "multi_choice" and len(body.option_ids) > 1 and set(q.get("exclusive_options", [])) & set(body.option_ids):
        raise DomainError("OPTION_CONFLICT", "无此现象不能与具体项目同时选择", 422)
    if not body.option_ids and (body.fields or body.unavailable_reason.strip()):
        raise DomainError("OPTION_INVALID", "未选择时不能附带检查结果", 422)
    if body.note.strip() and len(body.note.strip()) < 2:
        raise DomainError("OBSERVATION_BASIS_REQUIRED", "观察依据过短", 422)
    field_defs = {field["id"]: field for field in q["fields"]}
    if any(name not in field_defs for name in body.fields):
        raise DomainError("FIELD_UNKNOWN", "存在不属于此题的字段", 422)
    unavailable = any(valid[o]["outcome"] == "unavailable" for o in body.option_ids)
    if q.get("execution_conditions") and is_non_execution_answer(q, body.option_ids):
        unavailable = True
    if unavailable and body.fields:
        raise DomainError("FIELD_NOT_APPLICABLE", "无法完成时不能附带不适用的测量字段", 422)
    recorded = bool(body.option_ids) and not unavailable
    fields = {}
    for name, definition in field_defs.items():
        raw = body.fields.get(name)
        if raw in (None, ""):
            if (definition.get("required_when_recorded") and recorded) or (set(definition.get("required_when_options", [])) & set(body.option_ids)):
                raise DomainError("FIELD_REQUIRED", f"请填写{definition['label']}", 422)
            continue
        allowed = definition.get("allowed_when_options")
        if allowed and not set(allowed) & set(body.option_ids):
            raise DomainError("FIELD_NOT_APPLICABLE", f"{definition['label']}不适用于当前选项", 422)
        if not isinstance(raw, dict) or "value" not in raw:
            raise DomainError("FIELD_INVALID", f"{definition['label']}字段格式无效", 422)
        value = raw["value"]
        unit = definition.get("unit")
        if raw.get("unit") != unit:
            raise DomainError("UNIT_MISMATCH", f"{definition['label']}单位不符", 422)
        if definition["type"] == "number":
            validate_number(definition, value)
        elif not isinstance(value, str) or not value.strip() or len(value) > 2000:
            raise DomainError("TEXT_INVALID", f"{definition['label']}内容无效", 422)
        fields[name] = {"value": value, "unit": unit}
    capture = q.get("capture") or {}
    if capture.get("batch_id_required") and not unavailable:
        expected = plan["capture_batches"].get(capture["batch_kind"])
        if body.batch_id != expected:
            raise DomainError("BATCH_MISMATCH", "采集批次不是当前病例的受控批次", 409)
    return q, fields, unavailable

