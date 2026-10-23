"""The worker claims only the job kinds it can run."""
import pytest

from app.infrastructure.job_store import RUNTIME_JOB_KINDS, JobStore


def test_runtime_kinds_are_the_manual_ingest_and_the_test_job():
    assert RUNTIME_JOB_KINDS == {"no_op", "reference_ingest"}


def test_default_claim_uses_runtime_kinds_even_without_worker_filter():
    store = JobStore.__new__(JobStore)
    captured = []
    store._claim = lambda *args: captured.append(args)
    store.claim("runtime", run_id="selected")
    assert captured == [("runtime", None, "selected", RUNTIME_JOB_KINDS)]


@pytest.mark.parametrize("kind", ["diagnosis", "report", "case_analysis", "ingest", "index", "unknown"])
def test_claim_rejects_kinds_no_handler_runs(kind):
    store = JobStore.__new__(JobStore)
    with pytest.raises(ValueError, match="Unknown job kind"):
        store.claim("runtime", allowed_kinds={"no_op", kind})
