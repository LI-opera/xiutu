"""Bounded worker turn. Model output is a candidate, never a business write."""

import json
import os
import re
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError
from sqlalchemy import func, select

from app.agents.state import PriorCheck, ProposalContext, ProposalEnvelope, ProposeStep
from app.domain.measurements import BindEvidence
from app.domain.policies import DomainError
from app.infrastructure.model_factory import llm_factory
from app.infrastructure.model_gateway import ModelError
from app.infrastructure.orm import (
    cases,
    diagnosis_steps,
    graph_progress,
    runs,
    tool_executions,
)
from app.infrastructure.uow import UnitOfWork
from app.repositories.observations import ObservationRepository
from app.services.evidence_service import EvidenceService
from app.services.proposal_service import ProposalService
from app.skills.registry import SkillRegistry
from app.tools.executor import ToolExecutor
from app.validators.repetition import fingerprint


class WorkerIdentity:
    """Process-local principal built from owned run/case rows, not model parameters."""

    def __init__(self, actor):
        self.actor = actor
        self.cookie = os.urandom(24).hex()

    def get(self, cookie):
        if cookie != self.cookie:
            raise DomainError("CONTEXT_INVALID", "Worker identity invalid", 403)
        return SimpleNamespace(actor_id=self.actor)


def load_snapshot(engine, run_id):
    with UnitOfWork(engine) as u:
        c = u.connection
        run = c.execute(select(runs).where(runs.c.id == run_id)).mappings().one()
        case = c.execute(select(cases).where(cases.c.id == run["case_id"])).mappings().one()
        progress = c.execute(select(graph_progress).where(
            graph_progress.c.run_id == run_id)).mappings().one()
        if run["owner_id"] is not None or case["owner_id"] is None:
            raise DomainError("GRAPH_OWNER_INVALID", "Case owner required")
        if progress["graph_epoch"] != case["graph_epoch"] or progress["turn_id"] != run["turn_id"]:
            raise DomainError("GRAPH_EPOCH_STALE", "Graph epoch changed")
        if run["input_revision"] != case["revision"]:
            raise DomainError("REVISION_CONFLICT", "Case changed before turn")
        from app.infrastructure.orm import diagnosis_areas
        before = c.execute(select(diagnosis_steps).join(
            diagnosis_areas, diagnosis_areas.c.id == diagnosis_steps.c.area_id).where(
            diagnosis_steps.c.case_id == case["id"],
            diagnosis_areas.c.graph_epoch == case["graph_epoch"]).order_by(
            diagnosis_steps.c.ordinal)).mappings().all()
        seen = tuple(PriorCheck(fingerprint(ProposeStep.model_validate(x["candidate_json"])),
                                x["candidate_json"]["component_key"])
                     for x in before)
        prior_used = c.execute(select(func.coalesce(func.sum(tool_executions.c.used), 0),
                                      func.coalesce(func.sum(tool_executions.c.search_used), 0))
                               .join(runs, runs.c.id == tool_executions.c.run_id)
                               .where(runs.c.workflow_id == run["workflow_id"],
                                      runs.c.turn_id == run["turn_id"])).one()
        # WP-12 reads only persisted effective observations. Checkpoints and
        # model payloads cannot replace these facts.
        saved = ObservationRepository(c).read(case["id"], None, case["revision"])
        return dict(run=dict(run), case=dict(case), progress=dict(progress),
                    history=seen, prior_checks=[x["candidate_json"] for x in before],
                    observations=[dict(x) for x in saved],
                    tool_used=int(prior_used[0]), search_used=int(prior_used[1]))


_CANDIDATE_TYPES = frozenset({
    "request_tools", "propose_areas", "propose_step", "conclude_area", "need_input",
})
_DISPOSITIONS = frozenset({"candidate", "request_tools", "needs_input"})
_DIAGNOSTIC_CODES = frozenset({
    "ACTION_MISSING", "ACTION_SEMANTICS_UNCERTAIN", "ASSESSMENT_UNCERTAIN",
    "CHOICES_REQUIRED", "CHOICE_SEMANTICS_UNCERTAIN", "CITATION_INVALID",
    "CLAIM_UNCERTAIN", "CLAIM_UNSUPPORTED", "COMPONENT_NOT_GROUNDED",
    "CONCLUSION_SCOPE_MISMATCH", "CONDITIONS_MISSING", "CONDITIONS_UNCERTAIN",
    "CONTEXT_INCOMPLETE", "DUPLICATE_CHECK", "EVIDENCE_REQUIRED",
    "EXCLUSION_CONFLICT", "EXCLUSION_UNSUPPORTED", "HISTORY_UNSUPPORTED",
    "INPUT_KIND_MISMATCH", "INTERPRETATION_UNCERTAIN", "LOCATION_MISSING",
    "LOCATION_UNCERTAIN", "MEASUREMENT_USE_MISMATCH", "NOT_CHECKED",
    "OBSERVATION_INVALID", "PROFILE_MISMATCH", "PROPOSAL_SCHEMA_INVALID",
    "RETEST_LIMIT", "RETEST_REASON_UNCERTAIN", "RETEST_REASON_UNSUPPORTED",
    "RETEST_SOURCE_INVALID", "RETEST_WITHOUT_PRIOR", "SCOPE_NOT_MATCHED",
    "SOURCE_INVALID", "SPEC_COMPONENT_MISMATCH", "SPEC_CONDITIONS_MISMATCH",
    "SPEC_INVALID", "SPEC_REQUIRED", "SPEC_SOURCE_MISMATCH",
    "SPEC_VALUE_MISMATCH", "STRUCTURED_SPEC_REQUIRED",
    "SUPPORT_COMPARISON_INVALID", "SUPPORT_COMPARISON_MISMATCH",
    "SUPPORT_PREMISE_CONFLICT", "SUPPORT_PREMISE_MISSING",
    "SUPPORT_RULE_SCOPE_MISMATCH", "SUPPORT_SOURCE_INVALID",
    "SUPPORT_SOURCE_MISMATCH", "TOOL_ARGUMENTS_INVALID",
    "TOOL_BUDGET_EXHAUSTED", "TOOL_FORBIDDEN",
})
_DIAGNOSTIC_PATHS = frozenset({
    "actions", "areas", "assessment", "calls", "choices", "finding",
    "history", "input", "interpretation", "location", "prerequisites",
    "proposal", "purpose", "references", "retest",
})


def _proposal_diagnostic(sink, stage, *, candidate=None, checked=None,
                         schema_invalid=False, repair_used=False, error_code=None):
    """Emit only bounded validator identifiers to a trusted, optional sink."""
    if sink is None:
        return
    kind = candidate.get("type") if isinstance(candidate, dict) else None
    if not isinstance(kind, str) or kind not in _CANDIDATE_TYPES:
        kind = None
    issues = []
    for item in (checked or {}).get("issues", [])[:32]:
        code, path = item.get("code"), item.get("path")
        issues.append({
            "code": code if isinstance(code, str) and code in _DIAGNOSTIC_CODES
            else "UNAVAILABLE",
            "path": path if isinstance(path, str)
            and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.\[\]]{0,119}", path)
            and re.split(r"[.\[]", path, maxsplit=1)[0] in _DIAGNOSTIC_PATHS
            else "unavailable",
        })
    disposition = (checked or {}).get("disposition")
    event = {
        "stage": stage,
        "candidate_type": kind,
        "schema_status": "invalid" if schema_invalid else "valid",
        "disposition": disposition if isinstance(disposition, str)
        and disposition in _DISPOSITIONS else None,
        "issues": issues,
        "issue_count": len((checked or {}).get("issues", [])),
        "repair_used": repair_used,
        "error_code": error_code if error_code in
        {"MODEL_SCHEMA_INVALID", "REPAIR_EXHAUSTED"} else None,
    }
    try:
        sink(event)
    except Exception:
        # Optional diagnostics must never change validation, budget or fencing.
        pass


def _initial_source_chunks(executor, context, query):
    """Expand the first hits through the existing authorized, bounded context tool."""
    found = executor.execute(context, "search_manuals",
                             {"query": query, "vehicle_scope": {}, "top_k": 5},
                             "graph-initial-search")
    if not found["ok"]:
        raise ModelError(found["error"]["code"])
    hits = found["data"]["chunks"]
    selected = []
    seen = set()

    def add(chunk):
        key = (chunk["chunk_id"], chunk["document_version_id"], chunk["index_id"])
        if key not in seen:
            seen.add(key)
            selected.append(chunk)

    # Ranked hits can cluster around one part of a source. Expand up to three
    # distinct hits; skip hits already returned as neighbors. This keeps the
    # original six-call tool ceiling and leaves at least two calls for the model.
    expanded = 0
    for hit in hits:
        if expanded >= 3:
            break
        key = (hit["chunk_id"], hit["document_version_id"], hit["index_id"])
        if key in seen:
            continue
        nearby = executor.execute(context, "get_evidence_context", {
            "chunk_id": hit["chunk_id"],
            "document_version_id": hit["document_version_id"],
            "neighbors": 2,
        }, f"graph-initial-context-{expanded}")
        if not nearby["ok"]:
            raise ModelError(nearby["error"]["code"])
        for chunk in nearby["data"]["chunks"]:
            if (chunk["document_version_id"] != hit["document_version_id"]
                    or chunk["index_id"] != hit["index_id"]):
                raise ModelError("DIAGNOSIS_EVIDENCE_UNAVAILABLE")
            add(chunk)
        expanded += 1
    for hit in hits:
        add(hit)
    return selected[:12]


def run_diagnosis(store, lease, stopped, *, settings=None, gateway_factory=None,
                  executor_factory=None, skill_ref=None, diagnostic_sink=None):
    staged = store.staged_diagnosis(lease)
    if staged is not None:
        return staged
    from app.config import load_settings

    settings = settings or store.settings or load_settings(
        project_env=os.environ.get("XIUTU_LOAD_PROJECT_ENV") == "1"
    )
    snapshot = load_snapshot(store.engine, lease.job["run_id"])
    run, case, progress = snapshot["run"], snapshot["case"], snapshot["progress"]
    if stopped.is_set():
        raise ModelError("DIAGNOSIS_INTERRUPTED")
    # R1 makes the planner choice an explicit persisted case decision.  Legacy
    # cases with no mode continue on their historical path; conservative cases
    # must never fall through to a model.
    if case.get("diagnosis_mode") == "conservative":
        from app.services.protocol_service import ProtocolService
        protocol_result = ProtocolService(store.engine, settings).route(run, case, progress)
        if protocol_result is None:
            raise ModelError("CONSERVATIVE_PROTOCOL_UNAVAILABLE")
        store.stage_diagnosis(lease, protocol_result)
        return protocol_result
    def seconds_left():
        remaining = 120 - (datetime.now(timezone.utc) - progress["created_at"]).total_seconds()
        if remaining <= 0:
            raise ModelError("MODEL_TURN_TIMEOUT")
        return remaining

    seconds_left()
    calls_left = 6 - snapshot["tool_used"]
    searches_left = 3 - snapshot["search_used"]
    if calls_left <= 0 or searches_left <= 0:
        raise ModelError("TOOL_TURN_BUDGET_EXHAUSTED")
    identity = WorkerIdentity(case["owner_id"])
    executor = (executor_factory or ToolExecutor)(store.engine, settings)
    context = executor.contexts.open(
        identity, identity.cookie, case["id"], run_id=run["id"],
        allowlist=["search_manuals", "get_evidence_context", "get_measurement_spec"],
        call_limit=calls_left, search_limit=searches_left, retry_limit=1,
    )
    # This real business tool consults the frozen manifest and current review.
    source_chunks = _initial_source_chunks(executor, context, case["fault_description"])
    seconds_left()
    citations = []
    binder = EvidenceService(store.engine, settings)
    for chunk in source_chunks:
        if stopped.is_set():
            raise ModelError("DIAGNOSIS_INTERRUPTED")
        # Bind complete source paragraphs/table rows, not fragments. The WP-10
        # support gate requires an exact contextual quote and never infers
        # arbitrary paraphrase from a vector hit.
        parts = re.finditer(r"[^\n]+(?:\n(?!\n)[^\n]+)*", chunk["text"])
        for match in parts:
            if len(citations) >= 12:
                break
            quote = match.group().strip()
            if not quote or len(quote) > 20000:
                continue
            start = match.start() + len(match.group()) - len(match.group().lstrip())
            end = start + len(quote)
            body = BindEvidence(chunk_id=UUID(chunk["chunk_id"]),
                                document_version_id=UUID(chunk["document_version_id"]),
                                index_id=UUID(chunk["index_id"]), start=start, end=end,
                                quote=quote)
            _, item = binder.bind(case["owner_id"], case["id"], body,
                "graph-" + str(run["turn_id"]) + "-" + chunk["chunk_id"] + "-" + str(start))
            citations.append({"evidence_id": item["evidence_id"],
                              "document_version_id": chunk["document_version_id"],
                              "quote": quote, "locator": item["snapshot"]["locator"]})
    if not citations:
        raise ModelError("DIAGNOSIS_EVIDENCE_UNAVAILABLE")
    if gateway_factory is None and os.environ.get("XIUTU_WP11_PAID") != "1":
        raise ModelError("MODEL_CALL_DISABLED")
    # Search and evidence binding may take time before the first paid request.
    # Never give the gateway a stale full turn allowance after that work.
    remaining = seconds_left()
    make_gateway = gateway_factory or (lambda: llm_factory(
        settings, paid=True, turn_id=str(run["turn_id"]),
        turn_seconds_remaining=remaining, resume_existing=True,
        prompt_version="wp11-v2", max_output_tokens=settings.diagnosis_max_output_tokens,
        max_model_calls=4))
    gateway = make_gateway()
    try:
        skill = None
        skill_text = ""
        if skill_ref:
            name, version = skill_ref.split(":", 1)
            skill = SkillRegistry().load_body(name, version)
            skill_text = "\nTrusted method skill (not repair evidence): " + skill["body"]
        prompt = (
            "Suggest one grounded propose_step, or conclude_area with assessment unknown "
            "only after a saved checked observation, or need_input. An area end is merely "
            "a request for a conservative server-generated card, never a diagnosis. Do not invent "
            "repair values. Only cite the supplied evidence IDs and versions. "
            "For every factual claim, use an exact self-contained excerpt from its cited "
            "quote; do not paraphrase an unsupported inference. Include a location only "
            "when the source actually gives one. Do not invent a measurement standard or "
            "prerequisite. If no supported check can be formed, return need_input. "
            "For propose_step, keep each location, prerequisite, action and observation "
            "choice as a complete source sentence with its own matching citation. A location "
            "must state the component and an explicit spatial relation; a prerequisite must "
            "state the documented operating condition; an action must name the component, "
            "operation and inspection object. Choices must be documented nonnumerical "
            "observations, never inferred normality. Free-text diagnostic interpretation "
            "does not become supported merely by citation: omit unsupported interpretation "
            "or return need_input, never silently turn it into an authorized conclusion. "
            "The bounded synthetic DKVB demo also permits an exact S01/S02/S03 drawing "
            "location, the explicit no-real-pressure demo condition, a localized-leak "
            "inspection, and the three cited localized/not-found/inconclusive choices. "
            "These demo forms never establish a real vehicle location or leak diagnosis. "
            "FACT/EDITORIAL/DEMO distinctions and simulated thresholds must remain explicit. "
            "You may call only the available read-only business tools. Return JSON matching "
            + json.dumps(ProposalEnvelope.model_json_schema(), ensure_ascii=False,
                         separators=(",", ":"))
            + skill_text
        )
        vehicle = {k: v for k, v in case["vehicle_json"].items() if k != "vin"}
        message = {"vehicle": vehicle, "fault_description": case["fault_description"],
                   "fault_codes": case["fault_codes"], "citations": citations,
                   "saved_observations": [
                       {"id": str(x["id"]), "step_id": str(x["step_id"]) if x["step_id"] else None,
                        "kind": x["kind"], "payload": x["payload"]}
                       for x in snapshot["observations"]],
                   "prior_checks": snapshot["prior_checks"]}
        target_area = run["input_payload"].get("area_activation")
        if target_area:
            from app.infrastructure.orm import diagnosis_areas
            with UnitOfWork(store.engine) as u:
                area = u.connection.execute(select(diagnosis_areas).where(
                    diagnosis_areas.c.id == UUID(target_area),
                    diagnosis_areas.c.case_id == case["id"],
                    diagnosis_areas.c.graph_epoch == case["graph_epoch"])
                ).mappings().one_or_none()
            if area is None or area["status"] in {"retired", "stale", "completed"}:
                raise ModelError("AREA_ACTIVATION_INVALID")
            message["target_area"] = {"component_key": area["component_key"],
                                       "title": area["title"]}
        messages = [SystemMessage(content=prompt),
                    HumanMessage(content=json.dumps(message, ensure_ascii=False))]
        allowed = {"search_manuals", "get_evidence_context", "get_measurement_spec"}
        proposal_context = ProposalContext(case["owner_id"], case["id"], case["revision"],
                                           frozenset(allowed), snapshot["history"])
        proposal_service = ProposalService(store.engine, settings)
        records = []
        rejected_candidate = None
        try:
            proposal, records = gateway.run_tools(
                messages, ProposalEnvelope, executor, context,
                allowed_tools=allowed, skill=skill["metadata"] if skill else None,
                tool_round_limit=2, structured_repair=False)
            if stopped.is_set():
                raise ModelError("DIAGNOSIS_INTERRUPTED")
            candidate = proposal.model_dump(mode="json")
            checked = proposal_service.validate(proposal_context, candidate)
            _proposal_diagnostic(diagnostic_sink, "initial",
                                 candidate=candidate, checked=checked)
            seconds_left()
            if checked["accepted"] and (
                candidate["type"] == "propose_step" or
                (candidate["type"] == "conclude_area" and candidate["assessment"] == "unknown")
            ):
                checked["tool_call_count"] = len(records)
                checked["proposal_repair_used"] = False
                store.stage_diagnosis(lease, checked)
                return checked
            if candidate["type"] == "need_input":
                raise ModelError("DIAGNOSIS_PROPOSAL_NEEDS_INPUT")
            issues = checked["issues"]
            rejected_candidate = candidate
        except ModelError as exc:
            if exc.code != "MODEL_SCHEMA_INVALID":
                raise
            _proposal_diagnostic(diagnostic_sink, "initial", schema_invalid=True,
                                 error_code=exc.code)
            issues = [{"code": exc.code, "path": "proposal"}]
        try:
            store.reserve_diagnosis_repair(lease)
        except DomainError as exc:
            if exc.code == "REPAIR_EXHAUSTED":
                _proposal_diagnostic(diagnostic_sink, "repair_budget",
                                     repair_used=True, error_code=exc.code)
            raise
        if stopped.is_set():
            raise ModelError("DIAGNOSIS_INTERRUPTED")
        repair_context = {
            "rejected_candidate": rejected_candidate,
            "issues": [{"code": item["code"], "path": item["path"]} for item in issues],
        }
        repair = gateway.request(
            messages + [HumanMessage(content=(
                "Repair the rejected candidate once using only its already supplied evidence IDs. "
                "Preserve fields that passed validation. For INTERPRETATION_UNCERTAIN at "
                "interpretation, use an empty interpretation array; do not turn an untested "
                "caution into a diagnosis. If the remaining fields cannot be supported, "
                "return need_input. Return the complete proposal JSON. Repair context: "
                + json.dumps(repair_context, ensure_ascii=False, separators=(",", ":"))
            ))],
            response_format={"type": "json_object"})
        try:
            if repair.tool_calls:
                raise ValueError()
            candidate = ProposalEnvelope.model_validate_json(repair.content, strict=True)
        except (ValidationError, ValueError, TypeError):
            _proposal_diagnostic(diagnostic_sink, "repair", schema_invalid=True,
                                 repair_used=True, error_code="MODEL_SCHEMA_INVALID")
            raise ModelError("MODEL_SCHEMA_INVALID") from None
        if stopped.is_set():
            raise ModelError("DIAGNOSIS_INTERRUPTED")
        candidate = candidate.model_dump(mode="json")
        checked = proposal_service.validate(proposal_context, candidate)
        _proposal_diagnostic(diagnostic_sink, "repair", candidate=candidate,
                             checked=checked, repair_used=True)
        seconds_left()
        checked["tool_call_count"] = len(records)
        checked["proposal_repair_used"] = True
        if not checked["accepted"] or not (
            candidate["type"] == "propose_step" or
            (candidate["type"] == "conclude_area" and candidate["assessment"] == "unknown")
        ):
            raise ModelError("DIAGNOSIS_PROPOSAL_NEEDS_INPUT")
        store.stage_diagnosis(lease, checked)
        return checked
    finally:
        gateway.close()
