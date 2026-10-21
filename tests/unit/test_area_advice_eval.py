"""The evaluation set builds real model inputs and its program checks grade correctly.

Offline: no model call. Guards against cases drifting from the template (invalid answers,
rule results no longer matching what a case is meant to test) and against grader bugs.
"""
from types import SimpleNamespace

import pytest
from app.services.area_analysis_service import input_identity
from app.services.workbench_answer_validation import validate_answer

from scripts import area_advice_eval as ev

SPEC = ev.load_cases()
CASES = {case["id"]: case for case in SPEC["cases"]}
TOPIC = ev.load_topic(SPEC["template"])
REFERENCES = ev.load_references(SPEC["template"])


def payload_of(case_id):
    return ev.build_payload(SPEC, CASES[case_id], topic=TOPIC, references=REFERENCES)


def derived(payload):
    return {item["question_id"]: item for item in payload["derived_results"]}


def obs(payload, question_id):
    return next(o for o in payload["observations"] if o["question_id"] == question_id)


@pytest.mark.parametrize("case_id", list(CASES))
def test_every_saved_record_is_a_valid_answer(case_id):
    view = ev.build_view(SPEC, CASES[case_id], TOPIC)
    for record in view["observations"]:
        value = record["payload"]
        body = SimpleNamespace(question_id=value["question_id"], option_ids=value["option_ids"],
            fields=value["fields"], note=value["note"], unavailable_reason=value["unavailable_reason"],
            retest_frames=[], batch_id=value.get("batch_id"), topic_version=TOPIC["version"])
        validate_answer(TOPIC, view["plan"], [], body, effective=lambda *_: None)


@pytest.mark.parametrize("case_id", list(CASES))
def test_input_is_complete_and_stable(case_id):
    payload = payload_of(case_id)
    assert payload["areas"] and all(area["document_ids"] for area in payload["areas"])
    assert payload["documents"] and all(doc["body"] for doc in payload["documents"])
    # Template binding matches the reviewed reading guide, so records carry real roles.
    assert all(o["record_role"] != "unclassified" for o in payload["observations"])
    assert payload["prompt_version"].startswith("matched-area-advice-")
    assert input_identity(payload) == input_identity(payload_of(case_id))


def test_shared_background_rule_results():
    payload = payload_of("c1-baseline")
    assert {a["id"] for a in payload["areas"]} == {"boost-air", "pressure"}
    assert derived(payload)["PRS-04"]["option_id"] == "consistent"
    assert derived(payload)["PRS-11"]["option_id"] == "persistent_underboost"
    assert payload["repair_rounds"] == []


def test_repaired_but_not_retested():
    payload = payload_of("c2-repaired-not-retested")
    (repair,) = payload["repair_rounds"]
    assert repair["retest_status"] == "pending" and repair["retest_outcome"] is None
    assert all(o["after_repair_round_id"] is None for o in payload["observations"])


@pytest.mark.parametrize("case_id, condition", [
    ("c3-retested-same-condition", "same"), ("c4-retested-different-condition", "different")])
def test_retested_cases_mark_rechecks_after_repair(case_id, condition):
    payload = payload_of(case_id)
    (repair,) = payload["repair_rounds"]
    assert (repair["retest_condition"], repair["retest_outcome"]) == (condition, "resolved")
    joint = obs(payload, "AIR-07")
    assert joint["option_ids"] == ["seated"]
    assert joint["after_repair_round_id"] == repair["id"]
    assert joint["before_repair"]["option_ids"] == ["partially_seated"]
    # Grouped load frames are not re-recorded after repair; they stay pre-repair.
    assert obs(payload, "PRS-08")["after_repair_round_id"] is None
    assert derived(payload)["PRS-11"]["option_id"] == "persistent_underboost"


def test_rule_results_case():
    results = derived(payload_of("c5-rule-results"))
    assert results["PRS-04"]["option_id"] == "g71_outlier"
    assert results["PRS-04"]["evidence_state"] == "computed"
    assert results["PRS-11"]["option_id"] is None
    assert results["PRS-11"]["evidence_state"] == "insufficient"


def test_missing_prerequisite_case():
    payload = payload_of("c6-prerequisite-missing")
    assert obs(payload, "AIR-13")["option_ids"] == ["unavailable"]
    assert obs(payload, "AIR-14")["option_ids"] == ["not_performed"]
    assert obs(payload, "AIR-12")["option_ids"] == ["right_suspect"]


def test_every_case_has_checks_and_human_questions():
    for case in SPEC["cases"]:
        assert case["checks"] and case["human"] and case["purpose"] and case["expected"]
        for check in case["checks"]:
            assert check["type"] in {"first_step_kind", "any_step_targets", "no_step_targets"}


# ---------------------------------------------------------------- graders

def step(kind, title, question_ids=(), action="按资料操作"):
    return {"kind": kind, "title": title, "action": action, "question_ids": list(question_ids),
            "basis_observation_ids": [], "source_ids": []}


def result(steps=(), branches=(), **extra):
    return {"summary": "测试", "steps": list(steps), "conditional_branches": [
        {"trigger": trigger, "steps": list(items)} for trigger, items in branches], **extra}


def by_id(graded):
    return {g["id"]: g["passed"] for g in graded}


def test_repeat_repair_is_caught_and_retest_first_passes():
    case, payload = CASES["c2-repaired-not-retested"], payload_of("c2-repaired-not-retested")
    good = result([step("check", "全负荷复检增压压力", ["PRS-08"]), step("record", "记录复检结果")])
    bad = result([step("repair", "重新推入中冷器出口接头", ["AIR-07"])])
    assert by_id(ev.grade(case, payload, good))["first_step_is_check"]
    assert by_id(ev.grade(case, payload, good))["no_repeat_repair"]
    assert not by_id(ev.grade(case, payload, bad))["first_step_is_check"]
    assert not by_id(ev.grade(case, payload, bad))["no_repeat_repair"]
    # Collecting the retest frames is a record step; it still counts as retesting first.
    collect = result([step("record", "接头复位后按原工况采集压力", ["PRS-08"])])
    assert by_id(ev.grade(case, payload, collect))["first_step_is_check"]


def test_deferred_pressure_test_passes_and_current_one_fails():
    case, payload = CASES["c6-prerequisite-missing"], payload_of("c6-prerequisite-missing")
    good = result([step("check", "目视检查中冷器右侧接口", ["AIR-12"])],
                  [("取得 V.A.G 1687 或等效安全检漏工具后", [step("check", "低压加压检漏", ["AIR-14"])])])
    bad = result([step("check", "用烟雾检漏仪加压查找泄漏")])
    assert by_id(ev.grade(case, payload, good)) == {
        "refs_exist": True, "retired_fields_empty": True,
        "no_pressure_test_now": True, "pressure_test_deferred": True}
    graded = by_id(ev.grade(case, payload, bad))
    assert not graded["no_pressure_test_now"] and not graded["pressure_test_deferred"]
    # A branch that only repairs what a leak test found does not defer the test itself.
    only_repair = result([step("record", "记录工具缺失，具备条件后按 0.5 bar 加压定位", ["AIR-13", "AIR-14"])],
                         [("定位检漏确认右侧接口有响应", [step("repair", "处理右侧接口密封", ["AIR-15"])])])
    graded = by_id(ev.grade(case, payload, only_repair))
    # Recording the missing tool is allowed now; what matters is that the test itself is deferred.
    assert graded["no_pressure_test_now"] and not graded["pressure_test_deferred"]


def test_text_match_finds_g71_without_question_ids():
    case, payload = CASES["c5-rule-results"], payload_of("c5-rule-results")
    graded = by_id(ev.grade(case, payload, result([step("check", "核对 G71 插头与数据来源")])))
    assert graded["addresses_g71"] and not graded["asks_comparable_frames"]


def test_invented_references_and_filled_retired_fields_fail():
    case, payload = CASES["c1-baseline"], payload_of("c1-baseline")
    invented = step("check", "检查接头", ["AIR-07", "AIR-99"])
    invented["basis_observation_ids"] = ["not-a-record"]
    invented["source_ids"] = [payload["documents"][0]["id"], "made-up-doc"]
    graded = ev.grade(case, payload, result([invented], verification="整体复检……",
                                            missing=[{"question_id": "XYZ-1", "missing": "x"}]))
    refs = next(g for g in graded if g["id"] == "refs_exist")
    assert not refs["passed"]
    for marker in ("AIR-99", "not-a-record", "made-up-doc", "XYZ-1"):
        assert marker in refs["detail"]
    assert not by_id(graded)["retired_fields_empty"]
    real = step("check", "检查快插接头", ["AIR-07"])
    real["basis_observation_ids"] = [obs(payload, "AIR-07")["id"]]
    real["source_ids"] = [payload["documents"][0]["id"]]
    assert all(by_id(ev.grade(case, payload, result([real]))).values())
