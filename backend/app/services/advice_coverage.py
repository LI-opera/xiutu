"""Which abnormal saved records an AI advice leaves without any action.

A model sometimes mentions a recorded abnormal result only in passing, or even describes it as
"not recorded". This check is mechanical and model-free: every saved record whose selected option
is abnormal (by the template's option outcome) must be referenced by an action (a step or a
conditional-branch step, through question_ids or basis_observation_ids) or by a missing-fact entry.
Directions do not count: they are competing explanations, not a plan. The result is shown to the
user next to the advice; it never changes or blocks the advice itself.
"""


def abnormal_option_ids(questions):
    """question id -> option ids whose outcome is abnormal."""
    return {q["id"]: {o["id"] for o in q.get("options", []) if o.get("outcome") == "abnormal"}
            for q in questions}


def unplanned_records(result, observations, questions):
    """Saved abnormal records no action or missing-fact entry refers to, in record order."""
    if not result:
        return []
    abnormal = abnormal_option_ids(questions)
    actions = list(result.get("steps") or [])
    for branch in result.get("conditional_branches") or []:
        actions += branch.get("steps") or []
    covered_ids = {str(i) for a in actions for i in a.get("basis_observation_ids") or []}
    covered_questions = {q for a in actions for q in a.get("question_ids") or []}
    covered_questions |= {m.get("question_id") for m in result.get("missing") or []}
    found = []
    for record in observations:
        if not set(record.get("option_ids") or []) & abnormal.get(record["question_id"], set()):
            continue
        if str(record["id"]) in covered_ids or record["question_id"] in covered_questions:
            continue
        found.append({"observation_id": str(record["id"]), "question_id": record["question_id"],
                      "question": record.get("question"), "option_labels": record.get("option_labels", [])})
    return found
