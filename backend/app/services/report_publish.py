"""One fenced transaction publishes or preserves a stale report draft."""

from sqlalchemy import select, update

from app.domain.policies import DomainError
from app.infrastructure.event_store import append_event
from app.infrastructure.orm import jobs, reports, runs
from app.services.evidence_scope import owner_lock
from app.services.report_policy import final_gate, snapshot
from app.services.report_read_service import current_validity
from app.validators.report import validate_draft


def publish_report(c, store, lease, result, settings):
    run_id = lease.job["run_id"]
    preliminary = c.execute(select(reports).where(reports.c.run_id == run_id)).mappings().one()
    owner_lock(c, preliminary["owner_id"])
    snap = snapshot(c, preliminary["owner_id"], preliminary["case_id"], settings, lock=True)
    job = c.execute(select(jobs).where(jobs.c.id == lease.job["id"])
                    .with_for_update()).mappings().one()
    run = c.execute(select(runs).where(runs.c.id == run_id).with_for_update()).mappings().one()
    report = c.execute(select(reports).where(reports.c.id == preliminary["id"])
                       .with_for_update()).mappings().one()
    if (run["kind"] != "report" or run["case_id"] != report["case_id"] or
            report["owner_id"] != snap["case"]["owner_id"] or
            run["status"] != "running" or lease.lost):
        raise DomainError("REPORT_RUN_STALE", "Report run is no longer authorized")
    deadline = job["lease_until"]
    store._finish_valid(lease, deadline)
    reasons = current_validity(c, report["owner_id"], report, settings, snap)["reasons"]
    if report["kind"] == "final" and not final_gate(c, report["owner_id"], snap, settings)["allowed"]:
        reasons.append("final_gate_changed")
    if isinstance(result, dict) and result.get("_stale"):
        reasons.append("snapshot_changed")
    if reasons:
        c.execute(update(reports).where(reports.c.id == report["id"])
                  .values(status="stale", stale_reason=reasons[0]))
        append_event(c, run_id, "report.stale", {"report_id": str(report["id"]),
                                                  "reason": reasons[0]})
    else:
        content = validate_draft(c, report["owner_id"], snap, result, settings,
                                 final=report["kind"] == "final")
        c.execute(update(reports).where(reports.c.case_id == report["case_id"],
            reports.c.kind == report["kind"], reports.c.status == "current",
            reports.c.id != report["id"]).values(status="stale", stale_reason="superseded"))
        c.execute(update(reports).where(reports.c.id == report["id"])
                  .values(status="current", content_json=content, stale_reason=None))
        append_event(c, run_id, "report.published", {"report_id": str(report["id"]),
                                                      "kind": report["kind"]})
    store._terminal(c, job, "succeeded", {})
    c.execute(update(runs).where(runs.c.id == run_id)
              .values(output_revision=report["input_revision"]))
    store._finish_valid(lease, deadline)


def fail_report(c, run_id, code):
    c.execute(update(reports).where(reports.c.run_id == run_id,
        reports.c.status == "draft").values(status="failed", stale_reason=code))
