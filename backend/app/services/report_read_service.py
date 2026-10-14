"""Owned historical report reads and current validity projection."""

from uuid import UUID

from sqlalchemy import select

from app.domain.policies import DomainError
from app.infrastructure.orm import reports
from app.infrastructure.uow import UnitOfWork
from app.services.evidence_scope import source
from app.services.report_policy import final_gate, snapshot


def current_validity(c, actor, row, settings, snap=None):
    snap = snap or snapshot(c, actor, row["case_id"], settings)
    case = snap["case"]
    reasons = []
    if (case["revision"] != row["input_revision"] or
            case["graph_epoch"] != row["graph_epoch"]):
        reasons.append("revision_or_epoch_changed")
    if case["corpus_manifest"] != row["manifest_json"]:
        reasons.append("manifest_changed")
    present = {str(x["id"]) for x in snap["cards"].values() if not x["needs_review"]}
    if any(x not in present for x in row["conclusion_ids"]):
        reasons.append("conclusion_changed")
    for entry in row["manifest_json"]:
        try:
            source(c, actor, case, UUID(entry["document_version_id"]),
                   UUID(entry["index_id"]), settings.retrieval_profile)
        except (DomainError, KeyError, ValueError):
            reasons.append("source_invalid")
            break
    if row["kind"] == "final" and not final_gate(c, actor, snap, settings)["allowed"]:
        reasons.append("final_gate_changed")
    return {"valid": row["status"] == "current" and not reasons,
            "reasons": list(dict.fromkeys(reasons))}


class ReportReadService:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings

    def gate(self, actor, case_id):
        with UnitOfWork(self.engine) as u:
            snap = snapshot(u.connection, actor, case_id, self.settings)
            return final_gate(u.connection, actor, snap, self.settings)

    def _body(self, c, actor, row, snap):
        validity = current_validity(c, actor, row, self.settings, snap)
        return {"id": str(row["id"]), "case_id": str(row["case_id"]),
                "run_id": str(row["run_id"]), "kind": row["kind"],
                "status": "stale" if row["status"] == "current" and not validity["valid"]
                          else row["status"],
                "input_revision": row["input_revision"], "graph_epoch": row["graph_epoch"],
                "content": row["content_json"], "current_validity": validity,
                "stale_reason": row["stale_reason"]}

    def get(self, actor, case_id, report_id):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            snap = snapshot(c, actor, case_id, self.settings)
            row = c.execute(select(reports).where(reports.c.id == report_id,
                reports.c.case_id == case_id, reports.c.owner_id == actor)
            ).mappings().one_or_none()
            if row is None:
                raise DomainError("NOT_FOUND", "Report not found", 404)
            return self._body(c, actor, row, snap)

    def list(self, actor, case_id):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            snap = snapshot(c, actor, case_id, self.settings)
            rows = c.execute(select(reports).where(reports.c.case_id == case_id,
                reports.c.owner_id == actor).order_by(reports.c.created_at.desc(),
                reports.c.id.desc()).limit(50)).mappings().all()
            return {"case_id": str(case_id), "items": [self._body(c, actor, row, snap)
                                                       for row in rows]}
