"""C15 treatment requires matching frozen facts and source text."""

from copy import deepcopy

from app.services.case_analysis_actions import action_facts_satisfied
from app.legacy_execution.case_analysis import assemble_proposal, proposal_schema
from test_case_analysis_c14 import frozen, proposal

ACTION = "RESEAT_DKVB_CHARGE_AIR_HOSE_COUPLING"


def scenario():
    snapshot = frozen()
    snapshot["allowed_scope"] = "conditional_action"
    snapshot["vehicle"] = {"year": 2019, "engine_code": "DKVB-DEMO"}
    snapshot["observations"].extend([
        {"id": "mark", "question_id": "AIR-09", "option_ids": ["misaligned"], "fields": {}},
        {"id": "seal", "question_id": "AIR-10", "option_ids": ["normal"], "fields": {}},
        {"id": "location", "question_id": "AIR-15", "option_ids": ["connector"], "fields": {}},
        {"id": "leak", "question_id": "AIR-16", "option_ids": ["audible_or_bubble"], "fields": {}},
    ])
    draft = proposal()
    draft["steps"] = [{"type": "controlled", "action_id": ACTION,
                       "basis_observation_ids": ["air-fact", "mark", "seal", "location", "leak"]}]
    return snapshot, draft


def test_source_backed_treatment_uses_frozen_catalog():
    snapshot, draft = scenario()
    ids = proposal_schema(snapshot)["$defs"]["ControlledStepProposal"]["properties"]["action_id"]["enum"]
    assert ACTION in ids
    result = assemble_proposal(snapshot, draft)
    assert result["publication"]["state"] == "complete"
    step = result["steps"][0]
    rule = snapshot["action_catalog"]["actions"][ACTION]
    assert step["action"] == rule["action"] and step["retest"] == rule["retest"]
    assert step["source_ids"] == rule["required_excerpt_ids"]
    assert "5.5 Nm" in step["action"] and "0.5 bar" in step["retest"]


def test_missing_fact_or_excerpt_does_not_publish_treatment():
    snapshot, draft = scenario()
    rule = snapshot["action_catalog"]["actions"][ACTION]
    assert action_facts_satisfied(rule, snapshot["observations"])
    incomplete = deepcopy(draft)
    incomplete["steps"][0]["basis_observation_ids"].remove("seal")
    partial = assemble_proposal(snapshot, incomplete)
    assert partial["publication"]["state"] == "partial"
    assert partial["publication"]["rejected_sections"][0]["rule_id"] == "action.fact"
    missing_source = deepcopy(snapshot)
    missing_source["source_context"]["excerpts"] = [item for item in snapshot["source_context"]["excerpts"]
                                                      if item["id"] != "C15-SRC-CHARGE-AIR-P2"]
    partial = assemble_proposal(missing_source, draft)
    assert partial["publication"]["state"] == "partial"
    assert partial["publication"]["rejected_sections"][0]["rule_id"] == "action.source_missing"
    wrong_year = deepcopy(snapshot)
    wrong_year["vehicle"]["year"] = 2020
    partial = assemble_proposal(wrong_year, draft)
    assert partial["publication"]["state"] == "partial"
    assert partial["publication"]["rejected_sections"][0]["rule_id"] == "action.vehicle_applicability"
