"""The default store cannot silently opt into retired job execution."""
from types import SimpleNamespace

import pytest

from app.infrastructure.job_store import RUNTIME_JOB_KINDS, JobStore


def test_default_claim_uses_runtime_kinds_even_without_worker_filter():
    store = JobStore.__new__(JobStore)
    captured = []
    store._claim = lambda *args: captured.append(args)
    store.claim("runtime", run_id="selected")
    assert captured == [("runtime", None, "selected", RUNTIME_JOB_KINDS)]


@pytest.mark.parametrize("kind", ["diagnosis", "report", "case_analysis", "unknown"])
def test_runtime_claim_cannot_override_filter_with_retired_kinds(kind):
    store = JobStore.__new__(JobStore)
    with pytest.raises(ValueError, match="explicit isolated legacy"):
        store.claim("runtime", allowed_kinds={"no_op", kind})


@pytest.mark.parametrize("database", ["xiutu_dev", "production", None])
def test_legacy_claim_refuses_nonisolated_database(database):
    store = JobStore.__new__(JobStore)
    store.engine = SimpleNamespace(url=SimpleNamespace(database=database))
    with pytest.raises(ValueError, match="isolated test database"):
        store.claim_legacy("old-worker")


def test_explicit_isolated_claim_preserves_legacy_replay_arguments():
    store = JobStore.__new__(JobStore)
    store.engine = SimpleNamespace(url=SimpleNamespace(database="xiutu_test_replay"))
    captured = []
    store._claim = lambda *args: captured.append(args)
    store.claim_legacy("replay", run_id="old-run", allowed_kinds={"diagnosis"})
    assert captured == [("replay", None, "old-run", {"diagnosis"})]
