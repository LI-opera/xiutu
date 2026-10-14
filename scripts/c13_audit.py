"""Read-only independent probes of the restricted C13 response; no model call."""

import json
from uuid import UUID

import httpx
from sqlalchemy import select

from scripts.legacy_analysis_ids import C13_CASE_ID as CASE_ID
from scripts.legacy_analysis_ids import C13_ANALYSIS_ID as ANALYSIS_ID
from scripts.wp15_workbench import STATE, TEST_TOKEN, environment
from app.domain.case_analysis import CaseAdviceProposalV4
from app.domain.policies import DomainError
from app.infrastructure.orm import case_analyses
from app.infrastructure.uow import make_engine
from app.services import case_analysis_c09 as c09


def main():
    with httpx.Client(base_url="http://127.0.0.1:8215", trust_env=False, timeout=20) as client:
        auth = client.post("/api/v2/auth/login", json={"token": TEST_TOKEN},
                           headers={"Origin": "http://localhost:5215"})
        auth.raise_for_status()
        actor = UUID(auth.json()["actor_id"])
        response = client.get(f"/api/v2/cases/{CASE_ID}/analyses/{ANALYSIS_ID}/diagnostic")
        response.raise_for_status()
        diagnostic = response.json()["diagnostic"]
    assert not diagnostic["truncated"]
    raw = diagnostic["raw_response"]
    proposal = CaseAdviceProposalV4.model_validate_json(raw).model_dump(mode="json")
    state = json.loads(STATE.read_text(encoding="utf-8"))
    engine = make_engine(environment(state)["DATABASE_URL"])
    try:
        with engine.connect() as conn:
            row = conn.execute(select(case_analyses).where(
                case_analyses.c.id == UUID(ANALYSIS_ID),
                case_analyses.c.case_id == UUID(CASE_ID),
                case_analyses.c.owner_id == actor)).mappings().one()
            assert row["status"] == "failed" and row["mode"] == "real"
            snapshot = row["snapshot_json"]
    finally:
        engine.dispose()
    findings = []

    def probe(path, fn, value=""):
        try:
            fn()
        except DomainError as exc:
            details = exc.details or {}
            findings.append({"field_path": details.get("field_path", path),
                             "rule_id": details.get("rule_id", exc.code),
                             "code": exc.code,
                             "bounded_excerpt": str(value).replace("\n", " ")[:120]})

    for field in ("summary", "retest_plan", "uncertainty", "safety_notice"):
        role = "safety" if field == "safety_notice" else "uncertainty" if field == "uncertainty" else "explanation"
        sources = proposal["safety_source_ids"] if field == "safety_notice" else ()
        probe(field, lambda f=field, r=role, s=sources:
              c09.check_text(snapshot, f, proposal[f], role=r, safety_sources=s), proposal[field])
    for index, item in enumerate(proposal["supported_directions"]):
        path = f"supported_directions[{index}]"
        probe(path, lambda p=path, v=item: c09._direction(snapshot, v, p), item.get("limit", ""))
    for index, item in enumerate(proposal["steps"]):
        path = f"steps[{index}]"
        probe(path, lambda p=path, v=item: c09._step(snapshot, v, p),
              item.get("request", "") or item.get("action", ""))
    print(json.dumps({"analysis_id": ANALYSIS_ID, "raw_sha256": diagnostic["sha256"],
                      "complete": not diagnostic["truncated"],
                      "direction_count": len(proposal["supported_directions"]),
                      "step_count": len(proposal["steps"]),
                      "independent_findings": findings,
                      "limit": "Independent probes are not a full natural-language safety audit."}, indent=2))


if __name__ == "__main__":
    main()
