"""Matched-template treatment remains a distinct user-recorded workflow."""
import pytest
from pydantic import ValidationError

from app.api.template_repairs import RepairInput, RetestInput
from app.domain.policies import DomainError
from app.infrastructure.orm import template_repair_rounds
from app.services.template_repair_service import _areas


def test_frozen_template_limits_repair_area_without_a_fixed_fault_branch():
    row = {"intake_snapshot": {"workbench_flow": "template-match-v1",
            "template_content": {"areas": [{"id": "pressure", "title": "压力测量"},
                                           {"id": "air", "title": "增压空气通路"}]}}}
    assert _areas(row) == {"pressure": "压力测量", "air": "增压空气通路"}
    with pytest.raises(DomainError):
        _areas({"intake_snapshot": {}})


def test_repair_and_retest_are_separate_records_with_explicit_new_evidence():
    columns = {column.name for column in template_repair_rounds.columns}
    assert {"pre_repair_revision", "repair_action", "retest_condition", "retest_outcome",
            "retest_evidence", "retested_at", "next_area_id"} <= columns
    assert RepairInput(expected_revision=3, area_id="pressure", repair_action="已完成现场检查")
    assert RetestInput(expected_revision=4, retest_condition="same", retest_outcome="persists",
                       retest_evidence="新采集记录", next_area_id="air")
    with pytest.raises(ValidationError):
        RetestInput(expected_revision=4, retest_condition="same", retest_outcome="normal",
                    retest_evidence="新采集记录")
