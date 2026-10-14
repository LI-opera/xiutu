"""C02 scope, navigation, and one-shot gateway checks without network calls."""

from types import SimpleNamespace

import pytest

from app.infrastructure.model_gateway import DeepSeekGateway, ModelError
from app.infrastructure.model_budget import BudgetLedger
from app.legacy_execution.case_analysis import substitute_advice, validate_advice
from app.services.case_analysis_projection import _question_targets
from app.topics import dkvb_b02


def test_derived_gap_targets_missing_raw_question():
    topic, _ = dkvb_b02.catalog()
    targets = _question_targets(topic, ["PRS-04", "PRS-02"],
                                [{"question_id": "PRS-01", "effective": True}])
    assert targets[0]["target_question_id"] == "PRS-02"
    assert "静态绝对压力" in targets[1]["name"]


def test_one_shot_structured_parse_never_repairs_or_retries():
    gateway = DeepSeekGateway.__new__(DeepSeekGateway)
    calls = []

    def fake_request(messages, **options):
        calls.append(options)
        return SimpleNamespace(content="not-json", tool_calls=[])

    gateway.request = fake_request
    from app.domain.case_analysis import CaseAdviceDraft

    with pytest.raises(ModelError) as error:
        gateway.generate_structured_once(CaseAdviceDraft, [])
    assert str(error.value) == "MODEL_JSON_INVALID_NO_RETRY"
    assert calls == [{"retry_transient": False, "response_format": {"type": "json_object"}}]


def test_missing_question_title_is_not_recast_as_pressure_test_instruction():
    frozen = {"observations": [], "source_context": {"excerpts": []},
              "action_catalog": {"actions": {}}, "allowed_scope": "supplement_or_handoff",
              "unresolved_questions": [{"question_id": "AIR-14", "name": "加压过程不超过0.5 bar",
                                        "target_question_id": "AIR-14"}],
              "synthesis": {"unavailable": [], "missing_question_ids": [], "conflicts": []}}
    result = validate_advice(frozen, substitute_advice(frozen))
    assert "AIR-14" in result["steps"][0]["action"]
    assert "0.5 bar" not in result["steps"][0]["action"]


def test_c03_budget_accepts_one_4096_token_reservation(tmp_path):
    ledger = BudgetLedger(tmp_path / "c03-budget.json")
    ledger.initialize("offline bounded fixture")
    ledger.reserve("case-revision-42:1", "deepseek-flash", "synthetic", 4096)
    assert ledger.read()["calls"]["case-revision-42:1"]["output_upper"] == 4096
