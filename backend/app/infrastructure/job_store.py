"""Short transactions; one unpooled advisory-lock connection per active attempt."""

import hashlib
import random
import threading
from dataclasses import dataclass, field

from sqlalchemy import and_, create_engine, or_, select, text, update
from sqlalchemy.pool import NullPool

from app.domain.policies import DomainError
from app.domain.tasks import TERMINAL
from app.infrastructure.db_target import validate_target
from app.infrastructure.event_store import append_event
from app.infrastructure.orm import jobs, runs
from app.infrastructure.uow import make_engine


RUNTIME_JOB_KINDS = frozenset({"no_op", "reference_ingest"})


class LeaseLost(Exception):
    pass


@dataclass
class Lease:
    connection: object
    job: dict
    worker: str
    pid: int
    mutex: object = field(default_factory=threading.Lock)
    lost: bool = False
    final_deadline: object = None

    def close(self):
        with self.mutex:
            self.lost = True
            # NullPool physically closes this session, releasing ONLY its locks.
            self.connection.close()


def lock_key(identifier):
    return int.from_bytes(
        hashlib.sha256(("xiutu-task:" + str(identifier)).encode()).digest()[:8], "big", signed=True
    )


def due():
    return or_(
        and_(jobs.c.status == "queued", jobs.c.available_at <= text("clock_timestamp()")),
        and_(jobs.c.status == "running", jobs.c.lease_until <= text("clock_timestamp()")),
    )


class JobStore:
    def __init__(self, url, lease_seconds=60, settings=None):
        target = validate_target(url, "migration")
        if lease_seconds != 60:
            validate_target(url, "test")
        if not 0 < lease_seconds <= 60:
            raise ValueError("Invalid lease duration")
        self.engine = make_engine(url)
        self.locks = create_engine(
            target.sqlalchemy_url(),
            connect_args=target.connect_kwargs(),
            poolclass=NullPool,
            hide_parameters=True,
        )
        self.lease_seconds = lease_seconds
        self.settings = settings

    def close(self):
        self.engine.dispose()
        self.locks.dispose()

    def claim(self, worker, hook=None, run_id=None, allowed_kinds=None):
        """Claim the next due job of a kind this worker handles."""
        kinds = RUNTIME_JOB_KINDS if allowed_kinds is None else frozenset(allowed_kinds)
        if not kinds.issubset(RUNTIME_JOB_KINDS):
            raise ValueError("Unknown job kind")
        return self._claim(worker, hook, run_id, kinds)

    def _claim(self, worker, hook=None, run_id=None, allowed_kinds=None):
        allowed_kinds = None if allowed_kinds is None else frozenset(allowed_kinds)
        if allowed_kinds is not None and not allowed_kinds:
            return None
        kind_filter = jobs.c.kind.in_(allowed_kinds) if allowed_kinds is not None else True
        with self.engine.connect() as c:
            candidates = (
                c.execute(
                    select(jobs.c.id, jobs.c.run_id, runs.c.case_id)
                    .join(runs, jobs.c.run_id == runs.c.id)
                    .where(due(), jobs.c.run_id == run_id if run_id else True, kind_filter)
                    .order_by(jobs.c.available_at, jobs.c.id)
                    .limit(100)
                )
                .mappings()
                .all()
            )
        for candidate in candidates:
            c = self.locks.connect()
            keep = False
            try:
                locked = c.execute(
                    text("SELECT pg_try_advisory_lock(:key)"),
                    {"key": lock_key(candidate["case_id"] or candidate["run_id"])},
                ).scalar_one()
                pid = c.execute(text("SELECT pg_backend_pid()")).scalar_one()
                c.commit()
                if not locked:
                    continue
                with c.begin():
                    c.execute(text("SET LOCAL statement_timeout = '5000ms'"))
                    job = (
                        c.execute(
                            select(jobs)
                            .where(jobs.c.id == candidate["id"], due(), kind_filter)
                            .with_for_update(skip_locked=True)
                        )
                        .mappings()
                        .one_or_none()
                    )
                    if job is None:
                        continue
                    run = (
                        c.execute(select(runs).where(runs.c.id == job["run_id"]).with_for_update())
                        .mappings()
                        .one()
                    )
                    if run["status"] == "cancel_requested":
                        self._cancel_claim(c, job)
                        continue
                    if run["status"] in TERMINAL:
                        continue
                    if job["attempt"] >= min(3, job["max_attempts"]):
                        self._terminal(
                            c, job, "failed", {"code": "ATTEMPTS_EXHAUSTED", "retryable": False}
                        )
                        continue
                    updated = (
                        c.execute(
                            update(jobs)
                            .where(jobs.c.id == job["id"])
                            .values(
                                status="running",
                                attempt=jobs.c.attempt + 1,
                                lease_token=jobs.c.lease_token + 1,
                                lease_owner=worker,
                                lease_until=text(
                                    "clock_timestamp() + :seconds * interval '1 second'"
                                ),
                            )
                            .returning(jobs),
                            {"seconds": self.lease_seconds},
                        )
                        .mappings()
                        .one()
                    )
                    c.execute(
                        update(runs)
                        .where(runs.c.id == job["run_id"])
                        .values(status="running", error_json={})
                    )
                    append_event(c, job["run_id"], "run.started", {"attempt": updated["attempt"]})
                    if hook:
                        hook("before_claim_commit", dict(updated))
                keep = True
                return Lease(c, dict(updated), worker, pid)
            finally:
                if not keep:
                    c.close()
        return None

    def _valid(self, lease):
        c = lease.connection
        if lease.lost or c.closed or c.invalidated:
            raise LeaseLost()
        if c.execute(text("SELECT pg_backend_pid()")).scalar_one() != lease.pid:
            raise LeaseLost()
        job = (
            c.execute(select(jobs).where(jobs.c.id == lease.job["id"]).with_for_update())
            .mappings()
            .one()
        )
        run = (
            c.execute(select(runs).where(runs.c.id == job["run_id"]).with_for_update())
            .mappings()
            .one()
        )
        now = c.execute(text("SELECT clock_timestamp()")).scalar_one()
        if (
            job["status"] != "running"
            or job["lease_owner"] != lease.worker
            or job["lease_token"] != lease.job["lease_token"]
            or job["lease_until"] <= now
            or run["status"] not in {"running", "cancel_requested"}
        ):
            raise LeaseLost()
        return job, run

    def heartbeat(self, lease):
        with lease.mutex:
            try:
                with lease.connection.begin():
                    job, run = self._valid(lease)
                    lease.connection.execute(
                        update(jobs)
                        .where(jobs.c.id == job["id"])
                        .values(
                            lease_until=text("clock_timestamp() + :seconds * interval '1 second'")
                        ),
                        {"seconds": self.lease_seconds},
                    )
                    return run["status"] == "cancel_requested"
            except BaseException:
                lease.lost = True
                raise

    def _finish_valid(self, lease, deadline):
        # Called after ALL publication SQL, while the original job/run row locks
        # and advisory session are still held. Terminal SQL clears lease_until;
        # compare the saved, validated deadline rather than that cleared column.
        c = lease.connection
        if lease.lost or c.closed or c.invalidated:
            raise LeaseLost()
        owner, token, pid, now = c.execute(
            select(
                jobs.c.lease_owner,
                jobs.c.lease_token,
                text("pg_backend_pid()"),
                text("clock_timestamp()"),
            ).where(jobs.c.id == lease.job["id"])
        ).one()
        if (
            owner != lease.worker
            or token != lease.job["lease_token"]
            or pid != lease.pid
            or now >= deadline
        ):
            raise LeaseLost()

    def finish(self, lease, error=None, transient=False, result=None):
        with lease.mutex:
            try:
                with lease.connection.begin():
                    c = lease.connection
                    job, run = self._valid(lease)
                    if run["status"] == "cancel_requested":
                        self._terminal(c, job, "cancelled", {})
                    elif error is None:
                        self._terminal(c, job, "succeeded", {})
                    elif transient and job["attempt"] < min(3, job["max_attempts"]):
                        delay = (2, 8)[job["attempt"] - 1] + random.uniform(0, 0.25)
                        c.execute(
                            update(jobs)
                            .where(jobs.c.id == job["id"])
                            .values(
                                status="queued",
                                lease_until=None,
                                available_at=text(
                                    "clock_timestamp() + :delay * interval '1 second'"
                                ),
                            ),
                            {"delay": delay},
                        )
                        c.execute(
                            update(runs)
                            .where(runs.c.id == job["run_id"])
                            .values(status="queued", error_json={"code": error, "retryable": True})
                        )
                        append_event(
                            c,
                            job["run_id"],
                            "run.retry_scheduled",
                            {"attempt": job["attempt"], "delay_seconds": delay},
                        )
                    else:
                        self._terminal(c, job, "failed", {"code": error, "retryable": transient})
                    # Final authorization point: no further application SQL before
                    # COMMIT. Failure rolls back chunks, version, status AND events.
                    self._finish_valid(lease, job["lease_until"])
            except DomainError as exc:
                # Publication's transaction rolled back. If this attempt still
                # owns its lease, terminate it in a separate fenced transaction;
                # never let a permanent validation failure trigger another model call.
                try:
                    with lease.connection.begin():
                        job, run = self._valid(lease)
                        status = "cancelled" if run["status"] == "cancel_requested" else "failed"
                        self._terminal(lease.connection, job, status,
                                       {} if status == "cancelled" else
                                       {"code": exc.code, "retryable": False})
                        self._finish_valid(lease, job["lease_until"])
                except BaseException:
                    lease.lost = True
                    raise
            except BaseException:
                lease.lost = True
                raise

    def _cancel_claim(self, c, job):
        self._terminal(c, job, "cancelled", {})

    def _terminal(self, c, job, status, error):
        c.execute(
            update(jobs)
            .where(jobs.c.id == job["id"])
            .values(status="completed" if status == "succeeded" else status, lease_until=None)
        )
        c.execute(
            update(runs).where(runs.c.id == job["run_id"]).values(status=status, error_json=error)
        )
        append_event(
            c,
            job["run_id"],
            "run." + status,
            {
                "attempt": job["attempt"],
                "error_code": error.get("code"),
                "test_only": job["kind"] == "no_op",
            },
        )


