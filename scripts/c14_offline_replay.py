"""Owner-checked, read-only replay of C08/C10/C13 frozen real responses.

Never publishes a result or sends a model request. New-contract conversion is
limited to assigning the new version and V5 optional defaults; prose, facts,
sources and action proposals remain byte-for-byte from the retained response.
"""

import hashlib
import json
from copy import deepcopy
from uuid import UUID

import httpx
from sqlalchemy import select

from scripts.legacy_analysis_ids import C13_CASE_ID as C13_CASE
from scripts.legacy_analysis_ids import C13_ANALYSIS_ID as C13_ANALYSIS
from scripts.wp15_workbench import STATE, TEST_TOKEN, environment
from app.domain.case_analysis import CaseAdviceProposalV5
from app.domain.policies import DomainError
from app.infrastructure.orm import case_analyses
from app.infrastructure.uow import make_engine
from app.legacy_execution.case_analysis import assemble_proposal
from app.services import case_analysis_c14
from decimal import Decimal

CASES = (
    ("C08", "97812694-5339-4e59-badc-d87a9bc5c431",
     "9d38a39d-0c61-428a-beae-53316ce9ceb9"),
    ("C10", "d109a875-70e9-46aa-a198-7c75048aa8b3",
     "b6ab0831-8c3c-4499-89a2-3a41e52e0b71"),
    ("C13", C13_CASE, C13_ANALYSIS),
)


def outcome(snapshot, proposal):
    try:
        result = assemble_proposal(snapshot, proposal)
        return {"state": result.get("publication", {}).get("state", "complete"),
                "directions": len(result["supported_directions"]),
                "steps": len(result["steps"]),
                "rejected": result.get("publication", {}).get("rejected_sections", [])}
    except DomainError as exc:
        detail = exc.details or {}
        return {"state": "rejected", "code": exc.code,
                "rule_id": detail.get("rule_id"), "field_path": detail.get("field_path"),
                "diagnostic_excerpt": (detail.get("actual") or "")[:160]}
    except Exception as exc:
        return {"state": "uncheckable", "error_type": type(exc).__name__}


def independent_probes(snapshot, proposal):
    """Bounded read-only field probes; never substitutes for publication validation."""
    issues = []

    def check(path, callback):
        try:
            callback()
        except DomainError as exc:
            detail = exc.details or {}
            issues.append({"field_path": detail.get("field_path", path),
                           "rule_id": detail.get("rule_id", exc.code)})
        except Exception as exc:
            issues.append({"field_path": path, "uncheckable": type(exc).__name__})

    for key in ("summary", "uncertainty", "safety_notice", "retest_plan"):
        value = proposal.get(key)
        if not value:
            continue
        role = "safety" if key == "safety_notice" else "retest" if key == "retest_plan" else "analysis"
        for index, sentence in enumerate(case_analysis_c14._sentences(value)):
            check(f"{key}[sentence:{index}]", lambda s=sentence, k=key, r=role:
                  case_analysis_c14._text(snapshot, k, s, role=r,
                                          source_ids=proposal.get("safety_source_ids", []) if k == "safety_notice" else ()))
    for index, direction in enumerate(proposal.get("supported_directions", [])):
        check(f"supported_directions[{index}]", lambda d=direction, i=index:
              case_analysis_c14._direction(snapshot, d, f"supported_directions[{i}]"))
    for index, step in enumerate(proposal.get("steps", [])):
        check(f"steps[{index}]", lambda s=step, i=index:
              case_analysis_c14._step(snapshot, s, f"steps[{i}]"))
    return issues


def main():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    engine = make_engine(environment(state)["DATABASE_URL"])
    results = []
    try:
        with httpx.Client(base_url="http://127.0.0.1:8215", trust_env=False, timeout=20) as client:
            auth = client.post("/api/v2/auth/login", json={"token": TEST_TOKEN},
                               headers={"Origin": "http://localhost:5215"})
            auth.raise_for_status()
            actor = UUID(auth.json()["actor_id"])
            for label, case_id, analysis_id in CASES:
                response = client.get(f"/api/v2/cases/{case_id}/analyses/{analysis_id}/diagnostic")
                response.raise_for_status()
                payload = response.json()
                assert payload["availability"] == "retained"
                diagnostic = payload["diagnostic"]
                assert not diagnostic["truncated"] and not diagnostic["credentials_redacted"]
                raw = diagnostic["raw_response"]
                assert hashlib.sha256(raw.encode("utf-8")).hexdigest() == diagnostic["sha256"]
                with engine.connect() as conn:
                    row = conn.execute(select(case_analyses).where(
                        case_analyses.c.id == UUID(analysis_id),
                        case_analyses.c.case_id == UUID(case_id),
                        case_analyses.c.owner_id == actor)).mappings().one()
                    assert row["status"] == "failed" and row["mode"] == "real"
                    assert not row["content_json"]
                    frozen = row["snapshot_json"]
                parsed = json.loads(raw)
                original = outcome(frozen, parsed)
                entry = {"label": label, "analysis_id": analysis_id,
                         "raw_sha256": diagnostic["sha256"], "complete": True,
                         "input_revision": row["input_revision"],
                         "original_contract": frozen["output_contract_version"],
                         "original": original,
                         "conversion": "not_modified"}
                if label == "C08":
                    entry["new"] = {"state": "not_directly_verifiable",
                                    "reason": "C07 free-check lacks stable question_ids; cannot fabricate record targets"}
                else:
                    proposal = CaseAdviceProposalV5.model_validate(parsed).model_dump(mode="json")
                    updated = deepcopy(frozen)
                    updated["output_contract_version"] = "case-advice-proposal-c14-v1"
                    entry["conversion"] = ("only contract_version changed in evaluation copy; "
                                           "V5 optional editorial_rule_ids/retest/safety defaults added")
                    entry["new"] = outcome(updated, proposal)
                    entry["new_independent_probes"] = independent_probes(updated, proposal)
                    if label == "C10":
                        entry["first_record_targets"] = parsed["steps"][0].get("question_ids", [])
                        entry["frozen_target_names"] = [item.get("name", "") for item in
                            updated.get("unresolved_questions", []) if item["question_id"] in
                            parsed["steps"][0].get("question_ids", [])]
                    entry["safety_source_ids"] = parsed.get("safety_source_ids", [])
                    if label == "C13":
                        saved, editorial, manual = case_analysis_c14._frozen_numbers(updated)
                        entry["summary_numeric_provenance"] = [
                            {"value": part, "unit": match.group(3),
                             "saved": (Decimal(part), match.group(3).lower()) in saved,
                             "editorial": (Decimal(part), match.group(3).lower()) in editorial,
                             "manual": bool(manual.get((Decimal(part), match.group(3).lower())))}
                            for match in case_analysis_c14.NUMBER.finditer(parsed["summary"])
                            for part in (match.group(1), match.group(2)) if part is not None]
                results.append(entry)
    finally:
        engine.dispose()
    print(json.dumps(results, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
