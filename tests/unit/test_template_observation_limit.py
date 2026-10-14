"""Regression: report snapshot must not cap a full template question library."""
from uuid import uuid4
import pytest
from app.domain.policies import DomainError
from app.services.report_policy import snapshot

@pytest.mark.parametrize('binding,unlimited', [
    ({'workbench_flow': 'template-match-v1'}, True),
    ({'topic_binding': {'version': '2.2.1-b02'}}, True),
    ({}, False),
])
def test_report_snapshot_retains_all_effective_workbench_records(monkeypatch, binding, unlimited):
    cid, actor = uuid4(), uuid4()
    case = {'id': cid, 'owner_id': actor, 'revision': 80, 'graph_epoch': 1, 'intake_snapshot': binding}
    saved = [{'id': uuid4()} for _ in range(63)]
    class Result:
        def mappings(self): return self
        def one_or_none(self): return case
        def all(self): return []
    class Connection:
        def execute(self, query): return Result()
    def read(self, case_id, area_id, revision, *, max_results=50):
        assert (case_id, area_id, revision) == (cid, None, 80)
        if max_results is not None and len(saved) > max_results:
            raise DomainError('RESULT_TOO_LARGE', 'Observation result exceeds limit', 422)
        return saved
    monkeypatch.setattr('app.services.report_policy.ObservationRepository.read', read)
    if unlimited:
        result = snapshot(Connection(), actor, cid, None)
        assert set(result['observations']) == {item['id'] for item in saved}
    else:
        with pytest.raises(DomainError, match='Observation result exceeds limit'):
            snapshot(Connection(), actor, cid, None)
