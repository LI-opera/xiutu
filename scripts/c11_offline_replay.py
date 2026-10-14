"""Owner-checked, read-only C10 replay. Never starts a model task.

Restricted raw response is held only in memory. Output must not include it.
"""

import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import requests
from sqlalchemy import select
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.domain.case_analysis import CaseAdviceProposalV4  # noqa: E402
from app.domain.policies import DomainError  # noqa: E402
from app.infrastructure.orm import case_analyses  # noqa: E402
from app.infrastructure.uow import make_engine  # noqa: E402
from app.services import case_analysis_c09 as c09  # noqa: E402
from app.legacy_execution.case_analysis import assemble_proposal, validate_advice  # noqa: E402
from scripts.wp15_workbench import RUNTIME, STATE, TEST_TOKEN, environment  # noqa: E402

CASE_ID = UUID("d109a875-70e9-46aa-a198-7c75048aa8b3")
ANALYSIS_ID = UUID("b6ab0831-8c3c-4499-89a2-3a41e52e0b71")
EXPECTED_SHA256 = "0ae39556e0226e45e81369dc6ec354392d17ff8c7ee9d20c7a4d4d8fdb6b5d6b"


def load_frozen():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    env = environment(state)  # Default stub branch; never reads or injects a model key.
    engine = make_engine(env["DATABASE_URL"])
    with requests.Session() as session:
        login = session.post("http://127.0.0.1:8215/api/v2/auth/login",
                             json={"token": TEST_TOKEN},
                             headers={"Origin": "http://localhost:5215"}, timeout=10)
        login.raise_for_status()
        actor_id = UUID(login.json()["actor_id"])
        result = session.get(
            f"http://127.0.0.1:8215/api/v2/cases/{CASE_ID}/analyses/{ANALYSIS_ID}/diagnostic",
            timeout=10)
        result.raise_for_status()
        restricted = result.json()
    assert restricted["availability"] == "retained"
    diagnostic = restricted["diagnostic"]
    assert not diagnostic["truncated"] and not diagnostic["credentials_redacted"]
    raw = diagnostic["raw_response"]
    assert hashlib.sha256(raw.encode("utf-8")).hexdigest() == diagnostic["sha256"] == EXPECTED_SHA256
    assert len(raw.encode("utf-8")) == diagnostic["response_utf8_bytes"]
    with engine.connect() as conn:
        row = conn.execute(select(case_analyses).where(
            case_analyses.c.id == ANALYSIS_ID, case_analyses.c.case_id == CASE_ID,
            case_analyses.c.owner_id == actor_id)).mappings().one()
    engine.dispose()
    assert row["status"] == "failed" and row["mode"] == "real"
    assert row["input_revision"] == 42
    assert not row["content_json"]  # No offline result may be mistaken for published advice.
    assert row["diagnostic_json"]["sha256"] == diagnostic["sha256"]
    snapshot = row["snapshot_json"]
    assert snapshot["output_contract_version"] == "case-advice-proposal-c09-v1"
    assert snapshot["case_id"] == str(CASE_ID)
    proposal = CaseAdviceProposalV4.model_validate_json(raw)
    return snapshot, proposal.model_dump(mode="json"), diagnostic, row


def preview(value, limit=135):
    return str(value).replace("\n", " ")[:limit]


def inspect(snapshot, proposal, diagnostic, row):
    print(json.dumps({
        "analysis_id": str(ANALYSIS_ID), "status": row["status"],
        "revision": row["input_revision"], "contract": snapshot["output_contract_version"],
        "raw_bytes": diagnostic["response_utf8_bytes"], "truncated": diagnostic["truncated"],
        "sha256": diagnostic["sha256"], "original_rule": diagnostic.get("validation", {}).get("rule_id"),
        "original_field": diagnostic.get("validation", {}).get("field_path"),
        "allowed_scope": snapshot["allowed_scope"],
        "observation_count": len(snapshot["observations"]),
        "source_ids": [item["id"] for item in snapshot["source_context"]["excerpts"]],
        "editorial_thresholds": [(item["value"], item["unit"], item["kind"])
                                 for item in snapshot.get("editorial_thresholds", [])],
        "action_ids": list(snapshot.get("action_catalog", {}).get("actions", {})),
    }, ensure_ascii=False, indent=2))
    for field in ("summary", "retest_plan", "uncertainty", "safety_notice"):
        print(field, preview(proposal[field], 230))
    print("safety_source_ids", proposal["safety_source_ids"])
    for index, item in enumerate(proposal["supported_directions"]):
        print("direction", index, {k: preview(v) if isinstance(v, str) else v for k, v in item.items()})
    for index, item in enumerate(proposal["unconfirmed_directions"]):
        print("unconfirmed", index, preview(item))
    for index, item in enumerate(proposal["steps"]):
        print("step", index, {k: preview(v) if isinstance(v, str) else v for k, v in item.items()})


def diagnose(snapshot, proposal, diagnostic, row, label):
    """Independent field probes plus the unchanged full publication path.

    A clause probe can find more issues in one field, but it is not a claim that
    the full original proposal passes or that arbitrary prose was exhaustively audited.
    """
    findings = []
    independent_sections = []
    numeric_provenance = []

    saved_numbers, editorial_numbers = c09._numbers(snapshot)
    manual_numbers = {}
    for entry in snapshot["source_context"]["excerpts"]:
        for match in c09.NUMBER.finditer(entry["text"]):
            quantity = (Decimal(match.group(1)), re.sub(r"[·.\s]", "", match.group(3)).lower())
            manual_numbers.setdefault(quantity, []).append(entry["id"])

    def audit_numbers(path, value):
        for match in c09.NUMBER.finditer(value):
            unit = re.sub(r"[·.\s]", "", match.group(3)).lower()
            for part in (match.group(1), match.group(2)):
                if part is None:
                    continue
                quantity = (Decimal(part), unit)
                item = {"field_path": path, "value": str(quantity[0]), "unit": unit,
                        "frozen_kinds": (["saved_or_derived"] if quantity in saved_numbers else []) +
                                        (["editorial_demo"] if quantity in editorial_numbers else []) +
                                        (["local_manual"] if quantity in manual_numbers else []),
                        "manual_source_ids": manual_numbers.get(quantity, [])}
                if item not in numeric_provenance:
                    numeric_provenance.append(item)

    def probe(kind, path, operation):
        try:
            operation()
        except DomainError as exc:
            details = exc.details or {}
            finding = {"probe": kind, "field_path": details.get("field_path", path),
                       "rule_id": details.get("rule_id", exc.code), "code": exc.code,
                       "reason": exc.message[:160], "actual": preview(details.get("actual") or "", 120)}
            if finding not in findings:
                findings.append(finding)
            return False
        except ValidationError as exc:
            findings.append({"probe": kind, "field_path": path,
                             "rule_id": "proposal.structure", "code": "VALIDATION_ERROR",
                             "reason": preview(exc.errors()[0].get("msg", "")), "actual": ""})
            return False
        return True

    for field in ("summary", "retest_plan", "uncertainty", "safety_notice"):
        audit_numbers(field, proposal[field])
        role = "safety" if field == "safety_notice" else "uncertainty" if field == "uncertainty" else "explanation"
        sources = proposal["safety_source_ids"] if field == "safety_notice" else ()
        probe("whole_field", field, lambda f=field, r=role, s=sources:
              c09.check_text(snapshot, f, proposal[f], role=r, safety_sources=s))
        for index, clause in enumerate(c09._clauses(proposal[field])):
            probe("independent_clause", f"{field}#clause{index}", lambda f=field, v=clause, r=role, s=sources:
                  c09.check_text(snapshot, f, v, role=r, safety_sources=s,
                                 context=proposal[f], clause_index=index))
    probe("reference", "safety_notice.source_ids", lambda:
          c09._refs(snapshot, "safety_notice", sources=proposal["safety_source_ids"]))
    for index, value in enumerate(proposal["unconfirmed_directions"]):
        path = f"unconfirmed_directions[{index}]"
        audit_numbers(path, value)
        probe("whole_field", path, lambda p=path, v=value: c09.check_text(snapshot, p, v, role="explanation"))
        for index, clause in enumerate(c09._clauses(value)):
            probe("independent_clause", path, lambda p=path, v=clause:
                  c09.check_text(snapshot, p, v, role="explanation", context=value,
                                 clause_index=index))
    for index, item in enumerate(proposal["supported_directions"]):
        path = f"supported_directions[{index}]"
        independent_sections.append({"path": path, "passed": probe(
            "section", path, lambda p=path, v=item: c09._direction(snapshot, v, p))})
        probe("reference", path, lambda p=path, v=item: c09._refs(
            snapshot, p, v["basis_observation_ids"], v["source_ids"]))
        for field in ("title", "limit"):
            role = "direction_limit" if field == "limit" else "direction"
            audit_numbers(path + "." + field, item[field])
            probe("whole_field", path + "." + field, lambda p=path, v=item, f=field, r=role:
                  c09.check_text(snapshot, p + "." + f, v[f], role=r))
            for clause_index, clause in enumerate(c09._clauses(item[field])):
                probe("independent_clause", path + "." + field, lambda p=path, f=field, v=clause, r=role:
                      c09.check_text(snapshot, p + "." + f, v, role=r,
                                     context=item[f], clause_index=clause_index))
    for index, item in enumerate(proposal["steps"]):
        path = f"steps[{index}]"
        independent_sections.append({"path": path, "passed": probe(
            "section", path, lambda p=path, v=item: c09._step(snapshot, v, p))})
        probe("reference", path, lambda p=path, v=item: c09._refs(
            snapshot, p, v.get("basis_observation_ids", []), v.get("source_ids", []),
            v.get("missing_question_ids", [])))
        for field in ("request", "action", "reason"):
            if field not in item:
                continue
            role = "record" if item["type"] == "record" else "handoff"
            audit_numbers(path + "." + field, item[field])
            probe("whole_field", path + "." + field, lambda p=path, v=item, f=field, r=role:
                  c09.check_text(snapshot, p + "." + f, v[f], role=r,
                                 record_question_ids=v.get("question_ids", [])))
            for clause_index, clause in enumerate(c09._clauses(item[field])):
                probe("independent_clause", path + "." + field,
                      lambda p=path, f=field, v=clause, r=role:
                      c09.check_text(snapshot, p + "." + f, v, role=r,
                                     record_question_ids=item.get("question_ids", []),
                                     context=item[f], clause_index=clause_index))
    full = {"state": "not_checked"}
    stage = "assembly"
    try:
        assembled = assemble_proposal(snapshot, proposal)
        stage = "final_validation"
        published = validate_advice(snapshot, assembled)
        full = {"stage": "full_publication_validation", "state": published["publication"]["state"],
                "rejected_sections": published["publication"]["rejected_sections"],
                "direction_count": len(published["supported_directions"]),
                "step_count": len(published["steps"]),
                "controlled_steps": [step["action_id"] for step in published["steps"] if step["action_id"]]}
    except DomainError as exc:
        details = exc.details or {}
        full = {"stage": stage, "state": "rejected", "code": exc.code,
                "rule_id": details.get("rule_id"), "field_path": details.get("field_path"),
                "reason": exc.message[:160]}
    except ValidationError as exc:
        full = {"stage": "proposal_structure", "state": "structure_rejected", "errors": [
            {"path": list(item["loc"]), "type": item["type"]} for item in exc.errors()[:12]]}
    artifact = {"label": "C10 历史真实回复的离线校验结果，未发布为病例建议", "phase": label,
                "analysis_id": str(ANALYSIS_ID), "case_id": str(CASE_ID),
                "input_revision": row["input_revision"], "contract": snapshot["output_contract_version"],
                "raw_sha256": diagnostic["sha256"], "raw_complete": not diagnostic["truncated"],
                "original_status": row["status"], "original_rule": diagnostic.get("validation", {}).get("rule_id"),
                "original_field": diagnostic.get("validation", {}).get("field_path"),
                "field_probe_findings": findings, "independent_sections": independent_sections,
                "numeric_provenance": numeric_provenance,
                "full_publication_check": full,
                "probe_limit": "逐字段/分句探针独立执行，不证明任意自然语言风险已穷尽。"}
    target = RUNTIME / f"c11-{label}-offline-diagnostic.json"
    target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"artifact": str(target), "raw_sha256": diagnostic["sha256"],
                      "finding_count": len(findings), "findings": findings,
                      "independent_sections": independent_sections,
                      "number_count": len(numeric_provenance),
                      "unsupported_numbers": [item for item in numeric_provenance if not item["frozen_kinds"]],
                      "full_publication_check": full}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["inspect", "diagnose"])
    parser.add_argument("--label", choices=["before", "after"], default="before")
    args = parser.parse_args()
    snapshot, proposal, diagnostic, row = load_frozen()
    if args.mode == "inspect":
        inspect(snapshot, proposal, diagnostic, row)
    else:
        diagnose(snapshot, proposal, diagnostic, row, args.label)


if __name__ == "__main__":
    main()
