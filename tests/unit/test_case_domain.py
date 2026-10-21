import pytest
from app.domain.policies import DomainError, check_revision
from app.domain.schemas import CreateCase
from pydantic import ValidationError

VALID = {
    "vehicle": {"model": "Synthetic car", "engine_family": "family", "engine_code": "CODE"},
    "fault_description": "Synthetic fault",
}


@pytest.mark.parametrize(
    "extra", [{"owner_id": "fake"}, {"revision": 1}, {"corpus_manifest": ["fake"]}, {"unknown": 1}]
)
def test_extra_forbidden(extra):
    with pytest.raises(ValidationError):
        CreateCase.model_validate(VALID | extra)


@pytest.mark.parametrize(
    "vehicle",
    [
        {"model": " "},
        {"model": "x", "owner_id": "fake"},
        {"model": "x", "year": True},
        {"model": "x", "year": "2020"},
        {"model": "x", "vin": "INVALID"},
    ],
)
def test_nested_validation(vehicle):
    with pytest.raises(ValidationError):
        CreateCase.model_validate(VALID | {"vehicle": vehicle})


def test_blank_engine_code_means_not_provided():
    # Template intake allows a vehicle without an engine code; blank is stored as unknown.
    case = CreateCase.model_validate(VALID | {"vehicle": {"model": "x", "engine_code": "  "}})
    assert case.vehicle.engine_code is None


def test_normalization():
    a = CreateCase.model_validate(
        VALID
        | {"fault_description": " Synthetic fault ", "fault_codes": [" p0010 ", "P0010", "p0001"]}
    )
    assert a.fault_codes == ["P0001", "P0010"] and a.fault_description == "Synthetic fault"
    assert a.vehicle.engine_code != a.vehicle.engine_family


@pytest.mark.parametrize("current,expected", [(0, 1), (3, 2)])
def test_revision_conflict(current, expected):
    with pytest.raises(DomainError) as e:
        check_revision(current, expected)
    assert e.value.code == "REVISION_CONFLICT" and e.value.details["current_revision"] == current


@pytest.mark.parametrize("revision", [-1, True, "0"])
def test_revision_invalid(revision):
    with pytest.raises(DomainError):
        check_revision(0, revision)


def test_revision_match():
    check_revision(0, 0)
