from decimal import Decimal
from uuid import uuid4

import pytest
from app.domain.measurements import CompareInput, SpecInput
from app.tools.measurement import MeasurementComparator
from pydantic import ValidationError


def definition(**extra):
    fields = dict(
        evidence_id=uuid4(),
        component_key="SYNTHETIC",
        quantity="temperature",
        unit="C",
        lower="0",
        upper="100",
        lower_inclusive=True,
        upper_inclusive=True,
        conditions={"engine": "off"},
    )
    fields.update(extra)
    return SpecInput(**fields).model_dump(mode="json")


@pytest.mark.parametrize(
    "value,unit,expected",
    [
        ("32", "F", "within_range"),
        ("212", "F", "within_range"),
        ("31.999999999999999999999999", "F", "out_of_range"),
        ("212.00000000000000000000001", "F", "out_of_range"),
        ("0", "C", "within_range"),
        ("100", "C", "within_range"),
        (None, "C", "value_missing"),
    ],
)
def test_exact_temperature(value, unit, expected):
    result = MeasurementComparator.compare(
        definition(),
        CompareInput(value=value, quantity="temperature", unit=unit, conditions={"engine": "off"}),
    )
    assert result["outcome"] == expected


@pytest.mark.parametrize(
    "value", [True, False, 0, 1.1, "NaN", "Infinity", "-Inf", "1e99", "1e-31", "1" * 31, ""]
)
def test_invalid_decimal(value):
    with pytest.raises(ValidationError):
        CompareInput(value=value, quantity="pressure", unit="bar")


@pytest.mark.parametrize(
    "options",
    [
        {"lower": "2", "upper": "1"},
        {"lower": "1", "upper": "1", "upper_inclusive": False},
        {"lower": None, "upper": None, "lower_inclusive": False, "upper_inclusive": False},
        {"lower": None},
        {"quantity": "pressure"},
        {"conditions": {}},
    ],
)
def test_invalid_spec(options):
    with pytest.raises(ValidationError):
        definition(**options)


def test_controlled_conversion_conditions_and_open_bounds():
    spec = definition(
        quantity="pressure",
        unit="bar",
        lower="1.000000000000000000000000001",
        upper=None,
        upper_inclusive=False,
    )
    data = CompareInput(
        value="100.0000000000000000000000001",
        quantity="pressure",
        unit="kPa",
        conditions={"engine": "off"},
    )
    assert MeasurementComparator.compare(spec, data)["outcome"] == "within_range"
    spec["lower_inclusive"] = False
    assert MeasurementComparator.compare(spec, data)["outcome"] == "out_of_range"
    data.value = "200"
    assert MeasurementComparator.compare(spec, data)["outcome"] == "within_range"
    data.conditions = {}
    assert MeasurementComparator.compare(spec, data)["outcome"] == "conditions_missing"
    data.conditions = {"engine": "on"}
    assert MeasurementComparator.compare(spec, data)["outcome"] == "conditions_mismatch"
    data.quantity = "voltage"
    assert MeasurementComparator.compare(spec, data)["outcome"] == "quantity_mismatch"
    data.quantity = "pressure"
    data.unit = "V"
    assert MeasurementComparator.compare(spec, data)["outcome"] == "unit_mismatch"


@pytest.mark.parametrize(
    "quantity,unit,value,target",
    [
        ("voltage", "mV", "1000", "V"),
        ("resistance", "kohm", "0.001", "ohm"),
        ("pressure", "Pa", "100000", "bar"),
    ],
)
def test_scale(quantity, unit, value, target):
    spec = definition(quantity=quantity, unit=target, lower="1", upper="1")
    result = MeasurementComparator.compare(
        spec, CompareInput(value=value, quantity=quantity, unit=unit, conditions={"engine": "off"})
    )
    assert result["outcome"] == "within_range" and Decimal(result["converted"]) == Decimal("1")
