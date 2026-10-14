"""Retired case construction must not enter the formal creation transaction."""
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domain.policies import DomainError
from app.domain.schemas import CreateCase
from app.legacy_case_creation import LegacyCaseService
from app.services.case_service import CaseService


@pytest.mark.parametrize("topic_version", [None, "2.2.0-b01", "2.2.1-b02"])
def test_formal_service_rejects_old_creation_before_accessing_database(topic_version):
    data = CreateCase(vehicle={"model": "historical"}, fault_description="archive",
                      topic_version=topic_version)
    with pytest.raises(DomainError) as denied:
        CaseService(None, b"test").create(uuid4(), data, "old-flow")
    assert denied.value.code == "LEGACY_CASE_READ_ONLY"


@pytest.mark.parametrize("database", ["xiutu_dev", "production", None])
def test_legacy_constructor_refuses_nonisolated_database(database):
    engine = SimpleNamespace(url=SimpleNamespace(database=database))
    data = CreateCase(vehicle={"model": "historical"}, fault_description="archive")
    with pytest.raises(ValueError, match="isolated test database"):
        LegacyCaseService(engine, b"test").create(uuid4(), data, "old-flow")
