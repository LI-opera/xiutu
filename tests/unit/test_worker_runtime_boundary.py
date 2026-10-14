"""Retired task execution requires an explicit isolated-test worker."""

from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.legacy_worker_handlers import LegacyDispatcher
from app.worker import Worker


def test_legacy_worker_cannot_target_development_database():
    store = SimpleNamespace(engine=SimpleNamespace(url=SimpleNamespace(database="xiutu_dev")))
    with pytest.raises(ValueError, match="isolated test database"):
        Worker(store, legacy_execution=True)
    assert not Worker(store).legacy_execution


def test_isolated_legacy_dispatcher_preserves_publish_boundary(monkeypatch):
    from app.legacy_execution import graph

    run_id = uuid4()
    finished = Event()
    called = []

    class Graph:
        def __init__(self, store, lease, stopped, on_published, diagnostic_sink):
            called.append((store, lease, stopped, diagnostic_sink))
            self.on_published = on_published

        def execute(self):
            self.on_published()

    monkeypatch.setattr(graph, "DiagnosisGraph", Graph)
    store = object()
    lease = SimpleNamespace(job={"kind": "diagnosis", "run_id": run_id})
    stopped = Event()
    sink = object()
    result = LegacyDispatcher(sink).execute(store, lease, stopped, finished)
    assert result == (None, True, run_id)
    assert finished.is_set()
    assert called == [(store, lease, stopped, sink)]


@pytest.mark.parametrize(
    "kind,module_name,function_name",
    [
        ("report", "app.legacy_execution.report_graph", "run_report"),
        ("case_analysis", "app.legacy_execution.case_analysis", "run_case_analysis"),
    ],
)
def test_isolated_legacy_dispatcher_preserves_saved_result(
    monkeypatch, kind, module_name, function_name
):
    import importlib

    module = importlib.import_module(module_name)
    store, stopped, finished = object(), Event(), Event()
    lease = SimpleNamespace(job={"kind": kind})
    expected = {"saved": kind}
    monkeypatch.setattr(
        module, function_name, lambda store_arg, lease_arg, stopped_arg: expected
    )
    assert LegacyDispatcher().execute(store, lease, stopped, finished) == (
        expected, False, None
    )
