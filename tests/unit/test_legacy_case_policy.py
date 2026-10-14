from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.api import cases as case_api
from app.api import measurements as measurements_api
from app.api.legacy_case_policy import (
    reject_legacy_creation,
    require_template_case,
    retire_legacy_case_route,
)
from app.domain.policies import DomainError
from app.services import case_service


class Cases:
    def __init__(self, flow):
        self.flow = flow
        self.read_ids = []

    def get(self, actor, case_id):
        self.read_ids.append((actor, case_id))
        return {"intake_snapshot": {"workbench_flow": self.flow}}


@pytest.mark.parametrize("flow", [None, "old-workbench-v2", "template-match-v1"])
def test_archived_write_boundary_preserves_only_current_template(flow):
    cases = Cases(flow)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(case_service=cases)))
    case_id = uuid4()
    if flow == "template-match-v1":
        require_template_case(request, "owner", case_id)
        with pytest.raises(DomainError, match="已停用") as retired:
            retire_legacy_case_route(request, "owner", case_id)
        assert retired.value.code == "LEGACY_FLOW_RETIRED"
    else:
        with pytest.raises(DomainError) as archived:
            require_template_case(request, "owner", case_id)
        assert archived.value.code == "LEGACY_CASE_READ_ONLY"
        with pytest.raises(DomainError) as retired:
            retire_legacy_case_route(request, "owner", case_id)
        assert retired.value.code == "LEGACY_CASE_READ_ONLY"
    assert cases.read_ids and all(entry == ("owner", case_id) for entry in cases.read_ids)


def test_new_case_entry_accepts_only_template_flow():
    reject_legacy_creation(SimpleNamespace(workbench_flow="template-match-v1"))
    with pytest.raises(DomainError) as archived:
        reject_legacy_creation(SimpleNamespace(workbench_flow=None))
    assert archived.value.code == "LEGACY_CASE_READ_ONLY"


@pytest.mark.parametrize(
    ("flow", "expected_code"),
    [("template-match-v1", "LEGACY_FLOW_RETIRED"), (None, "LEGACY_CASE_READ_ONLY")],
)
def test_retired_public_writes_never_reach_legacy_services(flow, expected_code):
    case_service = Cases(flow)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(case_service=case_service)))
    principal = SimpleNamespace(actor_id="owner")
    case_id, item_id = uuid4(), uuid4()
    routes = (
        lambda: case_api.submit_observation(case_id, object(), request, principal, "key"),
        lambda: case_api.correct_observation(case_id, item_id, object(), request, principal, "key"),
        lambda: case_api.activate_diagnosis_area(case_id, item_id, object(), request, principal, "key"),
        lambda: case_api.conclude_diagnosis_area(case_id, item_id, object(), request, principal, "key"),
        lambda: measurements_api.bind(case_id, object(), request, principal, "key"),
    )
    for route in routes:
        with pytest.raises(DomainError) as denied:
            route()
        assert denied.value.code == expected_code
    assert case_service.read_ids == [("owner", case_id)] * len(routes)


def test_historical_case_list_label_is_read_only_without_changing_saved_status(monkeypatch):
    class Empty:
        def mappings(self):
            return self

        def one_or_none(self):
            return None

        def scalar_one_or_none(self):
            return None

        def first(self):
            return None

    class Connection:
        def execute(self, _statement):
            return Empty()

    monkeypatch.setattr(case_service, "snapshot", lambda row: {"status": row["status"]})
    row = {"id": uuid4(), "owner_id": uuid4(), "graph_epoch": 0,
           "intake_snapshot": {"topic_binding": {"version": "2.2.1-b02"}},
           "status": "waiting_input"}
    view = case_service.CaseService(None, b"test").with_active(Connection(), row)
    assert view["status"] == "waiting_input"
    assert view["experience"]["category"] == "reference"
    assert view["experience"]["label"] == "历史病例 · 只读"
