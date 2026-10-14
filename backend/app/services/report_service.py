"""Retained legacy report admission, separate from historical reads."""

from uuid import UUID


from app.domain.policies import DomainError, check_revision
from app.domain.schemas import RequestReport
from app.infrastructure.orm import reports
from app.infrastructure.uow import UnitOfWork
from app.services.evidence_scope import owner_lock
from app.services.report_policy import final_gate, snapshot
from app.services.report_read_service import ReportReadService
from app.services.run_service import enqueue, idempotent


class ReportService(ReportReadService):
    def request(self, actor, case_id, body: RequestReport, key):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            owner_lock(c, actor)

            def action():
                snap = snapshot(c, actor, case_id, self.settings, lock=True)
                case = snap["case"]
                check_revision(case["revision"], body.expected_revision)
                if body.kind == "final":
                    gate = final_gate(c, actor, snap, self.settings)
                    if not gate["allowed"]:
                        raise DomainError("FINAL_NOT_READY", "Final report conditions are not met",
                                          details={"blocking_items": gate["blocking_items"],
                                                   "current_revision": case["revision"]})
                status, result = enqueue(c, actor, "report",
                    {"case_id": str(case_id), "report_kind": body.kind},
                    case_id, case["revision"])
                run_id = UUID(result["run_id"])
                report_id = c.execute(reports.insert().values(
                    case_id=case_id, owner_id=actor, run_id=run_id,
                    kind=body.kind, input_revision=case["revision"],
                    graph_epoch=case["graph_epoch"],
                    manifest_json=case["corpus_manifest"],
                    conclusion_ids=[str(card["id"]) for card in snap["cards"].values()]
                ).returning(reports.c.id)).scalar_one()
                return status, {**result, "report_id": str(report_id),
                                "kind": body.kind, "input_revision": case["revision"]}

            return idempotent(c, actor, f"POST /api/v2/cases/{case_id}/reports",
                              key, body.model_dump(mode="json"), action)

