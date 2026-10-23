import json

import pytest
from app.domain.policies import DomainError
from app.services.template_projection import build_plan, project_template

from scripts.seed_workbench_templates import build_templates


def fixture(tmp_path, *, content_file="content.json", topic_id="cooling-template"):
    topic = {
        "topic_id": topic_id, "version": "cooling-template-v1",
        "areas": [{"id": "cooling", "componentIds": ["checks"]}],
        "cards": [{"id": "checks", "areaId": "cooling", "questionIds": ["COOL-01"]}],
        "questions": [{"id": "COOL-01", "area_id": "cooling", "cardId": "checks",
                       "answer_kind": "single_choice", "options": [
                           {"id": "normal", "outcome": "normal"},
                           {"id": "abnormal", "outcome": "abnormal"}]}],
    }
    (tmp_path / "content.json").write_text(json.dumps(topic), encoding="utf-8")
    relation = {"id": "cooling-v1", "template_id": "cooling-template",
                "version": "1", "area_ids": ["cooling"],
                "content_file": content_file}
    config = tmp_path / "relations.json"
    config.write_text(json.dumps({"runtime_importable": True, "relations": [relation]}), encoding="utf-8")
    return config


def test_template_is_built_only_from_its_content_file(tmp_path):
    config = fixture(tmp_path)
    relation, topic = next(build_templates(config))
    plan = build_plan(topic, {})
    view = project_template({"intake_snapshot": {"topic_plan": plan}}, [], topic)
    assert relation["template_id"] == "cooling-template"
    assert [area["area_id"] for area in view["areas"]] == ["cooling"]
    assert view["synthesis"]["missing_question_ids"] == ["COOL-01"]


def test_independent_content_must_match_identity_and_stay_in_package(tmp_path):
    with pytest.raises(ValueError, match="identity"):
        next(build_templates(fixture(tmp_path, topic_id="another-template")))
    with pytest.raises(ValueError, match="Invalid template content file"):
        next(build_templates(fixture(tmp_path, content_file="../content.json")))


def test_relation_without_content_file_is_rejected(tmp_path):
    config = fixture(tmp_path)
    body = json.loads(config.read_text(encoding="utf-8"))
    del body["relations"][0]["content_file"]
    config.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(ValueError, match="requires content_file"):
        next(build_templates(config))


def test_authoring_candidate_cannot_be_imported(tmp_path):
    config = fixture(tmp_path)
    body = json.loads(config.read_text(encoding="utf-8"))
    body["runtime_importable"] = False
    config.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(ValueError, match="not approved"):
        next(build_templates(config))


def test_content_with_rules_in_code_is_rejected(tmp_path):
    config = fixture(tmp_path)
    path = tmp_path / "content.json"
    topic = json.loads(path.read_text(encoding="utf-8"))
    topic["calculation_catalog"] = {"version": "2.2.1-b02"}
    path.write_text(json.dumps(topic), encoding="utf-8")
    with pytest.raises(ValueError, match="must be data"):
        next(build_templates(config))


def test_independent_observation_rules_are_checked_before_publication(tmp_path):
    config = fixture(tmp_path)
    path = tmp_path / "content.json"
    topic = json.loads(path.read_text(encoding="utf-8"))
    topic["observation_rules"] = {"version": "observation-v1", "focus_rules": [
        {"id": "focus", "all": [{"question_id": "COOL-01", "option_ids": ["abnormal"]}],
         "question_ids": ["COOL-01"]}], "conflict_rules": []}
    path.write_text(json.dumps(topic), encoding="utf-8")
    _, loaded = next(build_templates(config))
    assert loaded["observation_rules"]["version"] == "observation-v1"
    topic["observation_rules"]["focus_rules"][0]["question_ids"] = ["missing"]
    path.write_text(json.dumps(topic), encoding="utf-8")
    with pytest.raises(DomainError, match="观察规则配置无效"):
        next(build_templates(config))
