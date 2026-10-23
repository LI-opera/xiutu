"""Persistent worker: claims queued background jobs (manual chunking and embedding)."""

import argparse
import os
import threading
import time
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain.policies import DomainError
from app.domain.tasks import NoOpInput
from app.infrastructure.embedding_gateway import EmbeddingError
from app.infrastructure.job_store import RUNTIME_JOB_KINDS, JobStore, LeaseLost
from app.services.reference_ingest import IngestError


class TransientTaskError(Exception):
    pass


class PermanentTaskError(Exception):
    pass


def no_op(payload, stopped):
    data = NoOpInput.model_validate(payload)
    stopped.wait(data.seconds)


class Worker:
    def __init__(self, store, worker_id=None, heartbeat_seconds=15):
        self.store = store
        self.worker_id = worker_id or str(uuid4())
        self.heartbeat_seconds = heartbeat_seconds

    def once(self, hook=None, handler=None, run_id=None):
        # hook/handler are in-process test seams, never accepted from job payload or CLI.
        lease = self.store.claim(self.worker_id, hook, run_id, allowed_kinds=RUNTIME_JOB_KINDS)
        if lease is None:
            return False
        stopped, finished = threading.Event(), threading.Event()

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
            try:
                if lease.job["kind"] == "no_op":
                    (handler or no_op)(lease.job["payload"], stopped)
                elif lease.job["kind"] == "reference_ingest":
                    from app.services.reference_ingest import run_job
                    result = run_job(self.store.engine, lease.job["payload"], stopped)
                else:
                    raise PermanentTaskError()
            except (IngestError, EmbeddingError) as exc:
                error = exc.code
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
            if hook:
                hook("before_finish", lease.job)
            self.store.finish(lease, error, transient, result=result)
        except (SQLAlchemyError, LeaseLost):
            # Never log underlying DB exception/DSN. A fenced attempt cannot publish.
            stopped.set()
        finally:
            finished.set()
            pulse.join()
            lease.close()
        return True


def main():
    parser = argparse.ArgumentParser(description="Persistent xiutu task worker")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    store = JobStore(os.environ["DATABASE_URL"])
    try:
        worker = Worker(store)
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
