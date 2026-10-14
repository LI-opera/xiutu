import hashlib
import json
import re
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.domain.policies import DomainError, check_revision
from app.domain.tasks import ACTIVE, TERMINAL, NoOpInput, RunSnapshot
from app.infrastructure.event_store import append_event
from app.infrastructure.index_state import state as index_state
from app.infrastructure.ingest_state import state as ingest_state
from app.infrastructure.orm import (
    cases,
    document_versions,
    graph_progress,
    idempotency_keys,
    jobs,
    runs,
)
from app.infrastructure.uow import UnitOfWork
from app.services.event_service import check_cursor, read_events


def owned(conn, actor, identifier):
    row = conn.execute(select(runs).where(runs.c.id == identifier)).mappings().one_or_none()
    if row is None:
        raise DomainError("NOT_FOUND", "Run not found", 404)
    owner = (
        row["owner_id"]
        if row["case_id"] is None
        else conn.execute(select(cases.c.owner_id).where(cases.c.id == row["case_id"])).scalar_one()
    )
    if owner != actor:
        raise DomainError("NOT_FOUND", "Run not found", 404)
    return row


def lock_case(conn, actor, identifier, revision=None):
    row = (
        conn.execute(
            select(cases)
            .where(cases.c.id == identifier, cases.c.owner_id == actor)
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise DomainError("NOT_FOUND", "Case not found", 404)
    if revision is not None:
        check_revision(row["revision"], revision)
    return row


def idle_case(conn, case_id):
    if (
        case_id is not None
        and conn.execute(
            select(runs.c.id).where(runs.c.case_id == case_id, runs.c.status.in_(ACTIVE))
        ).first()
    ):
        raise DomainError("ACTIVE_RUN", "Case already has an active run")


def idempotent(conn, actor, scope, key, body, action):
    if not key or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", key):
        raise DomainError("VALIDATION_ERROR", "Valid Idempotency-Key required", 422)
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    match = (
        idempotency_keys.c.actor_id == actor,
        idempotency_keys.c.route_scope == scope,
        idempotency_keys.c.key == key,
    )
    won = conn.execute(
        insert(idempotency_keys)
        .values(
            actor_id=actor,
            route_scope=scope,
            key=key,
            request_hash=digest,
            response_status=202,
            response_json={},
        )
        .on_conflict_do_nothing(index_elements=["actor_id", "route_scope", "key"])
        .returning(idempotency_keys.c.key)
    ).scalar_one_or_none()
    if won is None:
        saved = conn.execute(select(idempotency_keys).where(*match)).mappings().one()
        if saved["request_hash"] != digest:
            raise DomainError(
                "IDEMPOTENCY_CONFLICT", "Idempotency key belongs to a different request"
            )
        return saved["response_status"], saved["response_json"]
    status, response = action()
    conn.execute(
        update(idempotency_keys)
        .where(*match)
        .values(response_status=status, response_json=response)
    )
    return status, response


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


class RunService:
    def __init__(self, engine):
        self.engine = engine

    def submit_no_op(self, actor, data, key, case_id=None, expected_revision=None):
        data = NoOpInput.model_validate(data)
        with UnitOfWork(self.engine) as u:
            c = u.connection
            if case_id is not None:
                row = lock_case(c, actor, case_id)
                check_revision(row["revision"], expected_revision)
            elif expected_revision is not None:
                raise DomainError("VALIDATION_ERROR", "Revision requires a case", 422)
            body = dict(
                case_id=str(case_id) if case_id else None,
                revision=expected_revision,
                **data.model_dump(),
            )
            return idempotent(
                c,
                actor,
                "CLI no_op",
                key,
                body,
                lambda: enqueue(c, actor, "no_op", data.model_dump(), case_id, expected_revision),
            )

    def get(self, actor, identifier):
        with UnitOfWork(self.engine) as u:
            row = owned(u.connection, actor, identifier)
            job = (
                u.connection.execute(select(jobs).where(jobs.c.run_id == identifier))
                .mappings()
                .one()
            )
            return RunSnapshot(
                id=row["id"],
                case_id=row["case_id"],
                kind=row["kind"],
                status=row["status"],
                attempt=job["attempt"],
                max_attempts=job["max_attempts"],
                parent_run_id=row["parent_run_id"],
                error=row["error_json"],
                usage=row["usage_json"],
            ).model_dump(mode="json")

    def cancel(self, actor, identifier, key):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            row = owned(c, actor, identifier)
            if row["case_id"] is not None:
                lock_case(c, actor, row["case_id"])

            def action():
                c.execute(select(jobs).where(jobs.c.run_id == identifier).with_for_update()).one()
                run = (
                    c.execute(select(runs).where(runs.c.id == identifier).with_for_update())
                    .mappings()
                    .one()
                )
                status = run["status"]
                if status in TERMINAL:
                    return 200, dict(run_id=str(identifier), status=status)
                if status == "queued":
                    status = "cancelled"
                    c.execute(
                        update(jobs)
                        .where(jobs.c.run_id == identifier)
                        .values(status=status, lease_until=None)
                    )
                elif status == "running":
                    status = "cancel_requested"
                if status == "cancelled" and run["kind"] == "index":
                    index_state(c, identifier, {"code": "cancelled", "retryable": False})
                if status == "cancelled" and run["kind"] == "ingest":
                    ingest_state(c, identifier, "cancelled")
                if status == "cancelled" and run["kind"] == "diagnosis":
                    from app.infrastructure.orm import diagnosis_steps

                    prior_step_id = c.execute(select(graph_progress.c.step_id).where(
                        graph_progress.c.run_id == identifier)).scalar_one_or_none()
                    has_waiting_step = prior_step_id is not None and c.execute(
                        select(diagnosis_steps.c.id).where(
                            diagnosis_steps.c.id == prior_step_id,
                            diagnosis_steps.c.status == "waiting_input")
                    ).first() is not None
                    has_published_step = c.execute(select(diagnosis_steps.c.id).where(
                        diagnosis_steps.c.case_id == run["case_id"]).limit(1)).first() is not None
                    c.execute(update(graph_progress).where(graph_progress.c.run_id == identifier)
                              .values(phase="failed"))
                    c.execute(update(cases).where(cases.c.id == run["case_id"])
                              .values(status=("waiting_input" if has_waiting_step else
                                              "needs_review" if has_published_step else "draft")))
                if status != run["status"]:
                    c.execute(update(runs).where(runs.c.id == identifier).values(status=status))
                    append_event(c, identifier, "run." + status)
                return 202, dict(run_id=str(identifier), status=status)

            return idempotent(c, actor, "cancel:" + str(identifier), key, {}, action)

    def retry(self, actor, identifier, data, key):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            row = owned(c, actor, identifier)
            if row["case_id"] is not None:
                current = lock_case(c, actor, row["case_id"])
            elif data.expected_revision is not None:
                raise DomainError("VALIDATION_ERROR", "Revision requires a case", 422)

            def action():
                job = (
                    c.execute(select(jobs).where(jobs.c.run_id == identifier).with_for_update())
                    .mappings()
                    .one()
                )
                run = (
                    c.execute(select(runs).where(runs.c.id == identifier).with_for_update())
                    .mappings()
                    .one()
                )
                if run["case_id"] is not None:
                    check_revision(current["revision"], data.expected_revision)
                if run["kind"] == "index":
                    raise DomainError(
                        "RETRY_NOT_ALLOWED", "Use explicit version reindex for a new build"
                    )
                if run["kind"] == "diagnosis":
                    raise DomainError(
                        "RETRY_NOT_ALLOWED", "Diagnosis recovery requires a saved turn checkpoint"
                    )
                if run["kind"] == "case_analysis":
                    raise DomainError("RETRY_NOT_ALLOWED", "病例分析不会自动重试可能已发出的模型请求；请主动发起新分析")
                if job["attempt"] >= 3 or not (
                    run["status"] == "cancelled"
                    or (run["status"] == "failed" and run["error_json"].get("retryable") is True)
                ):
                    raise DomainError("RETRY_NOT_ALLOWED", "Run has no retryable remaining attempt")
                idle_case(c, run["case_id"])
                c.execute(update(runs).where(runs.c.id == identifier).values(status="superseded"))
                append_event(c, identifier, "run.superseded")
                response = enqueue(
                    c,
                    actor,
                    run["kind"],
                    run["input_payload"],
                    run["case_id"],
                    data.expected_revision,
                    run,
                    job["attempt"],
                )
                if run["kind"] == "ingest":
                    c.execute(
                        update(document_versions)
                        .where(document_versions.c.current_run_id == identifier)
                        .values(
                            current_run_id=UUID(response[1]["run_id"]),
                            parse_status="pending",
                            parse_error={},
                        )
                    )
                return response

            return idempotent(
                c, actor, "retry:" + str(identifier), key, data.model_dump(mode="json"), action
            )

    def cursor(self, actor, identifier, raw):
        with UnitOfWork(self.engine) as u:
            owned(u.connection, actor, identifier)
            return check_cursor(u.connection, identifier, raw)

    def events(self, actor, identifier, cursor):
        with UnitOfWork(self.engine) as u:
            row = owned(u.connection, actor, identifier)
            # Snapshot status first, events second: terminal writers commit events atomically.
            return read_events(u.connection, identifier, cursor), row["status"] in TERMINAL
