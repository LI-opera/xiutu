"""Bounded, source-preserving expansion before the model sees candidate evidence."""

import pytest
from app.legacy_execution.runner import _initial_source_chunks
from app.infrastructure.model_gateway import ModelError


def chunk(number, *, version="v1", index="i1"):
    return {"chunk_id": f"c{number}", "document_version_id": version,
            "index_id": index, "text": f"source {number}"}


class Executor:
    def __init__(self, *, mismatch=False, fail=False):
        self.calls = []
        self.mismatch, self.fail = mismatch, fail

    def execute(self, context, name, body, key):
        self.calls.append((name, body, key))
        if name == "search_manuals":
            return {"ok": True, "data": {"chunks": [chunk(2), chunk(5), chunk(9)]}}
        if self.fail:
            return {"ok": False, "error": {"code": "SOURCE_INVALID"}}
        if body["chunk_id"] == "c2":
            return {"ok": True, "data": {"chunks": [chunk(1), chunk(2), chunk(3)]}}
        return {"ok": True, "data": {"chunks": [
            chunk(4), chunk(5), chunk(6, version="foreign" if self.mismatch else "v1")]}}


def test_bounded_context_expands_and_deduplicates_without_guessing_scope():
    executor = Executor()
    result = _initial_source_chunks(executor, object(), "synthetic query")
    assert [x["chunk_id"] for x in result] == ["c1", "c2", "c3", "c4", "c5", "c6", "c9"]
    assert [x[0] for x in executor.calls] == [
        "search_manuals", "get_evidence_context", "get_evidence_context",
        "get_evidence_context"]
    assert executor.calls[0][1]["top_k"] == 5
    assert all(x[1]["neighbors"] == 2 for x in executor.calls[1:])
    assert len({x[2] for x in executor.calls[1:]}) == 3


@pytest.mark.parametrize("mismatch,fail", [(True, False), (False, True)])
def test_context_invalid_or_unavailable_is_not_silently_dropped(mismatch, fail):
    with pytest.raises(ModelError):
        _initial_source_chunks(Executor(mismatch=mismatch, fail=fail), object(), "query")
