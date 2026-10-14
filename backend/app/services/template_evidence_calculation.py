"""Bounded, data-only evidence calculations for independent template versions.

Only effective saved observations are inputs. The rule catalog supplies all
question IDs, fields, units, batch kinds, bands and output options.
"""
import math

from app.domain.policies import DomainError

VERSION = "evidence-v1"
NUMERIC_OPERATORS = {"numeric_reference_consistency", "numeric_series_gap"}
LOGIC_OPERATORS = {"evidence_gate", "independent_group_count", "direction_set"}
OPERATORS = NUMERIC_OPERATORS | LOGIC_OPERATORS


def _invalid():
    raise DomainError("TEMPLATE_CALCULATION_INVALID", "模板派生规则配置无效", 409)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _qid(item):
    return item.get("question_id") if isinstance(item, dict) else None


def _validate_input(item, questions, batch_kind, field_names):
    qid = _qid(item)
    if not isinstance(qid, str):
        _invalid()
    question = questions.get(qid)
    if not question or question["answer_kind"] == "automatic_derived":
        _invalid()
    if (question.get("capture") or {}).get("batch_kind") != batch_kind or not (question.get("capture") or {}).get("batch_id_required"):
        _invalid()
    fields = {field["id"]: field for field in question.get("fields", [])}
    for name in field_names:
        field_id = item.get(name)
        if not isinstance(field_id, str) or field_id not in fields or fields[field_id].get("type") != "number":
            _invalid()
    valid_options = item.get("valid_option_ids")
    if (not isinstance(valid_options, list) or not valid_options or
            not all(isinstance(option, str) for option in valid_options) or
            len(set(valid_options)) != len(valid_options) or
            not set(valid_options) <= {option["id"] for option in question["options"]}):
        _invalid()


def _validate_predicate(predicate, questions, previous_rules):
    if not isinstance(predicate, dict) or len(predicate) != 2:
        _invalid()
    source = predicate.get("question_id")
    rule_id = predicate.get("result_id")
    options = predicate.get("option_ids")
    if (bool(source) == bool(rule_id) or
            (source is not None and (not isinstance(source, str) or not source)) or
            (rule_id is not None and (not isinstance(rule_id, str) or not rule_id)) or
            not isinstance(options, list) or
            not options or len(options) > 20 or
            not all(isinstance(option, str) and option for option in options) or
            len(options) != len(set(options))):
        _invalid()
    if source:
        question = questions.get(source)
        if not question or question["answer_kind"] == "automatic_derived" or not set(options) <= {
            option["id"] for option in question["options"]
        }:
            _invalid()
    elif rule_id not in previous_rules or not set(options) <= previous_rules[rule_id]:
        _invalid()


def _validate_logic(rule, questions, previous_rules, target_options):
    operator = rule["operator"]
    outputs = rule.get("outputs")
    if not isinstance(outputs, dict):
        _invalid()
    if operator == "evidence_gate":
        conditions = rule.get("all")
        if not isinstance(conditions, list) or not 1 <= len(conditions) <= 20:
            _invalid()
        for predicate in conditions:
            _validate_predicate(predicate, questions, previous_rules)
        if set(outputs) != {"supported"} or not isinstance(outputs["supported"], str):
            _invalid()
    else:
        groups = rule.get("groups")
        if not isinstance(groups, list) or not 1 <= len(groups) <= 20:
            _invalid()
        ids = set()
        for group in groups:
            if (not isinstance(group, dict) or not isinstance(group.get("id"), str) or
                    not group["id"] or group["id"] in ids or
                    ("all" in group) == ("any" in group)):
                _invalid()
            ids.add(group["id"])
            predicates = group.get("all", group.get("any"))
            if not isinstance(predicates, list) or not 1 <= len(predicates) <= 20:
                _invalid()
            for predicate in predicates:
                _validate_predicate(predicate, questions, previous_rules)
        if operator == "independent_group_count":
            parameters = rule.get("parameters")
            if (set(outputs) != {"below_threshold", "multiple"} or
                    not isinstance(parameters, dict) or
                    not isinstance(parameters.get("minimum_multiple"), int) or
                    isinstance(parameters["minimum_multiple"], bool) or
                    not 2 <= parameters["minimum_multiple"] <= len(groups)):
                _invalid()
        elif set(outputs) != ids | {"multiple"}:
            _invalid()
        if not all(isinstance(option, str) for option in outputs.values()):
            _invalid()
    if target_options is None:
        if operator != "evidence_gate" or outputs["supported"] != "supported":
            _invalid()
    elif not set(outputs.values()) <= target_options:
        _invalid()
    return set(outputs.values())


def validate(topic):
    catalog = topic.get("calculation_rules")
    if not isinstance(catalog, dict) or catalog.get("version") != VERSION:
        _invalid()
    rules = catalog.get("rules")
    if not isinstance(rules, list) or len(rules) > 100:
        _invalid()
    questions = {question["id"]: question for question in topic["questions"]}
    targets, previous_rules = set(), {}
    for rule in rules:
        if (not isinstance(rule, dict) or not isinstance(rule.get("operator"), str) or
                rule["operator"] not in OPERATORS):
            _invalid()
        target = rule.get("target_question_id")
        if target is not None and not isinstance(target, str):
            _invalid()
        question = questions.get(target) if isinstance(target, str) else None
        if (not isinstance(rule.get("id"), str) or not rule["id"] or rule["id"] in previous_rules or
                (target is not None and (target in targets or not question or
                                         question["answer_kind"] != "automatic_derived")) or
                (target is None and rule["operator"] != "evidence_gate")):
            _invalid()
        target_options = {option["id"] for option in question["options"]} if question else None
        reasons = rule.get("reasons", {})
        if (not isinstance(reasons, dict) or
                (target_options is None and reasons) or
                (target_options is not None and not set(reasons) <= target_options) or
                not all(isinstance(reason, str) and 0 < len(reason) <= 500 for reason in reasons.values())):
            _invalid()
        if rule["operator"] in LOGIC_OPERATORS:
            output_ids = _validate_logic(rule, questions, previous_rules, target_options)
            previous_rules[rule["id"]] = output_ids
            if target is not None:
                targets.add(target)
            continue
        if target is None:
            _invalid()
        batch_kind = rule.get("same_batch_kind")
        inputs = rule.get("inputs")
        unit = rule.get("unit")
        options = rule.get("outputs")
        parameters = rule.get("parameters")
        if (not isinstance(batch_kind, str) or not batch_kind or
                not isinstance(unit, str) or not unit or
                not isinstance(inputs, list) or not 2 <= len(inputs) <= 20 or
                not all(isinstance(item, dict) and isinstance(_qid(item), str) for item in inputs) or
                len({_qid(item) for item in inputs}) != len(inputs) or
                not isinstance(options, dict) or not isinstance(parameters, dict)):
            _invalid()
        if rule["operator"] == "numeric_reference_consistency":
            if (not _number(parameters.get("max_difference")) or parameters["max_difference"] < 0 or
                    set(options) != {"consistent", "single_outlier", "multiple_outliers"} or
                    not isinstance(options["single_outlier"], dict) or
                    set(options["single_outlier"]) != {_qid(item) for item in inputs[1:]} or
                    not all(isinstance(value, str) for value in options["single_outlier"].values()) or
                    not isinstance(options["consistent"], str) or
                    not isinstance(options["multiple_outliers"], str) or
                    options["consistent"] not in target_options or
                    options["multiple_outliers"] not in target_options or
                    not set(options["single_outlier"].values()) <= target_options):
                _invalid()
            for item in inputs:
                _validate_input(item, questions, batch_kind, ("field",))
                field = next(field for field in questions[item["question_id"]]["fields"] if field["id"] == item["field"])
                if field.get("unit") != unit:
                    _invalid()
        else:
            if (not _number(parameters.get("close_abs_max")) or parameters["close_abs_max"] < 0 or
                    not _number(parameters.get("large_positive_min")) or
                    parameters["large_positive_min"] <= parameters["close_abs_max"] or
                    set(options) != {"tracks", "persistent_positive_gap", "intermittent_positive_gap"} or
                    not all(isinstance(value, str) for value in options.values()) or
                    not set(options.values()) <= target_options):
                _invalid()
            gate = rule.get("comparability_gate")
            if (not isinstance(gate, dict) or not isinstance(gate.get("question_id"), str) or
                    gate["question_id"] not in questions or
                    questions[gate["question_id"]]["answer_kind"] == "automatic_derived" or
                    not isinstance(gate.get("allowed_option_ids"), list) or not gate["allowed_option_ids"] or
                    not all(isinstance(option, str) for option in gate["allowed_option_ids"]) or
                    not set(gate["allowed_option_ids"]) <=
                    {option["id"] for option in questions[gate["question_id"]]["options"]}):
                _invalid()
            for item in inputs:
                _validate_input(item, questions, batch_kind, ("target_field", "actual_field"))
                fields = {field["id"]: field for field in questions[item["question_id"]]["fields"]}
                if fields[item["target_field"]].get("unit") != unit or fields[item["actual_field"]].get("unit") != unit:
                    _invalid()
        previous_rules[rule["id"]] = ({options["consistent"], options["multiple_outliers"]} |
                                      set(options["single_outlier"].values()) if rule["operator"] == "numeric_reference_consistency"
                                      else set(options.values()))
        targets.add(target)
    return rules


def _predicate_state(predicate, effective, prior):
    if "question_id" in predicate:
        row = effective.get(predicate["question_id"])
        if not row:
            return None, []
        selected = set(row["payload"].get("option_ids") or [])
        return bool(selected & set(predicate["option_ids"])), [str(row["id"])]
    source = prior[predicate["result_id"]]
    selected = source["option_id"]
    return (selected in predicate["option_ids"] if selected is not None else None,
            source["basis_observation_ids"])


def _conditions_state(predicates, mode, effective, prior):
    outcomes = [_predicate_state(predicate, effective, prior) for predicate in predicates]
    basis = list(dict.fromkeys(identifier for _, identifiers in outcomes for identifier in identifiers))
    states = [state for state, _ in outcomes]
    if mode == "all":
        decision = False if False in states else None if None in states else True
    else:
        decision = True if True in states else None if None in states else False
    return decision, basis


def _evaluate_logic(rule, effective, prior):
    operator = rule["operator"]
    basis = []
    detail = {"rule_id": rule["id"], "rule_version": VERSION}
    selected = None
    if operator == "evidence_gate":
        state, basis = _conditions_state(rule["all"], "all", effective, prior)
        if state is True:
            selected = rule["outputs"]["supported"]
        detail["evidence_state"] = "computed" if state is True else "awaiting_input" if state is None else "insufficient"
    else:
        matched, unknown = [], []
        for group in rule["groups"]:
            mode = "all" if "all" in group else "any"
            state, group_basis = _conditions_state(group[mode], mode, effective, prior)
            basis.extend(group_basis)
            if state is True:
                matched.append(group["id"])
            elif state is None:
                unknown.append(group["id"])
        basis = list(dict.fromkeys(basis))
        detail.update({"matched_group_ids": matched, "unknown_group_ids": unknown})
        if operator == "independent_group_count":
            selected = (rule["outputs"]["multiple"] if len(matched) >= rule["parameters"]["minimum_multiple"] else
                        rule["outputs"]["below_threshold"] if matched else None)
        else:
            selected = (rule["outputs"]["multiple"] if len(matched) >= 2 else
                        rule["outputs"][matched[0]] if matched else None)
        detail["evidence_state"] = "computed" if matched else "awaiting_input" if unknown else "no_support"
    target = rule.get("target_question_id")
    return {"question_id": target, "option_id": selected,
            "reason": (rule.get("reasons", {}).get(selected, "按已保存记录及模板规则计算。") if selected else
                       "所需证据缺失或未命中模板条件；不能自动分类。"),
            "basis_observation_ids": basis, "detail": detail}


def evaluate(topic, effective, plan):
    result = {}
    prior = {}
    batches = plan.get("capture_batches", {})
    for rule in validate(topic):
        if rule["operator"] in LOGIC_OPERATORS:
            calculated = _evaluate_logic(rule, effective, prior)
            prior[rule["id"]] = calculated
            if rule.get("target_question_id"):
                result[rule["target_question_id"]] = calculated
            continue
        inputs = rule["inputs"]
        rows = [effective.get(item["question_id"]) for item in inputs]
        gate = rule.get("comparability_gate")
        gate_row = effective.get(gate["question_id"]) if gate else None
        basis = [str(row["id"]) for row in [*rows, gate_row] if row]
        state = "computed"
        values = []
        for item, row in zip(inputs, rows):
            if not row:
                state = "awaiting_input"
                break
            payload = row["payload"]
            names = ("field",) if rule["operator"] == "numeric_reference_consistency" else ("target_field", "actual_field")
            measured = []
            for name in names:
                field = (payload.get("fields") or {}).get(item[name]) or {}
                if not _number(field.get("value")) or field.get("unit") != rule["unit"]:
                    state = "insufficient"
                    break
                measured.append(field["value"])
            if state != "computed":
                break
            expected_batch = batches.get(rule["same_batch_kind"])
            if (not set(payload.get("option_ids", [])) & set(item["valid_option_ids"]) or
                    not expected_batch or payload.get("batch_id") != expected_batch):
                state = "insufficient"
                break
            values.append(measured)
        if state == "computed" and gate:
            if not gate_row:
                state = "awaiting_input"
            elif not set(gate_row["payload"].get("option_ids", [])) & set(gate["allowed_option_ids"]):
                state = "insufficient"
        selected = None
        detail = {"rule_id": rule["id"], "rule_version": VERSION, "evidence_state": state}
        if state == "computed" and rule["operator"] == "numeric_reference_consistency":
            reference = values[0][0]
            band = rule["parameters"]["max_difference"]
            outliers = [item["question_id"] for item, value in zip(inputs[1:], values[1:])
                        if abs(value[0] - reference) > band]
            if not outliers and max(value[0] for value in values) - min(value[0] for value in values) > band:
                # A full-spread conflict cannot be called consistent merely
                # because each comparator is close to the reference.
                selected = rule["outputs"]["multiple_outliers"]
            else:
                selected = (rule["outputs"]["consistent"] if not outliers else
                            rule["outputs"]["single_outlier"][outliers[0]] if len(outliers) == 1 else
                            rule["outputs"]["multiple_outliers"])
            detail["outlier_question_ids"] = outliers
        elif state == "computed":
            gaps = [pair[0] - pair[1] for pair in values]
            close = rule["parameters"]["close_abs_max"]
            large = rule["parameters"]["large_positive_min"]
            if all(abs(gap) <= close for gap in gaps):
                selected = rule["outputs"]["tracks"]
            elif all(gap > large for gap in gaps):
                selected = rule["outputs"]["persistent_positive_gap"]
            elif any(gap > large for gap in gaps) and any(abs(gap) <= close for gap in gaps):
                selected = rule["outputs"]["intermittent_positive_gap"]
            else:
                detail["evidence_state"] = "no_matching_rule"
            detail["gaps"] = gaps
        calculated = {
            "question_id": rule["target_question_id"], "option_id": selected,
            "reason": rule.get("reasons", {}).get(selected, "按同批次已保存数值及模板规则计算。") if selected else
                      "输入未保存、不可信或未命中模板判别条件；不能自动分类。",
            "basis_observation_ids": basis, "detail": detail,
        }
        prior[rule["id"]] = calculated
        result[rule["target_question_id"]] = calculated
    return result
