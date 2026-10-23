"""Only template matching creates cases; the retired creation fields are rejected by the schema."""
import pytest
from pydantic import ValidationError

from app.domain.schemas import CreateCase

VEHICLE = {"brand": "大众", "model": "探岳", "year": 2019}


def test_creation_requires_the_template_flow():
    with pytest.raises(ValidationError):
        CreateCase(vehicle=VEHICLE, fault_description="增压不足", fault_codes=["P0299"])
    case = CreateCase(workbench_flow="template-match-v1", vehicle=VEHICLE,
                      fault_description="增压不足", fault_codes=["p0299"])
    assert case.fault_codes == ["P0299"]


@pytest.mark.parametrize("field,value", [("topic_version", "2.2.1-b02"),
                                         ("diagnosis_mode", "conservative"),
                                         ("policy_version", "r1")])
def test_retired_creation_fields_are_unknown(field, value):
    with pytest.raises(ValidationError):
        CreateCase(workbench_flow="template-match-v1", vehicle=VEHICLE,
                   fault_description="增压不足", **{field: value})
