"""C17 technician-facing structure uses the same frozen publication path."""

from copy import deepcopy

from app.domain.case_analysis import CaseAdviceProposalV7
from app.legacy_execution.case_analysis import (assemble_proposal, model_payload,
                                                proposal_instruction, proposal_schema,
                                                substitute_advice)
from test_case_analysis_c15 import scenario


def current():
    snapshot, proposal = scenario()
    snapshot["output_contract_version"] = "case-advice-proposal-c17-v1"
    snapshot["prompt_version"] = "dkvb-c17-v1"
    snapshot["synthesis"] = {"conflicts": []}
    for key in ("safety_notice", "safety_source_ids", "retest_plan"):
        proposal.pop(key, None)
    proposal["supported_directions"][0]["counter_observation_ids"] = ["mark"]
    return snapshot, proposal


def test_new_schema_keeps_evidence_separate_and_server_owns_operation_text():
    snapshot, proposal = current()
    schema = proposal_schema(snapshot)
    assert schema["title"].startswith("case-advice-proposal-c17-v1")
    assert "counter_observation_ids" in schema["$defs"]["AdviceDirectionV7"]["properties"]
    assert "recheck_reason" in schema["$defs"]["RecordStepProposalV7"]["properties"]
    assert "safety_notice" not in schema["properties"]
    assert "action" not in model_payload(snapshot)["action_catalog"]["actions"]["RESEAT_DKVB_CHARGE_AIR_HOSE_COUPLING"]
    assert "面向维修人员" in proposal_instruction(snapshot)
    assert CaseAdviceProposalV7.model_validate(proposal)


def test_supported_treatment_and_counter_facts_use_frozen_refs():
    snapshot, proposal = current()
    result = assemble_proposal(snapshot, proposal)
    assert result["publication"]["state"] == "complete"
    assert result["supported_directions"][0]["counter_observation_ids"] == ["mark"]
    action = snapshot["action_catalog"]["actions"]["RESEAT_DKVB_CHARGE_AIR_HOSE_COUPLING"]
    assert result["steps"][0]["action"] == action["action"]
    assert result["steps"][0]["retest"] == action["retest"]
    assert result["safety_notice"] is None and result["retest_plan"] is None


def test_answered_question_cannot_be_rechecked_without_specific_reason():
    snapshot, proposal = current()
    proposal["steps"].append({"type": "record", "question_ids": ["AIR-09"],
                              "request": "补充 AIR-09 的当前结果。", "reason": "确认记录是否仍一致。",
                              "basis_observation_ids": ["mark"]})
    partial = assemble_proposal(snapshot, proposal)
    assert partial["publication"]["state"] == "partial"
    assert partial["publication"]["rejected_sections"][0]["rule_id"] == "record.recheck_reason"
    proposal["steps"][1]["recheck_reason"] = "本次座合与标记记录存在冲突，需澄清当前状态。"
    assert assemble_proposal(snapshot, proposal)["publication"]["state"] == "complete"


def test_invalid_counter_or_unsupported_operation_stays_unpublished():
    snapshot, proposal = current()
    bad = deepcopy(proposal)
    bad["supported_directions"][0]["counter_observation_ids"] = ["air-fact"]
    result = assemble_proposal(snapshot, bad)
    assert result["publication"]["state"] == "partial"
    assert result["publication"]["rejected_sections"][0]["rule_id"] == "direction.counter_distinct"
    bad = deepcopy(proposal)
    bad["steps"][0]["action_id"] = "UNLISTED_REPAIR"
    result = assemble_proposal(snapshot, bad)
    assert result["publication"]["state"] == "partial"
    assert result["steps"] == []


def test_substitute_guidance_adapts_to_complete_missing_and_conflicting_facts():
    snapshot, _ = current()
    snapshot["unresolved_questions"] = []
    full = substitute_advice(snapshot)
    assert [item["kind"] for item in full["steps"]] == ["check", "conditional_action"]
    assert full["publication"]["state"] == "complete"
    missing = deepcopy(snapshot)
    missing["allowed_scope"] = "supplement_or_handoff"
    missing["unresolved_questions"] = [{"question_id": "AIR-15", "name": "泄漏响应位置"}]
    next(item for item in missing["observations"] if item["question_id"] == "AIR-15")["option_ids"] = ["unavailable"]
    result = substitute_advice(missing)
    assert result["publication"]["state"] == "complete"
    assert result["steps"][0]["kind"] == "record"
    assert "保留现有原因" in result["steps"][0]["action"]
    assert not any(item["kind"] == "conditional_action" for item in result["steps"])
    conflict = deepcopy(snapshot)
    conflict["allowed_scope"] = "supplement_or_handoff"
    conflict["synthesis"]["conflicts"] = [{"id": "C-AIR-07-08", "question_ids": ["AIR-07", "AIR-08"],
                                            "reason": "座合与保持力记录冲突，需复核。"}]
    conflict["observations"][0]["option_ids"] = ["seated"]
    result = substitute_advice(conflict)
    assert result["publication"]["state"] == "complete"
    assert result["steps"][0]["recheck_reason"]
