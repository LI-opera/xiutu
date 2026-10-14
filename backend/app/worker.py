"""Persistent worker; the CLI only claims document and test jobs."""

import argparse
import os
import re
import threading
import time
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain.documents import IngestError
from app.domain.policies import DomainError
from app.domain.tasks import NoOpInput
from app.infrastructure.embedding_gateway import EmbeddingError
from app.infrastructure.job_store import RUNTIME_JOB_KINDS, JobStore, LeaseLost
from app.infrastructure.model_gateway import ModelError
from app.services.index_builder import build_index
from app.services.ingest import parse_ingest

class TransientTaskError(Exception):
    pass


class PermanentTaskError(Exception):
    pass


def no_op(payload, stopped):
    data = NoOpInput.model_validate(payload)
    stopped.wait(data.seconds)


class Worker:
    def __init__(self, store, worker_id=None, heartbeat_seconds=15,
                 diagnostic_sink=None, legacy_execution=False):
        if legacy_execution and not re.fullmatch(
            r"xiutu_test_[a-z0-9_]{1,40}", store.engine.url.database or ""
        ):
            raise ValueError("Legacy worker execution requires an isolated test database")
        self.store = store
        self.worker_id = worker_id or str(uuid4())
        self.heartbeat_seconds = heartbeat_seconds
        self.legacy_execution = legacy_execution
        self.legacy_dispatcher = None
        if legacy_execution:
            from app.legacy_worker_handlers import LegacyDispatcher

            self.legacy_dispatcher = LegacyDispatcher(diagnostic_sink)

    def once(self, hook=None, handler=None, run_id=None):
        # hook/handler are in-process test seams, never accepted from job payload or CLI.
        if self.legacy_dispatcher is not None:
            self.legacy_dispatcher.prepare(self.store)
            lease = self.store.claim_legacy(self.worker_id, hook, run_id)
        else:
            lease = self.store.claim(self.worker_id, hook, run_id,
                                     allowed_kinds=RUNTIME_JOB_KINDS)
        if lease is None:
            return False
        stopped, finished = threading.Event(), threading.Event()
        published_run = None

        def heartbeat():
            while not finished.wait(self.heartbeat_seconds):
                try:
                    if self.store.heartbeat(lease):
                        stopped.set()
                except (SQLAlchemyError, LeaseLost):
                    stopped.set()
                    return

        pulse = threading.Thread(target=heartbeat, daemon=True)
        pulse.start()
        try:
            if hook:
                hook("after_claim", lease.job)
            error, transient, result = None, False, None
            diagnosis_executed = False
            try:
                if lease.job["kind"] == "no_op":
                    (handler or no_op)(lease.job["payload"], stopped)
                elif lease.job["kind"] == "index":
                    result = build_index(self.store, lease, stopped, hook)
                elif lease.job["kind"] == "ingest":
                    result = parse_ingest(self.store.engine, lease.job["payload"], stopped)
                elif self.legacy_dispatcher is not None:
                    from app.legacy_worker_handlers import LEGACY_JOB_KINDS

                    if lease.job["kind"] not in LEGACY_JOB_KINDS:
                        raise PermanentTaskError()
                    result, diagnosis_executed, published_run = self.legacy_dispatcher.execute(
                        self.store, lease, stopped, finished
                    )
                else:
                    raise PermanentTaskError()
            except (IngestError, EmbeddingError) as exc:
                error = exc.code
            except ModelError as exc:
                error = exc.code
                transient = (
                    self.legacy_dispatcher.model_failure_is_transient(lease.job["kind"], error)
                    if self.legacy_dispatcher is not None else False
                )
            except DomainError as exc:
                error = exc.code
            except TransientTaskError:
                error, transient = "TRANSIENT_HANDLER_ERROR", True
            except (PermanentTaskError, ValidationError):
                error = (
                    "HANDLER_NOT_IMPLEMENTED" if lease.job["kind"] != "no_op" else "INVALID_TASK"
                )
            except Exception:
                error = "HANDLER_FAILED"
            if self.legacy_dispatcher is not None:
                diagnosis_executed, published_run = self.legacy_dispatcher.recover_published(
                    self.store, lease, finished, diagnosis_executed, published_run
                )
            if hook:
                hook("before_finish", lease.job)
            if not diagnosis_executed:
                self.store.finish(lease, error, transient, result=result)
        except (SQLAlchemyError, LeaseLost):
            # Never log underlying DB exception/DSN. A fenced attempt cannot publish.
            stopped.set()
        finally:
            finished.set()
            pulse.join()
            lease.close()
        if published_run is not None:
            self.legacy_dispatcher.reconcile_published(self.store, published_run)
        return True


def runtime_worker(store):
    """The launched worker cannot claim retired diagnostic or analysis jobs."""
    return Worker(store)


def main():
    parser = argparse.ArgumentParser(description="Persistent xiutu task worker")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    store = JobStore(os.environ["DATABASE_URL"])
    try:
        worker = runtime_worker(store)
        while True:
            worked = worker.once()
            if args.once:
                break
            if not worked:
                time.sleep(0.5)
    finally:
        store.close()


if __name__ == "__main__":
    main()
