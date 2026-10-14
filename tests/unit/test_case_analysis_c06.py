"""C06 proposal branches and frozen assembly; entirely offline synthetic fixtures."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.domain.case_analysis import CaseAdviceProposalV2
from app.domain.policies import DomainError
from app.services.case_analysis_actions import supported_actions
from app.services.case_analysis_context import selected_context
from app.legacy_execution.case_analysis import assemble_proposal, proposal_schema, substitute_advice
from app.topics import dkvb_b02


def frozen():
    topic, _ = dkvb_b02.catalog()
    context = deepcopy(selected_context(topic, ["AIR-07"]))
    return {
        "output_contract_version": "case-advice-proposal-c06-v1",
        "allowed_scope": "supplement_or_handoff",
        "observations": [{"id": "synthetic-air-07", "question_id": "AIR-07",
                          "option_ids": ["partially_seated"]}],
        "source_context": context,
        "action_catalog": supported_actions(context),
        "synthesis": {"unavailable": [], "missing_question_ids": [], "conflicts": []},
    }


def proposal(snapshot):
    result = substitute_advice(snapshot)
    steps = []
    for step in result["steps"]:
        if step.get("action_id"):
            steps.append({"type": "controlled", "action_id": step["action_id"],
                          "basis_observation_ids": step["basis_observation_ids"]})
        else:
            steps.append({"type": "free", **step})
    result["steps"] = steps
    return result


def test_c06_contract_and_frozen_assembly():
    snapshot = frozen()
    draft = proposal(snapshot)
    schema = proposal_schema(snapshot)
    assert schema["properties"]["supported_directions"]["maxItems"] == 0
    controlled = schema["$defs"]["ControlledStepProposal"]["properties"]
    assert set(controlled) == {"type", "action_id", "basis_observation_ids"}
    assert controlled["action_id"]["enum"] == ["CHECK_CHARGE_AIR_HOSE_SEATING_LEAK"]
    parsed = CaseAdviceProposalV2.model_validate(draft)
    assert parsed.steps[0].type == "controlled"
    result = assemble_proposal(snapshot, parsed)
    rule = snapshot["action_catalog"]["actions"][draft["steps"][0]["action_id"]]
    assert result["steps"][0]["kind"] == rule["kind"]
    for field in ("action", "prerequisites", "retest", "stop_condition"):
        assert result["steps"][0][field] == rule[field]
    assert result["steps"][0]["source_ids"] == rule["required_excerpt_ids"]
    assert result["steps"][1]["kind"] == "handoff"


@pytest.mark.parametrize("change,rule", [
    ({"action_id": "UNKNOWN"}, "action.known"),
    ({"basis_observation_ids": ["invented"]}, "reference.observation"),
    ({"basis_observation_ids": []}, "proposal.structure"),
])
def test_controlled_step_rejects_unknown_or_false_facts(change, rule):
    snapshot = frozen()
    draft = proposal(snapshot)
    draft["steps"][0].update(change)
    if rule == "proposal.structure":
        with pytest.raises(ValidationError):
            assemble_proposal(snapshot, draft)
    else:
        with pytest.raises(DomainError) as error:
            assemble_proposal(snapshot, draft)
        assert error.value.details["rule_id"] == rule


def test_missing_or_changed_frozen_excerpt_rejected():
    snapshot = frozen()
    draft = proposal(snapshot)
    snapshot["source_context"]["excerpts"] = [item for item in snapshot["source_context"]["excerpts"]
                                             if item["id"] != "C01-SRC-CHARGE-AIR-P1"]
    with pytest.raises(DomainError) as error:
        assemble_proposal(snapshot, draft)
    assert error.value.details["rule_id"] == "action.source_missing"


def test_existing_but_nonqualifying_fact_is_not_enough():
    snapshot = frozen()
    draft = proposal(snapshot)
    snapshot["observations"][0]["option_ids"] = ["locked"]
    with pytest.raises(DomainError) as error:
        assemble_proposal(snapshot, draft)
    assert error.value.details["rule_id"] == "action.fact"
    snapshot = frozen()
    snapshot["source_context"]["excerpts"][0]["text"] = "changed after freeze"
    with pytest.raises(DomainError) as error:
        assemble_proposal(snapshot, draft)
    assert error.value.details["rule_id"] == "action.source_missing"


@pytest.mark.parametrize("field,value", [
    ("source_ids", ["UNKNOWN_SOURCE"]),
    ("action", "直接拆卸并更换涡轮"),
])
def test_free_step_cannot_bypass_references_or_action_catalog(field, value):
    snapshot = frozen()
    draft = proposal(snapshot)
    draft["steps"][1][field] = value
    with pytest.raises(DomainError):
        assemble_proposal(snapshot, draft)


@pytest.mark.parametrize("field,value", [
    ("source_ids", ["C01-SRC-CHARGE-AIR-P1"]),
    ("action", "model-authored operation"),
    ("kind", "check"),
])
def test_controlled_step_forbids_model_owned_fields(field, value):
    draft = proposal(frozen())
    draft["steps"][0][field] = value
    with pytest.raises(ValidationError) as error:
        CaseAdviceProposalV2.model_validate(draft)
    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_old_c04_snapshot_uses_old_parser_without_changing_published_shape():
    snapshot = frozen()
    snapshot["output_contract_version"] = "case-advice-proposal-c04-v1"
    old = deepcopy(substitute_advice(snapshot))
    for field in ("action", "prerequisites", "retest", "stop_condition"):
        old["steps"][0].pop(field)
    assert assemble_proposal(snapshot, old)["steps"][0]["source_ids"] == old["steps"][0]["source_ids"]
