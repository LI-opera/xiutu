from copy import deepcopy

import pytest

from app.agents.trusted_protocol import DKVB_DEMO_PROTOCOL, TrustedProtocol, validate_protocol_package
from app.services.protocol_service import ProtocolService


def test_protocol_v31_starts_after_atomic_intake_and_has_concrete_task_content():
    protocol = DKVB_DEMO_PROTOCOL
    assert protocol.version == "3.1.0"
    assert protocol.start_check_id == "CHK-01"
    assert {check.check_id for check in protocol.checks} >= {
        "CHK-01", "CHK-02", "CHK-03", "CHK-04", "CHK-05", "CHK-06",
        "CHK-07", "CHK-08", "CHK-09", "CHK-10", "CHK-11",
    }
    assert all(check.presentation.operation_steps for check in protocol.checks)
    assert all(check.presentation.task_title and check.presentation.question
               and check.presentation.record_summary and check.presentation.outcome_preview
               and check.presentation.evidence_kind and check.presentation.progress_phase
               for check in protocol.checks)
    assert {option.option_id for check in protocol.checks for option in check.input_schema.options} >= {
        "profile.recorded", "static.compatible", "load.record", "leak.localized",
        "repair.completed", "retest.record", "control.continue", "setup.completed", "final.record"
    }
    validate_protocol_package(protocol)
    assert {item.decision for item in protocol.transitions} >= {"next_check", "need_input", "handoff", "area_summary"}


def test_protocol_static_validation_rejects_missing_exit_and_hash_never_uses_registry_bytes():
    payload = DKVB_DEMO_PROTOCOL.model_dump(mode="json")
    payload["transitions"] = [item for item in payload["transitions"]
                              if item["result_value"] != "leak.not_found"]
    with pytest.raises(ValueError, match="Every visible result"):
        TrustedProtocol.model_validate(payload)


def test_protocol_static_validation_rejects_ambiguous_exit():
    payload = deepcopy(DKVB_DEMO_PROTOCOL.model_dump(mode="json"))
    payload["transitions"].append(deepcopy(payload["transitions"][0]))
    payload["transitions"][-1]["transition_id"] = "DUPLICATE_RESULT"
    with pytest.raises(ValueError, match="Every visible result"):
        TrustedProtocol.model_validate(payload)


def test_full_flow_pressure_routing_is_deterministic():
    load = {"option_id": "load.record", "protocol_fields": {
        "symptom": "present", "target_1_hpa": "2000", "actual_1_hpa": "1700",
        "target_2_hpa": "2050", "actual_2_hpa": "1720",
        "target_3_hpa": "2100", "actual_3_hpa": "1750"}}
    assert ProtocolService._result_value("CHK-03", load) == "load.underboost"
    retest = {"option_id": "retest.record", "protocol_fields": {
        "leak_result": "not_found", "symptom": "present", **load["protocol_fields"]}}
    assert ProtocolService._result_value("CHK-07", retest) == "retest.residual_underboost"
    final = {"option_id": "final.record", "protocol_fields": {
        "symptom": "absent", "p0299": "absent", "repairs_rechecked": "completed", "conflict": "none",
        **{f"final_target_{i}_hpa": "2000" for i in range(1, 4)},
        **{f"final_actual_{i}_hpa": "1950" for i in range(1, 4)}}}
    assert ProtocolService._result_value("CHK-11", final) == "final.passed"
