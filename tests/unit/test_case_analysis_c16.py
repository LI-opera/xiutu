"""C16 owns controlled prose on the server; free text remains bounded."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.domain.case_analysis import CaseAdviceProposalV6
from app.domain.policies import DomainError
from app.legacy_execution.case_analysis import (assemble_proposal, model_payload,
                                                proposal_instruction, proposal_schema)
from test_case_analysis_c15 import scenario


def current():
    snapshot, proposal = scenario()
    snapshot["output_contract_version"] = "case-advice-proposal-c16-v1"
    snapshot["prompt_version"] = "dkvb-c16-v1"
    snapshot["synthesis"] = {"facts": []}
    for fact in snapshot["observations"]:
        fact["question"] = fact["question_id"] + " · 模拟观察"
    proposal.pop("retest_plan", None)
    proposal.pop("safety_notice", None)
    proposal.pop("safety_source_ids", None)
    return snapshot, proposal


def test_new_model_contract_does_not_request_server_owned_safety_or_retest():
    snapshot, proposal = current()
    schema = proposal_schema(snapshot)
    for key in ("safety_notice", "safety_source_ids", "retest_plan"):
        assert key not in schema["properties"]
        with pytest.raises(ValidationError):
            CaseAdviceProposalV6.model_validate({**proposal, key: "模型自由填写"})
    assert "无需生成全局 safety_notice" in proposal_instruction(snapshot)
    wire = model_payload(snapshot)
    action = wire["action_catalog"]["actions"]["RESEAT_DKVB_CHARGE_AIR_HOSE_COUPLING"]
    assert "action" not in action and "retest" not in action and "prerequisites" not in action
    assert action["required_all_question_options"]


def test_frozen_controlled_step_provides_all_fixed_text_and_refs():
    snapshot, proposal = current()
    result = assemble_proposal(snapshot, proposal)
    rule = snapshot["action_catalog"]["actions"]["RESEAT_DKVB_CHARGE_AIR_HOSE_COUPLING"]
    assert result["publication"]["contract_version"] == "case-advice-proposal-c16-v1"
    assert result["publication"]["state"] == "complete"
    assert result["safety_notice"] is None and result["retest_plan"] is None
    assert all(result["steps"][0][key] == rule[key] for key in
               ("action", "prerequisites", "retest", "stop_condition"))
    assert result["steps"][0]["source_ids"] == rule["required_excerpt_ids"]


def test_handoff_to_repair_personnel_is_not_an_operation_but_new_operation_is_rejected():
    snapshot, proposal = current()
    proposal["steps"].append({"type": "handoff",
        "action": "将接头座合与泄漏复核结果交接给具备现场条件的维修人员。",
        "reason": "模拟观察需要现场核实。", "basis_observation_ids": ["air-fact"]})
    assert assemble_proposal(snapshot, proposal)["publication"]["state"] == "complete"
    changed = deepcopy(proposal)
    changed["steps"][1]["action"] = "请先拆卸接头，再交给维修人员。"
    partial = assemble_proposal(snapshot, changed)
    assert partial["publication"]["state"] == "partial"
    assert partial["publication"]["rejected_sections"][0]["rule_id"] == "text.unlisted_operation"
    assert len(partial["steps"]) == 1


def test_missing_frozen_action_evidence_still_isolates_operation():
    snapshot, proposal = current()
    proposal["steps"][0]["basis_observation_ids"].remove("seal")
    result = assemble_proposal(snapshot, proposal)
    assert result["publication"]["state"] == "partial"
    assert result["publication"]["rejected_sections"][0]["rule_id"] == "action.fact"
    assert not result["steps"]


def test_global_new_executable_instruction_still_fails_closed():
    snapshot, proposal = current()
    proposal["summary"] = "目前不能确诊；请重新加压至 2 bar。"
    with pytest.raises(DomainError):
        assemble_proposal(snapshot, proposal)
