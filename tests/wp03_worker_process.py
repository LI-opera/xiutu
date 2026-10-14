"""Isolated test launcher: no fault controls in production payload/CLI."""

import json
import os
import sys
import time
from pathlib import Path
from uuid import UUID

from app.infrastructure.db_target import validate_target
from app.infrastructure.job_store import JobStore
from app.worker import PermanentTaskError, TransientTaskError, Worker, no_op

control = Path(sys.argv[1])
config = json.loads(control.read_text())
url = os.environ["TEST_DATABASE_URL"]
validate_target(url, "test")
store = JobStore(url, lease_seconds=config.get("lease", 3))

# Opt-in diagnostic trace for an isolated test child. Never serialize the
# exception message: DB exceptions may contain SQL parameters or credentials.
if os.environ.get("WP11_TRACE_WORKER") == "1":
    for method in ("finish", "heartbeat", "stage_index", "_valid", "_finish_valid"):
        original = getattr(store, method)

        def traced(*args, _method=method, _original=original, **kwargs):
            try:
                return _original(*args, **kwargs)
            except BaseException as exc:
                lease = args[0]
                detail = {"type": type(exc).__name__,
                          "lost": bool(getattr(lease, "lost", False)),
                          "closed": bool(getattr(lease.connection, "closed", True)),
                          "invalidated": bool(getattr(lease.connection, "invalidated", True)),
                          "claim_deadline": str(lease.job.get("lease_until"))}
                try:
                    from app.infrastructure.orm import jobs, runs
                    from sqlalchemy import select, text

                    with store.engine.connect() as observer:
                        row = observer.execute(select(
                            jobs.c.status, jobs.c.lease_owner, jobs.c.lease_token,
                            jobs.c.lease_until, runs.c.status.label("run_status"),
                            text("clock_timestamp()"))
                            .join(runs, runs.c.id == jobs.c.run_id)
                            .where(jobs.c.id == lease.job["id"])).one_or_none()
                        if row is not None:
                            detail.update(job_status=row[0], owner_matches=row[1] == lease.worker,
                                          token_matches=row[2] == lease.job["lease_token"],
                                          lease_until=str(row[3]), run_status=row[4],
                                          db_clock=str(row[5]))
                except BaseException:
                    detail["observer_unavailable"] = True
                (control.parent / (control.stem + "." + _method + "_failure")).write_text(
                    json.dumps(detail)
                )
                raise

        setattr(store, method, traced)


def signal(name, job=None):
    (control.parent / (control.stem + "." + name)).write_text(
        json.dumps({"pid": os.getpid(), "job": str(job["id"]) if job else None, "at": time.time()})
    )


def hook(stage, job):
    signal(stage, job)
    if config.get("barrier") == stage:
        while not (control.parent / (control.stem + ".release")).exists():
            time.sleep(0.02)


def handler(payload, stopped):
    signal("executing")
    if config.get("failure") == "transient":
        raise TransientTaskError()
    if config.get("failure") == "permanent":
        raise PermanentTaskError()
    no_op(payload, stopped)


signal("ready")
while config.get("gate") and not Path(config["gate"]).exists():
    time.sleep(0.02)
try:
    worker = Worker(store, heartbeat_seconds=config.get("heartbeat", 0.3))
    worked = worker.once(hook, handler, UUID(config["run_id"]))
    if os.environ.get("WP11_TRACE_WORKER") == "1":
        from app.infrastructure.orm import jobs, runs
        from sqlalchemy import select, text

        with store.engine.connect() as observer:
            state = observer.execute(select(
                jobs.c.status, jobs.c.lease_until, runs.c.status.label("run_status"),
                text("clock_timestamp()"))
                .join(runs, runs.c.id == jobs.c.run_id)
                .where(jobs.c.run_id == UUID(config["run_id"]))).one_or_none()
        (control.parent / (control.stem + ".final_state")).write_text(json.dumps(
            {"worked": worked, "job_status": state[0] if state else None,
             "lease_until": str(state[1]) if state else None,
             "run_status": state[2] if state else None,
             "db_clock": str(state[3]) if state else None}))
    signal("worked" if worked else "idle")
finally:
    store.close()
