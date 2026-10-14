"""Bounded field-role grammar and immutable locator envelope regressions."""

import pytest
from app.validators.support import table_requires_spec


@pytest.mark.parametrize("header", ["| 范围（V） |", "| 电压 | engine=off |", "| 仅engine=off |"])
def test_header_comes_from_evidence_source_locator(header):
    locator = {"source": {"table_header": {"text": header}}}
    assert table_requires_spec("| P01 | 1–2 |", locator)
    assert not table_requires_spec("P01 是合成部件。", locator)
