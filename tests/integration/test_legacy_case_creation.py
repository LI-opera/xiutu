"""Explicit replay construction remains isolated while historical reads survive."""
from uuid import UUID, uuid4

import pytest
from app.domain.policies import DomainError
from app.domain.schemas import CreateCase
from app.infrastructure.uow import make_engine
from app.legacy_case_creation import LegacyCaseService
from app.services.case_service import CaseService

pytestmark = pytest.mark.database


@pytest.mark.parametrize("version", ["2.2.0-b01", "2.2.1-b02"])
def test_old_topic_is_constructed_only_by_explicit_legacy_service(database_url, version):
    actor = uuid4()
    data = CreateCase(
        vehicle={"model": "虚拟探岳 DKVB 演示台架", "year": 2019, "engine_code": "DKVB-DEMO"},
        fault_description="Isolated historical construction regression", fault_codes=["P0299"],
        topic_version=version, diagnosis_mode="conservative",
        topic_intake={"symptom_condition": "mid_load", "safety_gate": "none"},
    )
    engine = make_engine(database_url)
    try:
        formal = CaseService(engine, b"test", profile="synthetic")
        with pytest.raises(DomainError) as denied:
            formal.create(actor, data, "formal-old")
        assert denied.value.code == "LEGACY_CASE_READ_ONLY"
        legacy = LegacyCaseService(engine, b"test", profile="synthetic")
        result = legacy.create(actor, data, "explicit-old")
        assert legacy.create(actor, data, "explicit-old") == result
        archived = formal.get(actor, UUID(result[1]["id"]))
        assert archived["intake_snapshot"]["topic_binding"]["version"] == version
        assert archived["experience"]["label"] == "历史病例 · 只读"
    finally:
        engine.dispose()
