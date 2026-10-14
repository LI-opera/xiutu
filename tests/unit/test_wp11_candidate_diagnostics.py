"""Only trusted, finite validator identifiers may enter the private trace."""

import json

from app.legacy_execution.runner import _proposal_diagnostic


def test_diagnostic_sink_only_receives_bounded_identifiers():
    events = []
    _proposal_diagnostic(
        events.append, "initial",
        candidate={"type": "propose_step", "title": "SYNTHETIC_SECRET"},
        checked={"disposition": "needs_input", "issues": [
            {"code": "LOCATION_MISSING", "path": "location", "detail": "SYNTHETIC_SECRET"},
            {"code": "SYNTHETIC_SECRET", "path": "private marker", "detail": "raw"},
        ]},
    )
    assert events[0]["issues"] == [
        {"code": "LOCATION_MISSING", "path": "location"},
        {"code": "UNAVAILABLE", "path": "unavailable"},
    ]
    assert "SYNTHETIC_SECRET" not in json.dumps(events)
    assert events[0]["candidate_type"] == "propose_step"
    _proposal_diagnostic(lambda _: (_ for _ in ()).throw(OSError()), "initial")


def test_schema_and_repair_budget_are_separate_from_business_rejection():
    events = []
    _proposal_diagnostic(events.append, "initial", schema_invalid=True,
                         error_code="MODEL_SCHEMA_INVALID")
    _proposal_diagnostic(events.append, "repair_budget", repair_used=True,
                         error_code="REPAIR_EXHAUSTED")
    assert [x["stage"] for x in events] == ["initial", "repair_budget"]
    assert events[0]["schema_status"] == "invalid"
    assert events[0]["candidate_type"] is None
    assert events[1]["repair_used"] is True
    assert events[1]["error_code"] == "REPAIR_EXHAUSTED"
