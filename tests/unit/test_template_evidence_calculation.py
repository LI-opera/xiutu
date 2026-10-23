"""Independent numeric template rules keep saved facts and uncertainty separate."""
import json
from uuid import uuid4

import pytest
from app.domain.policies import DomainError
from app.services.template_projection import build_plan, project_template

from scripts.seed_workbench_templates import build_templates


def question(qid, kind, options, *, fields=(), batch=None):
    return {"id": qid, "area_id": "cooling", "answer_kind": kind,
            "options": [{"id": option, "outcome": "normal"} for option in options],
            "fields": [{"id": field, "type": "number", "unit": "kPa"} for field in fields],
            "capture": {"batch_kind": batch, "batch_id_required": True} if batch else {}}


def row(qid, fields, batch, *, option="recorded", supersedes=None, unit="kPa"):
    return {"id": uuid4(), "supersedes_id": supersedes,
            "payload": {"question_id": qid, "option_ids": [option], "batch_id": batch,
                        "fields": {name: {"value": value, "unit": unit} for name, value in fields.items()}}}


def static_topic():
    inputs = [{"question_id": qid, "field": "reading", "valid_option_ids": ["recorded"]}
              for qid in ("REF", "SENSOR-A", "SENSOR-B")]
    return {"version": "cooling-v2", "areas": [{"id": "cooling"}],
            "questions": [*(question(qid, "numeric_with_choice", ["recorded", "unavailable"],
                                     fields=("reading",), batch="cold_start")
                           for qid in ("REF", "SENSOR-A", "SENSOR-B")),
                          question("COMPARE", "automatic_derived",
                                   ["consistent", "a_outlier", "b_outlier", "multiple"])],
            "calculation_rules": {"version": "evidence-v1", "rules": [{
                "id": "cooling-static", "target_question_id": "COMPARE",
                "operator": "numeric_reference_consistency", "inputs": inputs,
                "same_batch_kind": "cold_start", "unit": "kPa",
                "parameters": {"max_difference": 5},
                "outputs": {"consistent": "consistent", "single_outlier": {
                    "SENSOR-A": "a_outlier", "SENSOR-B": "b_outlier"},
                    "multiple_outliers": "multiple"}}]}}


def series_topic():
    inputs = [{"question_id": qid, "target_field": "desired", "actual_field": "measured",
               "valid_option_ids": ["recorded"]} for qid in ("FRAME-A", "FRAME-B", "FRAME-C")]
    return {"version": "cooling-v2", "areas": [{"id": "cooling"}],
            "questions": [question("CONDITION", "single_choice", ["comparable", "different"]),
                          *(question(qid, "numeric_with_choice", ["recorded", "unavailable"],
                                     fields=("desired", "measured"), batch="load_series")
                            for qid in ("FRAME-A", "FRAME-B", "FRAME-C")),
                          question("TREND", "automatic_derived", ["tracks", "lag", "intermittent"])],
            "calculation_rules": {"version": "evidence-v1", "rules": [{
                "id": "cooling-series", "target_question_id": "TREND",
                "operator": "numeric_series_gap", "inputs": inputs,
                "same_batch_kind": "load_series", "unit": "kPa",
                "comparability_gate": {"question_id": "CONDITION", "allowed_option_ids": ["comparable"]},
                "parameters": {"close_abs_max": 5, "large_positive_min": 15},
                "outputs": {"tracks": "tracks", "persistent_positive_gap": "lag",
                            "intermittent_positive_gap": "intermittent"}}]}}


def view(topic, records, plan):
    return project_template({"intake_snapshot": {"topic_plan": plan}}, records, topic)


def test_numeric_reference_uses_same_batch_and_effective_correction():
    topic = static_topic()
    plan = build_plan(topic, {})
    batch = plan["capture_batches"]["cold_start"]
    reference = row("REF", {"reading": 100}, batch)
    sensor_a = row("SENSOR-A", {"reading": 102}, batch)
    sensor_b = row("SENSOR-B", {"reading": 118}, batch)
    records = [reference, sensor_a, sensor_b]
    result = view(topic, records, plan)["derived"]["COMPARE"]
    assert result["option_id"] == "b_outlier"
    assert set(result["basis_observation_ids"]) == {str(item["id"]) for item in records}

    split = [row("REF", {"reading": 100}, batch),
             row("SENSOR-A", {"reading": 96}, batch),
             row("SENSOR-B", {"reading": 104}, batch)]
    assert view(topic, split, plan)["derived"]["COMPARE"]["option_id"] == "multiple"

    corrected = row("SENSOR-B", {"reading": 101}, batch, supersedes=sensor_b["id"])
    result = view(topic, [*records, corrected], plan)["derived"]["COMPARE"]
    assert result["option_id"] == "consistent"
    assert str(sensor_b["id"]) not in result["basis_observation_ids"]
    assert str(corrected["id"]) in result["basis_observation_ids"]

    wrong_batch = row("SENSOR-B", {"reading": 101}, str(uuid4()), supersedes=sensor_b["id"])
    result = view(topic, [*records, wrong_batch], plan)["derived"]["COMPARE"]
    assert result["option_id"] is None
    assert result["detail"]["evidence_state"] == "insufficient"

    wrong_unit = row("SENSOR-B", {"reading": 101}, batch, supersedes=sensor_b["id"], unit="bar")
    result = view(topic, [*records, wrong_unit], plan)["derived"]["COMPARE"]
    assert result["option_id"] is None
    assert result["detail"]["evidence_state"] == "insufficient"


def test_series_does_not_classify_uncomparable_or_uncovered_gaps():
    topic = series_topic()
    plan = build_plan(topic, {})
    batch = plan["capture_batches"]["load_series"]
    frames = [row(qid, {"desired": 100, "measured": actual}, batch)
              for qid, actual in zip(("FRAME-A", "FRAME-B", "FRAME-C"), (98, 96, 97))]
    gate = row("CONDITION", {}, None, option="comparable")
    assert view(topic, frames, plan)["derived"]["TREND"]["option_id"] is None
    assert view(topic, [*frames, gate], plan)["derived"]["TREND"]["option_id"] == "tracks"

    different = row("CONDITION", {}, None, option="different", supersedes=gate["id"])
    result = view(topic, [*frames, gate, different], plan)["derived"]["TREND"]
    assert result["option_id"] is None
    assert result["detail"]["evidence_state"] == "insufficient"

    between = [row(qid, {"desired": 100, "measured": 90}, batch)
               for qid in ("FRAME-A", "FRAME-B", "FRAME-C")]
    result = view(topic, [*between, gate], plan)["derived"]["TREND"]
    assert result["option_id"] is None
    assert result["detail"]["evidence_state"] == "no_matching_rule"

    lag = [row(qid, {"desired": 100, "measured": 70}, batch)
           for qid in ("FRAME-A", "FRAME-B", "FRAME-C")]
    assert view(topic, [*lag, gate], plan)["derived"]["TREND"]["option_id"] == "lag"
    mixed = [lag[0], frames[1], lag[2]]
    assert view(topic, [*mixed, gate], plan)["derived"]["TREND"]["option_id"] == "intermittent"


def test_invalid_rule_cannot_reference_unknown_field_or_threshold():
    topic = static_topic()
    topic["calculation_rules"]["rules"][0]["inputs"][1]["field"] = "missing"
    with pytest.raises(DomainError, match="模板派生规则配置无效"):
        build_plan(topic, {})
    topic = static_topic()
    topic["calculation_rules"]["rules"][0]["parameters"]["max_difference"] = float("nan")
    with pytest.raises(DomainError, match="模板派生规则配置无效"):
        build_plan(topic, {})


def test_numeric_catalog_is_publishable(tmp_path):
    topic = static_topic()
    topic["topic_id"] = "cooling-template"
    topic["version"] = "cooling-template-v1"
    topic["areas"][0]["componentIds"] = ["cooling-checks"]
    topic["cards"] = [{"id": "cooling-checks", "areaId": "cooling",
                       "questionIds": [question["id"] for question in topic["questions"]]}]
    for question in topic["questions"]:
        question["cardId"] = "cooling-checks"
    (tmp_path / "content.json").write_text(json.dumps(topic), encoding="utf-8")
    relation = {"id": "cooling-v1", "template_id": "cooling-template", "version": "1",
                "area_ids": ["cooling"], "content_file": "content.json"}
    config = tmp_path / "relations.json"
    config.write_text(json.dumps({"runtime_importable": True, "relations": [relation]}), encoding="utf-8")
    loaded_relation, loaded_topic = next(build_templates(config))
    plan = build_plan(loaded_topic, {})
    assert loaded_relation == relation
    assert "cold_start" in plan["capture_batches"]
    assert "calculation_catalog" not in loaded_topic


def logic_topic():
    return {"version": "cooling-v2", "areas": [{"id": "cooling"}],
            "questions": [question(qid, "single_choice", options) for qid, options in (
                ("STATIC", ["credible", "conflict"]), ("TREND", ["persistent", "other"]),
                ("LEAK-A", ["found", "clear"]), ("LEAK-B", ["found", "clear"]),
                ("MECHANICAL", ["found", "clear"]), ("FUEL", ["found", "clear"]))] + [
                question("SUPPORT", "automatic_derived", ["weak", "strong"]),
                question("DIRECTION", "automatic_derived", ["air", "fuel", "multiple"])],
            "calculation_rules": {"version": "evidence-v1", "rules": [
                {"id": "credibility", "operator": "evidence_gate",
                 "all": [{"question_id": "STATIC", "option_ids": ["credible"]},
                         {"question_id": "TREND", "option_ids": ["persistent"]}],
                 "outputs": {"supported": "supported"}},
                {"id": "support-count", "operator": "independent_group_count",
                 "target_question_id": "SUPPORT", "parameters": {"minimum_multiple": 2}, "groups": [
                     {"id": "external", "any": [
                         {"question_id": "LEAK-A", "option_ids": ["found"]},
                         {"question_id": "LEAK-B", "option_ids": ["found"]}]},
                     {"id": "mechanical", "any": [
                         {"question_id": "MECHANICAL", "option_ids": ["found"]}]},
                     {"id": "pressure", "all": [
                         {"result_id": "credibility", "option_ids": ["supported"]},
                         {"question_id": "TREND", "option_ids": ["persistent"]}]}],
                 "outputs": {"below_threshold": "weak", "multiple": "strong"}},
                {"id": "directions", "operator": "direction_set",
                 "target_question_id": "DIRECTION", "groups": [
                     {"id": "air", "any": [
                         {"question_id": "LEAK-A", "option_ids": ["found"]},
                         {"question_id": "LEAK-B", "option_ids": ["found"]}]},
                     {"id": "fuel", "all": [
                         {"question_id": "FUEL", "option_ids": ["found"]},
                         {"result_id": "credibility", "option_ids": ["supported"]}]}],
                 "outputs": {"air": "air", "fuel": "fuel", "multiple": "multiple"}}]}}


def test_cross_evidence_groups_count_once_and_directions_preserve_multiple():
    topic = logic_topic()
    plan = build_plan(topic, {})
    a = row("LEAK-A", {}, None, option="found")
    b = row("LEAK-B", {}, None, option="found")
    result = view(topic, [a, b], plan)["derived"]
    assert result["SUPPORT"]["option_id"] == "weak"
    assert result["SUPPORT"]["detail"]["matched_group_ids"] == ["external"]
    assert result["DIRECTION"]["option_id"] == "air"
    assert "credibility" not in result

    records = [a, b, row("STATIC", {}, None, option="credible"),
               row("TREND", {}, None, option="persistent"),
               row("FUEL", {}, None, option="found")]
    result = view(topic, records, plan)["derived"]
    assert result["SUPPORT"]["option_id"] == "strong"
    assert result["SUPPORT"]["detail"]["matched_group_ids"] == ["external", "pressure"]
    assert result["DIRECTION"]["option_id"] == "multiple"
    assert result["DIRECTION"]["detail"]["matched_group_ids"] == ["air", "fuel"]
    assert set(result["DIRECTION"]["basis_observation_ids"]) == {
        str(item["id"]) for item in records}

    changed = row("STATIC", {}, None, option="conflict", supersedes=records[2]["id"])
    result = view(topic, [*records, changed], plan)["derived"]
    assert result["SUPPORT"]["option_id"] == "weak"
    assert result["DIRECTION"]["option_id"] == "air"
    assert str(records[2]["id"]) not in result["DIRECTION"]["basis_observation_ids"]
    assert str(changed["id"]) in result["DIRECTION"]["basis_observation_ids"]


def test_cross_evidence_missing_is_not_normal_and_invalid_dependencies_fail():
    topic = logic_topic()
    result = view(topic, [], build_plan(topic, {}))["derived"]
    assert result["SUPPORT"]["option_id"] is None
    assert result["SUPPORT"]["detail"]["evidence_state"] == "awaiting_input"
    assert result["DIRECTION"]["option_id"] is None
    assert result["DIRECTION"]["detail"]["unknown_group_ids"] == ["air", "fuel"]

    topic = logic_topic()
    topic["calculation_rules"]["rules"][0]["all"][0] = {
        "result_id": "directions", "option_ids": ["air"]}
    with pytest.raises(DomainError, match="模板派生规则配置无效"):
        build_plan(topic, {})
    topic = logic_topic()
    topic["calculation_rules"]["rules"][1]["groups"][0]["any"][0]["option_ids"] = ["missing"]
    with pytest.raises(DomainError, match="模板派生规则配置无效"):
        build_plan(topic, {})
    topic = logic_topic()
    topic["calculation_rules"]["rules"][0]["all"][0]["question_id"] = ["STATIC"]
    with pytest.raises(DomainError, match="模板派生规则配置无效"):
        build_plan(topic, {})


def test_evidence_gate_can_depend_on_numeric_result_without_copying_legacy_logic():
    topic = static_topic()
    topic["questions"].append(question("TRUST", "automatic_derived", ["supported"]))
    topic["calculation_rules"]["rules"].append({
        "id": "credibility", "operator": "evidence_gate", "target_question_id": "TRUST",
        "all": [{"result_id": "cooling-static", "option_ids": ["consistent"]}],
        "outputs": {"supported": "supported"}})
    plan = build_plan(topic, {})
    batch = plan["capture_batches"]["cold_start"]
    readings = [row(qid, {"reading": value}, batch) for qid, value in
                (("REF", 100), ("SENSOR-A", 102), ("SENSOR-B", 101))]
    result = view(topic, readings, plan)["derived"]
    assert result["TRUST"]["option_id"] == "supported"
    assert set(result["TRUST"]["basis_observation_ids"]) == {str(item["id"]) for item in readings}
    conflict = row("SENSOR-B", {"reading": 130}, batch, supersedes=readings[2]["id"])
    result = view(topic, [*readings, conflict], plan)["derived"]
    assert result["COMPARE"]["option_id"] == "b_outlier"
    assert result["TRUST"]["option_id"] is None
    assert result["TRUST"]["detail"]["evidence_state"] == "insufficient"
