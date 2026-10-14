"""Owner-checked, read-only C18 diagnostic summary; never republishes advice."""

import hashlib
import json
from uuid import UUID

import httpx
from sqlalchemy import select

from scripts.legacy_analysis_ids import C18_CASE_ID as CASE_ID, ORIGIN
from scripts.legacy_analysis_ids import C18_ANALYSIS_ID as ANALYSIS_ID
from scripts.wp15_workbench import STATE, TEST_TOKEN, environment
from app.domain.case_analysis import CaseAdviceProposalV7
from app.domain.policies import DomainError
from app.infrastructure.orm import case_analyses
from app.infrastructure.uow import make_engine
from app.services import case_analysis_c14
from app.legacy_execution.case_analysis import assemble_proposal


def main():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    with httpx.Client(base_url="http://127.0.0.1:8215", trust_env=False, timeout=20) as client:
        login = client.post("/api/v2/auth/login", json={"token": TEST_TOKEN},
                            headers={"Origin": ORIGIN})
        login.raise_for_status()
        actor = UUID(login.json()["actor_id"])
        response = client.get(f"/api/v2/cases/{CASE_ID}/analyses/{ANALYSIS_ID}/diagnostic")
        response.raise_for_status()
        entry = response.json()
    assert entry["availability"] == "retained"
    diagnostic = entry["diagnostic"]
    assert not diagnostic["truncated"] and not diagnostic["credentials_redacted"]
    raw = diagnostic["raw_response"]
    assert hashlib.sha256(raw.encode("utf-8")).hexdigest() == diagnostic["sha256"]
    engine = make_engine(environment(state)["DATABASE_URL"])
    try:
        with engine.connect() as conn:
            row = conn.execute(select(case_analyses).where(
                case_analyses.c.id == UUID(ANALYSIS_ID),
                case_analyses.c.case_id == UUID(CASE_ID),
                case_analyses.c.owner_id == actor)).mappings().one()
            assert row["status"] == "failed" and row["mode"] == "real" and not row["content_json"]
            snapshot = row["snapshot_json"]
    finally:
        engine.dispose()
    proposal = json.loads(raw)
    normalized = CaseAdviceProposalV7.model_validate(proposal).model_dump(mode="json")
    first = {}
    try:
        assemble_proposal(snapshot, proposal)
    except DomainError as exc:
        detail = exc.details or {}
        first = {"code": exc.code, "rule_id": detail.get("rule_id"),
                 "field_path": detail.get("field_path"), "actual": (detail.get("actual") or "")[:160]}
    issues = []

    def probe(path, callback):
        try:
            callback()
        except DomainError as exc:
            detail = exc.details or {}
            issues.append({"path": detail.get("field_path", path),
                           "rule_id": detail.get("rule_id", exc.code),
                           "actual": (detail.get("actual") or "")[:120]})
        except Exception as exc:
            issues.append({"path": path, "not_checked": type(exc).__name__})

    for key in ("summary", "uncertainty", "safety_notice", "retest_plan"):
        value = normalized.get(key)
        if value:
            role = "safety" if key == "safety_notice" else "retest" if key == "retest_plan" else "analysis"
            probe(key, lambda k=key, v=value, r=role: case_analysis_c14._text(snapshot, k, v, role=r,
                  source_ids=normalized.get("safety_source_ids", []) if k == "safety_notice" else ()))
    for index, value in enumerate(normalized.get("unconfirmed_directions", [])):
        probe(f"unconfirmed_directions[{index}]", lambda i=index, v=value:
              case_analysis_c14._text(snapshot, f"unconfirmed_directions[{i}]", v, role="analysis"))
    for index, item in enumerate(normalized.get("supported_directions", [])):
        probe(f"supported_directions[{index}]", lambda i=index, v=item:
              case_analysis_c14._direction(snapshot, v, f"supported_directions[{i}]"))
    for index, item in enumerate(normalized.get("steps", [])):
        probe(f"steps[{index}]", lambda i=index, v=item:
              case_analysis_c14._step(snapshot, v, f"steps[{i}]"))
    print(json.dumps({
        "analysis_id": ANALYSIS_ID, "sha256": diagnostic["sha256"],
        "response_complete": True, "contract": snapshot["output_contract_version"],
        "first_failure": first, "independent_issues": issues,
        "proposal_shape": {"direction_count": len(proposal.get("supported_directions", [])),
                           "step_types": [item.get("type") for item in proposal.get("steps", [])],
                           "action_ids": [item.get("action_id") for item in proposal.get("steps", [])]},
        "summary_excerpt": (proposal.get("summary") or "")[:220],
        "direction_titles": [item.get("title", "")[:90] for item in proposal.get("supported_directions", [])],
        "unconfirmed_direction_excerpts": [value[:160] for value in proposal.get("unconfirmed_directions", [])],
    }, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
