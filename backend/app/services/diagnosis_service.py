"""Retained legacy diagnosis admission, separate from historical reads."""

from uuid import UUID

from sqlalchemy import select

from app.domain.policies import DomainError, check_revision
from app.domain.schemas import ResumeDiagnosis, StartDiagnosis
from app.infrastructure.orm import cases, diagnosis_steps, graph_progress, observations, runs
from app.infrastructure.uow import UnitOfWork
from app.services.diagnosis_read_service import DiagnosisReadService
from app.services.run_service import enqueue, idempotent, lock_case


class DiagnosisService(DiagnosisReadService):
    def start(self, actor: UUID, case_id: UUID, body: StartDiagnosis, key: str):
        if self.settings is not None:
            from app.services.protocol_service import ProtocolService
            ProtocolService(self.engine, self.settings).bind_for_case(actor, case_id)
        with UnitOfWork(self.engine) as u:
            c = u.connection

            def action():
                row = lock_case(c, actor, case_id)
                check_revision(row["revision"], body.expected_revision)
                if row["status"] != "draft":
                    raise DomainError("DIAGNOSIS_ALREADY_STARTED", "Case already has a diagnosis")
                if not row["corpus_manifest"]:
                    raise DomainError("CORPUS_EMPTY", "Case has no authorized indexed material")
                status, response = enqueue(
                    c, actor, "diagnosis", {"case_id": str(case_id)},
                    case_id, body.expected_revision,
                )
                run_id = UUID(response["run_id"])
                run = c.execute(select(runs).where(runs.c.id == run_id)).mappings().one()
                c.execute(graph_progress.insert().values(
                    workflow_id=run["workflow_id"], turn_id=run["turn_id"],
                    case_id=case_id, run_id=run_id, graph_epoch=row["graph_epoch"],
                    phase="queued",
                ))
                c.execute(cases.update().where(cases.c.id == case_id).values(status="analyzing"))
                return status, response

            # A committed replay returns the original response even after case revision moves.
            return idempotent(
                c, actor, "POST /api/v2/cases/" + str(case_id) + "/diagnosis/runs",
                key, {"expected_revision": body.expected_revision}, action,
            )

    def resume(self, actor: UUID, case_id: UUID, body: ResumeDiagnosis, key: str):
        from app.repositories.observations import ObservationRepository

        with UnitOfWork(self.engine) as u:
            c = u.connection

            def action():
                row = lock_case(c, actor, case_id)
                check_revision(row["revision"], body.expected_revision)
                if row["status"] != "waiting_input":
                    raise DomainError("NOT_WAITING", "Case is not waiting for saved input")
                step = c.execute(select(diagnosis_steps).where(
                    diagnosis_steps.c.case_id == case_id,
                    diagnosis_steps.c.status == "waiting_input").with_for_update()
                ).mappings().one_or_none()
                if step is None:
                    raise DomainError("NO_CURRENT_STEP", "Current step is unavailable")
                saved = c.execute(select(observations).where(
                    observations.c.id == body.observation_id,
                    observations.c.case_id == case_id,
                    observations.c.step_id == step["id"])).mappings().one_or_none()
                parent = c.execute(select(runs).where(runs.c.id == step["run_id"])).mappings().one()
                if (saved is None or parent["output_revision"] is None
                        or saved["created_revision"] < parent["output_revision"]
                        or saved["created_revision"] > row["revision"]):
                    raise DomainError("OBSERVATION_INVALID", "Saved observation does not match current check")
                effective = {x["id"] for x in ObservationRepository(c).read(
                    case_id, None, row["revision"])}
                if saved["id"] not in effective:
                    raise DomainError("OBSERVATION_INVALID", "Saved observation was superseded")
                if parent["status"] != "waiting_input":
                    raise DomainError("RUN_NOT_WAITING", "Previous run is not waiting")
                status, response = enqueue(c, actor, "diagnosis",
                    {"case_id": str(case_id), "observation_id": str(body.observation_id)},
                    case_id, row["revision"], parent=parent, new_turn=True)
                run = c.execute(select(runs).where(runs.c.id == UUID(response["run_id"]))).mappings().one()
                c.execute(graph_progress.insert().values(
                    workflow_id=run["workflow_id"], turn_id=run["turn_id"],
                    case_id=case_id, run_id=run["id"], graph_epoch=row["graph_epoch"],
                    phase="resuming", step_id=step["id"],
                ))
                c.execute(cases.update().where(cases.c.id == case_id).values(status="analyzing"))
                return status, response

            return idempotent(c, actor,
                "POST /api/v2/cases/" + str(case_id) + "/diagnosis/resume", key,
                body.model_dump(mode="json"), action)

