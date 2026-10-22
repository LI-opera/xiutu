from copy import deepcopy
import pytest
from app.domain.policies import DomainError
from app.services.area_analysis_service import (build_input, build_matched_input,
    input_identity, messages_for, MATCHED_PROMPT_VERSION, SYSTEM_PROMPT)
from scripts.seed_area_references import build_documents, DEFAULT_PACKAGE, extract_sections, load_manuals


def view():
    return {"case": {"id": "case", "revision": 2, "vehicle": {"model": "车型"},
        "fault_description": "偶尔跳变", "fault_codes": ["P0236"],
        "intake_snapshot": {"template_binding": {"template_id": "x", "version": "1"}}},
        "plan": {"intake": {}}, "topic": {"areas": [
            {"id": "pressure", "title": "压力", "description": "压力测量"},
            {"id": "new-area", "title": "新区域", "description": "新资料"}],
            "questions": [
                {"id": "P1", "area_id": "pressure", "title": "问题1", "answer_kind": "single_choice", "options": [{"id": "lost", "label": "丢失"}]},
                {"id": "P2", "area_id": "pressure", "title": "问题2", "answer_kind": "single_choice", "options": []},
                {"id": "N1", "area_id": "new-area", "title": "问题3", "answer_kind": "single_choice", "options": []}]},
        "observations": [
            {"id": "old", "question_id": "P1", "effective": False, "payload": {"option_ids": []}},
            {"id": "current", "question_id": "P1", "effective": True, "payload": {"option_ids": ["lost"], "fields": {"p": {"value": 980, "unit": "hPa"}}}},
            {"id": "other", "question_id": "N1", "effective": True, "payload": {"option_ids": []}}]}


def test_input_is_area_scoped_effective_and_unknown_not_normal():
    original = view()
    before = deepcopy(original)
    payload = build_input(original, "pressure", [{"id": "doc", "body": "完整正文"}])
    assert [o["id"] for o in payload["observations"]] == ["current"]
    assert payload["unknown_question_ids"] == ["P2"]
    assert payload["documents"][0]["body"] == "完整正文"
    assert payload["observations"][0]["fields"]["p"]["unit"] == "hPa"
    assert before == original


def test_new_area_works_without_code_or_prompt_branch():
    payload = build_input(view(), "new-area", [{"id": "new-document"}])
    assert [o["id"] for o in payload["observations"]] == ["other"]
    assert payload["documents"] == [{"id": "new-document"}]
    assert "G31" not in SYSTEM_PROMPT and "pressure" not in SYSTEM_PROMPT


def test_combined_request_includes_only_areas_with_effective_saved_answers():
    original = view()
    refs = {"pressure": [{"id": "pressure-doc", "version": "1", "body": "压力资料"}],
            "new-area": [{"id": "new-doc", "version": "1", "body": "另一区资料"}]}
    payload = build_matched_input(original, refs)
    assert [a["id"] for a in payload["areas"]] == ["pressure", "new-area"]
    assert payload["areas"][0]["observation_ids"] == ["current"]
    assert payload["areas"][1]["observation_ids"] == ["other"]
    assert payload["areas"][0]["document_ids"] == ["pressure-doc"]
    assert payload["areas"][1]["document_ids"] == ["new-doc"]
    assert [d["id"] for d in payload["documents"]] == ["pressure-doc", "new-doc"]
    assert payload["unknown_question_ids"] == ["P2"]
    assert payload["prompt_version"] == MATCHED_PROMPT_VERSION
    assert len(messages_for(payload)) == 2
    assert "有已保存检查记录的区域" in messages_for(payload)[0].content
    added = deepcopy(original)
    added["topic"]["areas"].append({"id": "third", "title": "第三区", "description": "第三资料"})
    added["topic"]["questions"].append({"id": "T1", "area_id": "third", "title": "问题4",
                                          "answer_kind": "single_choice", "options": []})
    refs["third"] = [{"id": "third-doc", "version": "1", "body": "第三资料"}]
    assert len(build_matched_input(added, refs)["areas"]) == 2
    added["observations"].append({"id": "third-answer", "question_id": "T1", "effective": True,
                                  "payload": {"option_ids": []}})
    assert [area["id"] for area in build_matched_input(added, refs)["areas"]] == ["pressure", "new-area", "third"]
    no_answers = deepcopy(original)
    no_answers["observations"] = [no_answers["observations"][0]]
    empty = build_matched_input(no_answers, refs)
    assert empty["areas"] == empty["documents"] == empty["observations"] == []
    assert input_identity(empty) != input_identity(payload)


def test_unmatched_area_rejected():
    with pytest.raises(DomainError):
        build_input(view(), "not-matched", [])


def test_unrelated_case_revision_does_not_age_area_advice():
    initial = build_input(view(), "pressure", [{"id": "doc", "version": "1"}])
    changed = deepcopy(initial)
    changed["case_revision"] += 1
    assert input_identity(changed) == input_identity(initial)
    changed["documents"][0]["version"] = "2"
    assert input_identity(changed) != input_identity(initial)


def test_source_sections_are_exact_and_missing_is_not_silently_ignored():
    assert extract_sections("# title\n## A\none\n## B\ntwo\n", ["## A"]) == "## A\none"
    with pytest.raises(ValueError):
        extract_sections("## A\none", ["## B"])


def test_manual_list_has_five_independent_documents():
    entries = list(build_documents(DEFAULT_PACKAGE, load_manuals()))
    assert len(entries) == 5
    assert len({record["document_id"] for _, record in entries}) == 5
    assert all(record["body"] and len(record["content_hash"]) == 64 for _, record in entries)
    actuator = next(record for _, record in entries if record["document_id"] == "tayron-dkvb-actuator")
    assert actuator["body"] == (DEFAULT_PACKAGE / "15-增压调节机构检查与维修参考-详细版.md").read_text(encoding="utf-8")


def test_manual_list_rejects_changed_source(tmp_path):
    source = tmp_path / "sample.md"
    source.write_text("初始资料", encoding="utf-8")
    entry = {"document_id": "sample", "version": "2",
             "title": "资料", "coverage": "检查", "sources": [{"file": "sample.md"}],
             "source_hashes": {"sample.md": "0" * 64}}
    with pytest.raises(ValueError, match="Source changed"):
        list(build_documents(tmp_path, {"documents": [entry]}))



def test_action_schema_requires_titles_in_current_and_conditional_steps():
    from app.domain.area_advice import AreaAdviceV3, CaseAdviceOpenV2
    from pydantic import ValidationError
    old = {"summary": "需要确认", "steps": [{"kind": "check", "action": "测量连接点"}]}
    assert CaseAdviceOpenV2.model_validate(old).steps[0].action == "测量连接点"
    with pytest.raises(ValidationError):
        AreaAdviceV3.model_validate(old)
    current = deepcopy(old)
    current["steps"][0]["title"] = "核对供电"
    current["conditional_branches"] = [{"trigger": "供电正常但仍失效", "steps": old["steps"]}]
    with pytest.raises(ValidationError):
        AreaAdviceV3.model_validate(current)
    current["conditional_branches"][0]["steps"][0]["title"] = "检查控制信号"
    assert AreaAdviceV3.model_validate(current).steps[0].title == "核对供电"


def test_prompt_upgrade_changes_identity_without_changing_case():
    current = build_matched_input(view(), {})
    old = deepcopy(current)
    old["prompt_version"] = "matched-area-advice-v3"
    assert input_identity(current) != input_identity(old)
