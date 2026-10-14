"""Bounded, optional observation rules for independently published templates.

These rules suggest focus and report conflicts. They never hide questions,
require every question before analysis, or turn an absent answer into a fact.
"""
from app.domain.policies import DomainError

VERSION = "observation-v1"


def _invalid():
    raise DomainError("TEMPLATE_OBSERVATION_RULE_INVALID", "模板观察规则配置无效", 409)


def _predicates(items, questions):
    if not isinstance(items, list) or not 1 <= len(items) <= 20:
        _invalid()
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"question_id", "option_ids"}:
            _invalid()
        qid = item["question_id"]
        options = item["option_ids"]
        if (not isinstance(qid, str) or qid in seen or qid not in questions or
                questions[qid]["answer_kind"] == "automatic_derived" or
                not isinstance(options, list) or not options or len(options) > 20 or
                not all(isinstance(value, str) for value in options) or
                len(options) != len(set(options)) or
                not set(options) <= {option["id"] for option in questions[qid]["options"]}):
            _invalid()
        seen.add(qid)


def validate(topic):
    questions = {q["id"]: q for q in topic["questions"]}
    for q in questions.values():
        option_ids = {o["id"] for o in q["options"]}
        for field in q.get("fields", []):
            for key in ("allowed_when_options", "required_when_options"):
                configured = field.get(key)
                if configured is None:
                    continue
                if (not isinstance(configured, list) or not configured or
                        not all(isinstance(value, str) for value in configured) or
                        len(configured) != len(set(configured)) or not set(configured) <= option_ids):
                    _invalid()
            allowed = field.get("allowed_when_options")
            required = field.get("required_when_options")
            if allowed and required and not set(required) <= set(allowed):
                _invalid()
            recorded_options = {o["id"] for o in q["options"] if o["outcome"] != "unavailable"}
            if allowed and field.get("required_when_recorded") and not recorded_options <= set(allowed):
                _invalid()
        conditions = q.get("execution_conditions")
        if conditions is None:
            continue
        if (q["answer_kind"] != "conditional_operation" or not isinstance(conditions, dict) or
                set(conditions) != {"requirements", "bypass_options"}):
            _invalid()
        bypass = conditions["bypass_options"]
        if (not isinstance(bypass, list) or not bypass or len(bypass) > 20 or
                not all(isinstance(value, str) for value in bypass) or
                len(bypass) != len(set(bypass)) or
                not set(bypass) <= {o["id"] for o in q["options"] if o["outcome"] == "unavailable"}):
            _invalid()
        requirements = conditions["requirements"]
        if not isinstance(requirements, list) or not 1 <= len(requirements) <= 20:
            _invalid()
        refs = set()
        for requirement in requirements:
            if (not isinstance(requirement, dict) or
                    set(requirement) not in ({"ref", "allowed", "label"},
                                             {"intake_key", "allowed", "label"})):
                _invalid()
            ref = requirement.get("ref")
            intake_key = requirement.get("intake_key")
            if ref is not None and not isinstance(ref, str):
                _invalid()
            identity = ref or f"intake:{intake_key}"
            allowed = requirement["allowed"]
            label = requirement["label"]
            if (identity in refs or
                    not isinstance(label, str) or not 1 <= len(label) <= 200 or
                    not isinstance(allowed, list) or not allowed or len(allowed) > 20 or
                    not all(isinstance(value, str) for value in allowed) or
                    len(allowed) != len(set(allowed))):
                _invalid()
            if ref is not None:
                if (not isinstance(ref, str) or ref == q["id"] or ref not in questions or
                        questions[ref]["answer_kind"] == "automatic_derived" or
                        not set(allowed) <= {o["id"] for o in questions[ref]["options"]}):
                    _invalid()
            elif intake_key != "safety_gate" or not set(allowed) <= {"none", "caution", "stop_now", "unavailable", "unprovided"}:
                _invalid()
            refs.add(identity)
    catalog = topic.get("observation_rules")
    if catalog is None:
        return None
    if not isinstance(catalog, dict) or set(catalog) != {"version", "focus_rules", "conflict_rules"} or catalog["version"] != VERSION:
        _invalid()
    identifiers = set()
    for kind in ("focus_rules", "conflict_rules"):
        rules = catalog[kind]
        if not isinstance(rules, list) or len(rules) > 100:
            _invalid()
        for rule in rules:
            expected = {"id", "all", "question_ids"} if kind == "focus_rules" else {"id", "all", "reason"}
            if not isinstance(rule, dict) or set(rule) != expected:
                _invalid()
            rid = rule["id"]
            if not isinstance(rid, str) or not rid or rid in identifiers:
                _invalid()
            identifiers.add(rid)
            _predicates(rule["all"], questions)
            if kind == "focus_rules":
                targets = rule["question_ids"]
                if (not isinstance(targets, list) or not 1 <= len(targets) <= 30 or
                        not all(isinstance(qid, str) and qid in questions and
                                questions[qid]["answer_kind"] != "automatic_derived" for qid in targets) or
                        len(targets) != len(set(targets))):
                    _invalid()
            elif not isinstance(rule["reason"], str) or not 2 <= len(rule["reason"]) <= 500:
                _invalid()
    return catalog


def evaluate(topic, effective):
    catalog = validate(topic)
    if catalog is None:
        return {"focus_question_ids": [], "matched_rule_ids": [], "conflicts": []}
    focused, matched, conflicts = [], [], []
    for kind in ("focus_rules", "conflict_rules"):
        for rule in catalog[kind]:
            rows = [effective.get(item["question_id"]) for item in rule["all"]]
            if any(row is None or not set(row["payload"].get("option_ids") or []) & set(item["option_ids"])
                   for row, item in zip(rows, rule["all"])):
                continue
            matched.append(rule["id"])
            if kind == "focus_rules":
                focused.extend(rule["question_ids"])
            else:
                conflicts.append({"id": rule["id"], "reason": rule["reason"],
                                  "question_ids": [item["question_id"] for item in rule["all"]],
                                  "basis_observation_ids": [str(row["id"]) for row in rows]})
    return {"focus_question_ids": list(dict.fromkeys(focused)),
            "matched_rule_ids": matched, "conflicts": conflicts}
