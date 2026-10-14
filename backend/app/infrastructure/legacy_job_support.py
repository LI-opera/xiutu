"""Retired publications and recovery; reachable only on isolated test databases."""
import hashlib
import random
import re

from sqlalchemy import select, text, update

from app.domain.documents import IngestError
from app.domain.policies import DomainError
from app.infrastructure import index_state
from app.infrastructure.embedding_gateway import EmbeddingError
from app.infrastructure.event_store import append_event
from app.infrastructure.ingest_state import publish as publish_ingest
from app.infrastructure.ingest_state import state as ingest_state
from app.infrastructure.job_store import LeaseLost, lock_key
from app.infrastructure.orm import cases, diagnosis_candidates, graph_progress, jobs, runs


class LegacyJobSupport:
    def __init__(self, store):
        if not re.fullmatch(r"xiutu_test_[a-z0-9_]{1,40}", store.engine.url.database or ""):
            raise ValueError("Legacy job support requires an isolated test database")
        self.store = store

    def __getattr__(self, name):
        # Reuse the same connection pools, lease, settings and test hooks.
        return getattr(self.store, name)

    def cancel_claim(self, c, job):
        if job["kind"] == "case_analysis":
            from app.legacy_execution.case_analysis import fail_case_analysis

            fail_case_analysis(c, job["run_id"], "ANALYSIS_CANCELLED")
        self._terminal(c, job, "cancelled", {})

    def finish(self, lease, error=None, transient=False, result=None):
        with lease.mutex:
            try:
                with lease.connection.begin():
                    c = lease.connection
                    if lease.job["kind"] == "report" and error is None:
                        from app.config import load_settings
                        from app.services.report_publish import publish_report

                        publish_report(c, self, lease, result,
                                       self.settings or load_settings())
                        return
                    if lease.job["kind"] == "diagnosis" and error is None:
                        from app.config import load_settings
                        from app.services.publish_service import publish_area_close, publish_waiting

                        settings = self.settings or load_settings()
                        publisher = (publish_area_close if isinstance(result, dict) and
                                     result.get("candidate", {}).get("type") == "conclude_area"
                                     else publish_waiting)
                        _, deadline = publisher(c, self, lease, result, settings)
                        lease.final_deadline = deadline
                        # Publication, waiting state, event and journal are one commit.
                        # The terminal update cleared the live deadline; use the
                        # pre-publication deadline retained in the lease below.
                        self._finish_valid(lease, deadline)
                        return
                    if lease.job["kind"] == "diagnosis":
                        self._lock_diagnosis_case(c, lease)
                    job, run = self._valid(lease)
                    if run["status"] == "cancel_requested":
                        self._terminal(c, job, "cancelled", {})
                    elif error is None:
                        if job["kind"] == "case_analysis":
                            from app.legacy_execution.case_analysis import publish_case_analysis

                            publish_case_analysis(c, job["run_id"], result)
                        if job["kind"] == "ingest":
                            publish_ingest(
                                c, job, result, validate_lease=lambda: self._valid(lease)
                            )
                        if job["kind"] == "index":
                            try:
                                index_state.publish(c, job, lambda: self._valid(lease))
                            except (IngestError, EmbeddingError) as exc:
                                self._terminal(
                                    c, job, "failed", {"code": exc.code, "retryable": False}
                                )
                            else:
                                self._terminal(c, job, "succeeded", {})
                        else:
                            self._terminal(c, job, "succeeded", {})
                    elif transient and job["kind"] != "case_analysis" and job["attempt"] < min(3, job["max_attempts"]):
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
                        if job["kind"] == "ingest":
                            ingest_state(c, job["run_id"], "pending")
                        append_event(
                            c,
                            job["run_id"],
                            "run.retry_scheduled",
                            {"attempt": job["attempt"], "delay_seconds": delay},
                        )
                    else:
                        self._terminal(c, job, "failed", {"code": error, "retryable": transient})
                    if job["kind"] == "report" and error is not None:
                        from app.services.report_publish import fail_report

                        fail_report(c, job["run_id"], error)
                    if job["kind"] == "case_analysis" and error is not None:
                        from app.legacy_execution.case_analysis import fail_case_analysis

                        fail_case_analysis(c, job["run_id"], error)
                    # Final authorization point: no further application SQL before
                    # COMMIT. Failure rolls back chunks, version, status AND events.
                    self._finish_valid(lease, job["lease_until"])
            except DomainError as exc:
                # Publication's transaction rolled back. If this attempt still
                # owns its lease, terminate it in a separate fenced transaction;
                # never let a permanent validation failure trigger another model call.
                if lease.job["kind"] == "diagnosis" and self.published(lease.job["run_id"]):
                    # A conflicting replay must not rewrite the already committed
                    # publication or turn it into a failed run.
                    raise
                try:
                    with lease.connection.begin():
                        if lease.job["kind"] == "diagnosis":
                            self._lock_diagnosis_case(lease.connection, lease)
                        job, run = self._valid(lease)
                        status = "cancelled" if run["status"] == "cancel_requested" else "failed"
                        self._terminal(lease.connection, job, status,
                                       {} if status == "cancelled" else
                                       {"code": exc.code, "retryable": False})
                        if job["kind"] == "report":
                            from app.services.report_publish import fail_report

                            fail_report(lease.connection, job["run_id"], exc.code)
                        if job["kind"] == "case_analysis":
                            from app.legacy_execution.case_analysis import fail_case_analysis

                            fail_case_analysis(lease.connection, job["run_id"], exc.code)
                        self._finish_valid(lease, job["lease_until"])
                except BaseException:
                    lease.lost = True
                    raise
            except BaseException:
                lease.lost = True
                raise


    def staged_diagnosis(self, lease):
        # A committed draft belongs to the same logical run; a replacement
        # worker may reuse it without paying for the same model answer again.
        with self.engine.connect() as c:
            return c.execute(select(diagnosis_candidates.c.result_json).where(
                diagnosis_candidates.c.run_id == lease.job["run_id"])).scalar_one_or_none()


    def reconcile_wait(self, run_id):
        from app.infrastructure.orm import diagnosis_publications, diagnosis_steps
        from app.services.evidence_scope import owner_lock

        with self.engine.connect() as observer:
            row = observer.execute(select(runs.c.case_id, cases.c.owner_id)
                .join(cases, cases.c.id == runs.c.case_id)
                .where(runs.c.id == run_id)).one_or_none()
        if row is None:
            return False
        case_id, actor = row
        with self.locks.connect() as c:
            held = c.execute(text("SELECT pg_try_advisory_lock(:key)"),
                             {"key": lock_key(case_id)}).scalar_one()
            c.commit()
            if not held:
                return False
            inconsistent = False
            with c.begin():
                owner_lock(c, actor)
                case = c.execute(select(cases).where(cases.c.id == case_id)
                                 .with_for_update()).mappings().one()
                run = c.execute(select(runs).where(runs.c.id == run_id)
                                .with_for_update()).mappings().one()
                progress = c.execute(select(graph_progress).where(
                    graph_progress.c.run_id == run_id).with_for_update()).mappings().one()
                publication = c.execute(select(diagnosis_publications).where(
                    diagnosis_publications.c.run_id == run_id,
                    diagnosis_publications.c.node == "publish")).mappings().one_or_none()
                if publication is None or run["status"] != "waiting_input":
                    return False
                step = c.execute(select(diagnosis_steps).where(
                    diagnosis_steps.c.id == publication["step_id"])).mappings().one_or_none()
                # A correction supersedes the old graph epoch. Its committed
                # publication remains historical, but must not be checkpointed
                # into the new graph or prevent unrelated workers from starting.
                if progress["graph_epoch"] != case["graph_epoch"]:
                    return False
                if (progress["phase"] == "failed" and
                    run["error_json"].get("code") == "CHECKPOINT_INCONSISTENT"):
                    inconsistent = True
                elif (case["owner_id"] != actor or run["case_id"] != case_id or
                      progress["case_id"] != case_id or publication["case_id"] != case_id or
                      step is None or step["case_id"] != case_id or
                      step["run_id"] != run_id or step["turn_id"] != run["turn_id"] or
                      publication["output_revision"] > case["revision"] or
                      progress["workflow_id"] != publication["workflow_id"] or
                      progress["turn_id"] != publication["turn_id"] or
                      progress["workflow_id"] != run["workflow_id"] or
                      progress["turn_id"] != run["turn_id"] or
                      progress["phase"] not in {"evaluating", "waiting_input"} or
                      (progress["phase"] == "waiting_input" and
                       progress["step_id"] != step["id"])):
                    # Commit a bounded quarantine marker before raising. Keeping
                    # the publication and step intact prevents false success or
                    # duplicate publication; phase=failed removes this run from
                    # automatic recovery scans until an operator resolves it.
                    c.execute(update(graph_progress).where(
                        graph_progress.c.id == progress["id"]).values(phase="failed"))
                    c.execute(update(runs).where(runs.c.id == run_id).values(
                        error_json={"code": "CHECKPOINT_INCONSISTENT",
                                    "retryable": False, "recovery": "manual_review"}))
                    append_event(c, run_id, "checkpoint.quarantined",
                                 {"code": "CHECKPOINT_INCONSISTENT"})
                    inconsistent = True
                elif progress["phase"] == "waiting_input":
                    return True
                else:
                    c.execute(update(graph_progress).where(graph_progress.c.id == progress["id"])
                              .values(phase="waiting_input", step_id=step["id"]))
                    return True
            if inconsistent:
                raise DomainError("CHECKPOINT_INCONSISTENT", "Published turn mismatch")


    def reconcile_pending(self):
        from app.infrastructure.orm import diagnosis_publications

        with self.engine.connect() as c:
            pending = c.execute(select(graph_progress.c.run_id)
                .join(diagnosis_publications,
                      diagnosis_publications.c.run_id == graph_progress.c.run_id)
                .join(runs, runs.c.id == graph_progress.c.run_id)
                .where(graph_progress.c.phase == "evaluating",
                       runs.c.status == "waiting_input")
                .limit(10)).scalars().all()
        for run_id in pending:
            try:
                self.reconcile_wait(run_id)
            except DomainError as exc:
                if exc.code != "CHECKPOINT_INCONSISTENT":
                    raise
                # Only a durable quarantine may be isolated. Never suppress a
                # same-epoch mismatch whose marker failed to commit.
                with self.engine.connect() as c:
                    state = c.execute(select(graph_progress.c.phase, runs.c.error_json)
                        .join(runs, runs.c.id == graph_progress.c.run_id)
                        .where(graph_progress.c.run_id == run_id)).one_or_none()
                if (state is None or state.phase != "failed" or
                    state.error_json.get("code") != "CHECKPOINT_INCONSISTENT"):
                    raise


    def published(self, run_id):
        from app.infrastructure.orm import diagnosis_publications

        with self.engine.connect() as c:
            return c.execute(select(diagnosis_publications.c.id).where(
                diagnosis_publications.c.run_id == run_id,
                diagnosis_publications.c.node.in_(["publish", "area_close"]))).first() is not None


    @staticmethod
    def _lock_diagnosis_case(c, lease):
        case_id = c.execute(select(runs.c.case_id).where(
            runs.c.id == lease.job["run_id"])).scalar_one()
        if case_id is None:
            raise LeaseLost()
        c.execute(select(cases.c.id).where(cases.c.id == case_id).with_for_update()).one()


    def stage_diagnosis(self, lease, result):
        import json
        from uuid import uuid4

        encoded = json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode()) > 100000:
            raise DomainError("PROPOSAL_TOO_LARGE", "Candidate exceeds storage limit")
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with lease.mutex:
            try:
                with lease.connection.begin():
                    job, run = self._valid(lease)
                    if job["kind"] != "diagnosis" or run["status"] != "running":
                        raise LeaseLost()
                    old = lease.connection.execute(select(diagnosis_candidates).where(
                        diagnosis_candidates.c.run_id == run["id"])).mappings().one_or_none()
                    if old is not None:
                        if old["result_hash"] != digest:
                            raise DomainError("PROPOSAL_CONFLICT", "Run draft already differs")
                    else:
                        draft_id = uuid4()
                        lease.connection.execute(diagnosis_candidates.insert().values(
                            id=draft_id, run_id=run["id"], turn_id=run["turn_id"],
                            result_hash=digest, result_json=result))
                        lease.connection.execute(update(graph_progress).where(
                            graph_progress.c.run_id == run["id"]).values(
                            phase="evaluating", checkpoint_ref=str(draft_id)))
                    self._finish_valid(lease, job["lease_until"])
            except BaseException as exc:
                if isinstance(exc, LeaseLost) or lease.connection.closed or lease.connection.invalidated:
                    lease.lost = True
                raise


    def reserve_diagnosis_repair(self, lease):
        """Persist the single business repair BEFORE asking the model again."""
        with lease.mutex:
            with lease.connection.begin():
                job, run = self._valid(lease)
                if job["kind"] != "diagnosis" or run["status"] != "running":
                    raise LeaseLost()
                budget = dict(run["budget_json"])
                if budget.get("proposal_repair_used"):
                    raise DomainError("REPAIR_EXHAUSTED", "Proposal repair already used")
                budget["proposal_repair_used"] = True
                lease.connection.execute(update(runs).where(runs.c.id == run["id"])
                                         .values(budget_json=budget))
                self._finish_valid(lease, job["lease_until"])


    @staticmethod
    def _terminal(c, job, status, error):
        if job["kind"] == "diagnosis":
            from app.infrastructure.orm import diagnosis_steps

            prior_step_id = c.execute(select(graph_progress.c.step_id).where(
                graph_progress.c.run_id == job["run_id"])).scalar_one_or_none()
            has_waiting_step = prior_step_id is not None and c.execute(
                select(diagnosis_steps.c.id).where(
                    diagnosis_steps.c.id == prior_step_id,
                    diagnosis_steps.c.status == "waiting_input")
            ).first() is not None
            needs_input = error.get("code") in {
                "DIAGNOSIS_PROPOSAL_NEEDS_INPUT", "CORPUS_EMPTY",
                "DIAGNOSIS_EVIDENCE_UNAVAILABLE", "PROPOSAL_NOT_ACCEPTED",
                "AREA_NOT_READY", "AREA_NEEDS_INPUT", "AREA_SOURCE_INVALID",
                "AREA_CONFLICTING", "AREA_RETIRED_UNVERIFIED", "NEXT_AREA_MISMATCH",
            }
            c.execute(update(graph_progress).where(graph_progress.c.run_id == job["run_id"])
                      .values(phase="needs_input" if needs_input else "failed"))
            case_id = c.execute(select(runs.c.case_id).where(runs.c.id == job["run_id"])).scalar_one()
            if case_id is not None:
                has_published_step = c.execute(select(diagnosis_steps.c.id).where(
                    diagnosis_steps.c.case_id == case_id).limit(1)).first() is not None
                c.execute(update(cases).where(cases.c.id == case_id).values(
                    status=("waiting_input" if has_waiting_step else
                            "needs_review" if needs_input or
                            (status == "cancelled" and has_published_step) else
                            "draft" if status == "cancelled"
                            else "failed")))
        if job["kind"] == "index" and status != "succeeded":
            index_state.state(c, job["run_id"], error or {"code": status, "retryable": False})
        if job["kind"] == "ingest" and status != "succeeded":
            ingest_state(c, job["run_id"], status, error)
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


