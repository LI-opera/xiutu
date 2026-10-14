import pytest
from app.tools.registry import export_schemas
from app.tools.schemas import INPUTS
from pydantic import ValidationError


@pytest.mark.parametrize("name", list(INPUTS))
def test_model_cannot_supply_authority(name):
    with pytest.raises(ValidationError):
        INPUTS[name].model_validate(
            dict(owner="x", case_id="x", manifest=[], profile="synthetic", budget=999)
        )


def test_five_real_langchain_schemas():
    out = export_schemas()
    assert len(out["schemas"]) == 5 and len(out["sha256"]) == 64
    for name, s in out["schemas"].items():
        assert s["input"]["additionalProperties"] is False
        assert s["langchain"]["function"]["name"] == name
        assert s["langchain"]["function"]["parameters"]["additionalProperties"] is False


def test_export_keeps_typed_condition_map():
    from uuid import uuid4

    from jsonschema import Draft202012Validator

    schema = export_schemas()["schemas"]["compare_measurement"]["langchain"]["function"][
        "parameters"
    ]
    Draft202012Validator(schema).validate(
        dict(spec_id=str(uuid4()), value="1.0001", unit="V", conditions={"engine": "off"})
    )
    assert schema["properties"]["conditions"]["additionalProperties"] == {"type": "string"}


def test_scope_omission_cannot_erase_server_constraint():
    from app.domain.policies import DomainError
    from app.domain.retrieval import VehicleScope
    from app.tools.manual_tools import narrow

    vehicle = {"model": "Exact", "engine_family": "F", "engine_code": "CODE"}
    assert narrow(vehicle, VehicleScope(engine_code=None)) == vehicle
    with pytest.raises(DomainError) as e:
        narrow(vehicle, VehicleScope(engine_code="OTHER"))
    assert e.value.code == "SCOPE_CONFLICT"
