"""Small, declarative option derivation for independently authored templates.

Only effective saved raw choices are inputs. This deliberately does not infer
vehicle-specific measurements, safety, or repair conclusions.
"""
from app.domain.policies import DomainError


def _invalid():
    raise DomainError("TEMPLATE_CALCULATION_INVALID", "模板派生规则配置无效", 409)


def validate(topic):
    catalog = topic.get("calculation_rules")
    if catalog is None:
        return []
    if not isinstance(catalog, dict) or catalog.get("version") != "choice-v1":
        _invalid()
    rules = catalog.get("rules")
    if not isinstance(rules, list) or len(rules) > 100:
        _invalid()
    questions = {q["id"]: q for q in topic["questions"]}
    seen = set()
    for rule in rules:
        if not isinstance(rule, dict):
            _invalid()
        target = rule.get("question_id")
        inputs = rule.get("inputs")
        cases = rule.get("cases")
        if (target in seen or target not in questions or
                questions[target]["answer_kind"] != "automatic_derived" or
                not isinstance(inputs, list) or not 0 < len(inputs) <= 30 or
                not all(isinstance(qid, str) for qid in inputs) or
                len(inputs) != len(set(inputs)) or
                not isinstance(cases, list) or not 0 < len(cases) <= 30):
            _invalid()
        seen.add(target)
        for qid in inputs:
            if qid not in questions or questions[qid]["answer_kind"] == "automatic_derived":
                _invalid()
        target_options = {o["id"] for o in questions[target]["options"]}
        for case in cases:
            if not isinstance(case, dict) or case.get("option_id") not in target_options:
                _invalid()
            clauses = case.get("when")
            if not isinstance(clauses, list) or not clauses or len(clauses) > len(inputs):
                _invalid()
            refs = set()
            for clause in clauses:
                if not isinstance(clause, dict):
                    _invalid()
                ref, options = clause.get("question_id"), clause.get("option_ids")
                if (not isinstance(ref, str) or ref not in inputs or ref in refs or
                        not isinstance(options, list) or not options or
                        not all(isinstance(option, str) for option in options) or
                        not set(options) <= {o["id"] for o in questions[ref]["options"]}):
                    _invalid()
                refs.add(ref)
    return rules


def evaluate(topic, effective):
    result = {}
    for rule in validate(topic):
        inputs = rule["inputs"]
        rows = [effective.get(qid) for qid in inputs]
        selected = None
        if all(rows):
            for case in rule["cases"]:
                if all(set(effective[c["question_id"]]["payload"].get("option_ids", [])) &
                       set(c["option_ids"]) for c in case["when"]):
                    selected = case
                    break
        result[rule["question_id"]] = {
            "question_id": rule["question_id"],
            "option_id": selected["option_id"] if selected else None,
            "reason": selected.get("reason", "按已保存记录计算。") if selected else
                      "输入未全部保存，或现有记录未命中已配置的计算条件。",
            "basis_observation_ids": [str(row["id"]) for row in rows if row],
            "detail": {"evidence_state": "computed" if selected else
                       "awaiting_input" if not all(rows) else "no_matching_rule"},
        }
    return result
