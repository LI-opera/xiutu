"""Owned persisted diagnosis status and current-step projection."""

from uuid import UUID

from sqlalchemy import select

from app.domain.policies import DomainError
from app.infrastructure.orm import cases, diagnosis_steps, graph_progress, runs
from app.infrastructure.uow import UnitOfWork


class DiagnosisReadService:
    def __init__(self, engine, settings=None):
        self.engine = engine
        self.settings = settings

    def current(self, actor: UUID, case_id: UUID):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            case = c.execute(select(cases).where(cases.c.id == case_id,
                                                  cases.c.owner_id == actor)).mappings().one_or_none()
            if case is None:
                raise DomainError("NOT_FOUND", "Case not found", 404)
            step = c.execute(
                select(diagnosis_steps).where(diagnosis_steps.c.case_id == case_id,
                                              diagnosis_steps.c.status == "waiting_input")
            ).mappings().one_or_none()
            required_conditions = None
            if step is not None and step["candidate_json"].get("type") == "propose_step":
                from app.agents.state import ProposeStep
                from app.validators.support import operating_conditions

                proposal = ProposeStep.model_validate(step["candidate_json"])
                required_conditions = operating_conditions(proposal.prerequisites)
            recent = c.execute(select(runs.c.id, runs.c.status, runs.c.error_json,
                graph_progress.c.phase, graph_progress.c.created_at).join(
                    graph_progress, graph_progress.c.run_id == runs.c.id).where(
                    runs.c.case_id == case_id, runs.c.kind == "diagnosis",
                    graph_progress.c.graph_epoch == case["graph_epoch"]
                ).order_by(graph_progress.c.created_at.desc()).limit(5)).mappings().all()
            return {"case_id": str(case_id), "revision": case["revision"],
                    "graph_epoch": case["graph_epoch"], "status": case["status"],
                    "recent_runs": [{"id": str(x["id"]), "status": x["status"],
                        "phase": x["phase"], "error_code": (x["error_json"] or {}).get("code")}
                        for x in recent],
                    "current_step": None if step is None else {
                        "id": str(step["id"]), "area_id": str(step["area_id"]),
                        "run_id": str(step["run_id"]), "candidate": step["candidate_json"],
                        "validation": step["validation_json"], "status": step["status"],
                        "required_conditions": required_conditions,
                    }}
