"""Retired SQL support must fail before touching a nonisolated database."""
from types import SimpleNamespace

import pytest

from app.infrastructure.job_store import JobStore


@pytest.mark.parametrize("operation,args", [
    ("staged_diagnosis", (None,)),
    ("reconcile_wait", ("old-run",)),
    ("reconcile_pending", ()),
    ("published", ("old-run",)),
    ("stage_diagnosis", (None, {})),
    ("reserve_diagnosis_repair", (None,)),
    ("finish", (SimpleNamespace(job={"kind": "diagnosis"}),)),
    ("finish", (SimpleNamespace(job={"kind": "report"}),)),
    ("finish", (SimpleNamespace(job={"kind": "case_analysis"}),)),
    ("_cancel_claim", (None, {"kind": "case_analysis"})),
    ("_terminal", (None, {"kind": "diagnosis"}, "failed", {})),
])
def test_retired_publication_and_recovery_refuse_development_database(operation, args):
    store = JobStore.__new__(JobStore)
    store.engine = SimpleNamespace(url=SimpleNamespace(database="xiutu_dev"))
    with pytest.raises(ValueError, match="isolated test database"):
        getattr(store, operation)(*args)
