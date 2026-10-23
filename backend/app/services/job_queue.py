"""Queue background work: one run row (status, events) and one job row the worker claims."""
from uuid import uuid4

from sqlalchemy import select

from app.domain.policies import DomainError
from app.domain.tasks import ACTIVE
from app.infrastructure.event_store import append_event
from app.infrastructure.orm import jobs, runs


def idle_case(conn, case_id):
    if (
        case_id is not None
        and conn.execute(
            select(runs.c.id).where(runs.c.case_id == case_id, runs.c.status.in_(ACTIVE))
        ).first()
    ):
        raise DomainError("ACTIVE_RUN", "Case already has an active run")


def enqueue(conn, actor, kind, payload, case_id=None, revision=None, parent=None, attempt=0,
            new_turn=False):
    idle_case(conn, case_id)
    identifier = uuid4()
    conn.execute(
        runs.insert().values(
            id=identifier,
            owner_id=actor if case_id is None else None,
            case_id=case_id,
            kind=kind,
            input_payload=payload,
            input_revision=revision,
            parent_run_id=parent["id"] if parent else None,
            workflow_id=parent["workflow_id"] if parent else uuid4(),
            turn_id=(uuid4() if new_turn else parent["turn_id"]) if parent else uuid4(),
            budget_json={"max_attempts": 3},
        )
    )
    conn.execute(
        jobs.insert().values(
            run_id=identifier, kind=kind, payload=payload, attempt=attempt, max_attempts=3
        )
    )
    append_event(conn, identifier, "run.queued", {"kind": kind, "test_only": kind == "no_op"})
    return 202, dict(
        run_id=str(identifier), status="queued", parent_run_id=str(parent["id"]) if parent else None
    )
