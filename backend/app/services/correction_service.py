"""Append-only observation correction starts a new fenced graph epoch."""

from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import select, update

from app.domain.policies import DomainError, check_revision
from app.domain.schemas import PersistedText
from app.infrastructure.event_store import append_event
from app.infrastructure.orm import (
    cases,
    diagnosis_area_conclusions,
    diagnosis_areas,
    diagnosis_steps,
    graph_progress,
    observations,
    runs,
)
from app.infrastructure.uow import UnitOfWork
from app.services.evidence_scope import owner_lock
from app.services.observation_service import ObservationService, SubmitObservation
from app.services.run_service import enqueue, idempotent, idle_case, lock_case


class CorrectObservation(SubmitObservation):
    correction_reason: PersistedText = Field(min_length=1, max_length=1000)


class CorrectionService(ObservationService):
    def correct(self, actor: UUID, case_id: UUID, original_id: UUID,
                body: CorrectObservation, key: str):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            owner_lock(c, actor)

            def action():
                case = lock_case(c, actor, case_id)
                check_revision(case["revision"], body.expected_revision)
                if case["graph_epoch"] != body.graph_epoch:
                    raise DomainError("GRAPH_EPOCH_STALE", "Diagnosis graph changed")
                try:
                    idle_case(c, case_id)
                except DomainError as exc:
                    if exc.code == "ACTIVE_RUN":
                        raise DomainError("RUN_ACTIVE", "Cancel and await the active run before correction") from None
                    raise
                old = c.execute(select(observations).where(
                    observations.c.id == original_id,
                    observations.c.case_id == case_id).with_for_update()).mappings().one_or_none()
                if old is None:
                    raise DomainError("NOT_FOUND", "Observation not found", 404)
                if old["step_id"] != body.step_id or old["actor_id"] != actor:
                    raise DomainError("OBSERVATION_INVALID", "Original check does not match")
                if c.execute(select(observations.c.id).where(
                    observations.c.supersedes_id == original_id)).first():
                    raise DomainError("OBSERVATION_STALE", "Observation was already corrected")
                step = c.execute(select(diagnosis_steps).where(
                    diagnosis_steps.c.id == old["step_id"],
                    diagnosis_steps.c.case_id == case_id).with_for_update()).mappings().one_or_none()
                if step is None or step["status"] not in {"completed", "needs_review"}:
                    raise DomainError("STEP_NOT_ANSWERED", "Only a saved check can be corrected")
                payload = self._payload(c, actor, case_id, case, step, body, key)
                next_revision, next_epoch = case["revision"] + 1, case["graph_epoch"] + 1
                from app.services.protocol_service import ProtocolService
                ProtocolService.clone_epoch(c, case_id, actor, case["graph_epoch"], next_epoch)
                c.execute(update(cases).where(cases.c.id == case_id).values(
                    revision=next_revision, graph_epoch=next_epoch, status="analyzing"))
                replacement = uuid4()
                c.execute(observations.insert().values(
                    id=replacement, case_id=case_id, area_id=old["area_id"],
                    step_id=old["step_id"], kind=body.kind, payload=payload,
                    created_revision=next_revision, supersedes_id=original_id,
                    correction_reason=body.correction_reason, actor_id=actor,
                ))
                # Conservative invalidation: no old step or conclusion may be
                # presented as a current answer after a fact changes.
                c.execute(update(diagnosis_steps).where(diagnosis_steps.c.case_id == case_id)
                          .values(status="needs_review"))
                c.execute(update(diagnosis_areas).where(diagnosis_areas.c.case_id == case_id,
                    diagnosis_areas.c.graph_epoch == case["graph_epoch"])
                    .values(status="stale"))
                c.execute(update(diagnosis_area_conclusions).where(
                    diagnosis_area_conclusions.c.case_id == case_id,
                    diagnosis_area_conclusions.c.graph_epoch == case["graph_epoch"])
                    .values(needs_review=True, review_reason="observation_corrected"))
                _, response = enqueue(c, actor, "diagnosis",
                    {"case_id": str(case_id), "context_revised": str(replacement)},
                    case_id, next_revision)
                new_run = c.execute(select(runs).where(
                    runs.c.id == UUID(response["run_id"]))).mappings().one()
                c.execute(graph_progress.insert().values(
                    workflow_id=new_run["workflow_id"], turn_id=new_run["turn_id"],
                    case_id=case_id, run_id=new_run["id"], graph_epoch=next_epoch,
                    phase="queued",
                ))
                append_event(c, new_run["id"], "observation.corrected",
                             {"observation_id": str(replacement),
                              "supersedes_id": str(original_id),
                              "case_revision": next_revision, "graph_epoch": next_epoch})
                return 202, {**response, "observation_id": str(replacement),
                             "supersedes_id": str(original_id),
                             "case_revision": next_revision, "graph_epoch": next_epoch}

            return idempotent(c, actor,
                f"observation_correct:{original_id}",
                key, {"case_id": str(case_id), **body.model_dump(mode="json")}, action)
