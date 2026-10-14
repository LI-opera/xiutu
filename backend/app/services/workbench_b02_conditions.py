"""B02 conditional-operation interpreter shared by write validation and view projection."""


def is_non_execution_answer(question, option_ids):
    conditions = question.get("execution_conditions")
    return bool(conditions and len(option_ids) == 1 and
                option_ids[0] in conditions["bypass_options"])


def blockers(question, answers, intake, questions=None):
    conditions = question.get("execution_conditions")
    if not conditions:
        return []
    missing = []
    for requirement in conditions["requirements"]:
        ref = requirement["ref"]
        actual = ([intake.get("safety_gate")] if ref == "IN-08" else answers.get(ref, []))
        if not set(actual) & set(requirement["allowed"]):
            labels = {option["id"]: option["label"] for option in
                      (questions or {}).get(ref, {}).get("options", [])}
            actual_text = "、".join(labels.get(option, option) for option in actual) if actual and actual[0] else "未记录"
            missing.append({"ref": ref, "expected": requirement["allowed"],
                            "actual": actual_text,
                            "reason": f"{ref}：需{requirement['label']}；当前为{actual_text}"})
    return missing
