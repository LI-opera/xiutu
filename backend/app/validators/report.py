"""Bounded report draft and deterministic source/action validation."""

import json
from uuid import UUID

from pydantic import Field

from app.domain.policies import DomainError
from app.domain.schemas import InputModel, PersistedText
from app.infrastructure.orm import case_evidence, measurement_specs
from app.services.evidence_service import EvidenceService, row_owned


class ReportClaim(InputModel):
    text: PersistedText = Field(min_length=1, max_length=1200)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=12)
    observation_ids: list[UUID] = Field(default_factory=list, max_length=12)
    spec_ids: list[UUID] = Field(default_factory=list, max_length=8)


class ReportAction(InputModel):
    id: PersistedText = Field(min_length=1, max_length=60)
    target: PersistedText = Field(min_length=1, max_length=100)
    reason: PersistedText = Field(min_length=1, max_length=1200)
    prerequisites: list[PersistedText] = Field(default_factory=list, max_length=10)
    instructions: PersistedText = Field(min_length=1, max_length=2000)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=12)
    observation_ids: list[UUID] = Field(min_length=1, max_length=12)
    spec_ids: list[UUID] = Field(default_factory=list, max_length=8)
    depends_on_action_ids: list[PersistedText] = Field(default_factory=list, max_length=12)
    completion_criteria: PersistedText = Field(min_length=1, max_length=1200)


class ReportDraft(InputModel):
    scope: PersistedText = Field(min_length=1, max_length=500)
    confirmed_facts: list[ReportClaim] = Field(default_factory=list, max_length=40)
    diagnostic_findings: list[ReportClaim] = Field(default_factory=list, max_length=30)
    unresolved_items: list[PersistedText] = Field(default_factory=list, max_length=40)
    repair_actions: list[ReportAction] = Field(default_factory=list, max_length=30)
    verification_actions: list[ReportAction] = Field(default_factory=list, max_length=30)
    limitations: list[PersistedText] = Field(default_factory=list, max_length=30)


def validate_draft(c, actor, snap, draft, settings, *, final):
    draft = ReportDraft.model_validate(draft)
    body = draft.model_dump(mode="json")
    if len(json.dumps(body, ensure_ascii=False).encode()) > 100_000:
        raise DomainError("REPORT_TOO_LARGE", "Report exceeds size limit", 422)
    case = snap["case"]
    cards = snap["cards"]
    allowed_evidence = set()
    allowed_observations = set(snap["observations"])
    allowed_specs = set()
    trusted_actions = {}
    trusted_repair_actions = {}
    trusted_findings = {}
    trusted_facts = {}

    def action_key(action):
        value = action if isinstance(action, dict) else action.model_dump(mode="json")
        return (value.get("target"), value.get("reason"),
                tuple(value.get("prerequisites", [])), value.get("instructions"),
                value.get("completion_criteria"))

    for card in cards.values():
        if card["needs_review"]:
            continue
        data = card["content_json"] or {}
        allowed_evidence.update(data.get("source_evidence_ids", []))
        allowed_specs.update(data.get("spec_ids", []))
        basis = (set(data.get("source_evidence_ids", [])),
                 set(data.get("observation_ids", [])),
                 set(data.get("spec_ids", [])))
        if isinstance(data.get("finding"), str):
            trusted_findings[data["finding"]] = basis
        for fact in data.get("confirmed_facts", []):
            if isinstance(fact, str):
                trusted_facts[fact] = basis
        for action in data.get("report_actions", []):
            if isinstance(action, dict):
                key = action_key(action)
                trusted_actions[key] = basis
                if card["assessment"] == "supported":
                    trusted_repair_actions[key] = basis
    source = EvidenceService(None, settings)

    def check_refs(item):
        if final and not item.evidence_ids:
            raise DomainError("REPORT_CITATION_REQUIRED", "Final claim needs a source", 422)
        if not item.evidence_ids and not item.observation_ids:
            raise DomainError("REPORT_CITATION_REQUIRED", "Claim needs current facts", 422)
        for eid in item.evidence_ids:
            if str(eid) not in allowed_evidence:
                raise DomainError("REPORT_SOURCE_INVALID", "Source is outside current conclusions", 422)
            try:
                row = row_owned(c, actor, case_evidence, eid)
                if row["case_id"] != case["id"] or not source.validity(c, actor, row)["valid"]:
                    raise DomainError("REPORT_SOURCE_INVALID", "Source is no longer valid", 422)
            except DomainError:
                raise DomainError("REPORT_SOURCE_INVALID", "Source is no longer valid", 422) from None
        for oid in item.observation_ids:
            if oid not in allowed_observations or not snap["observations"][oid]["payload"].get("checked"):
                raise DomainError("REPORT_OBSERVATION_INVALID", "Observation is not current", 422)
        for sid in item.spec_ids:
            if str(sid) not in allowed_specs:
                raise DomainError("REPORT_SPEC_INVALID", "Specification is not in current conclusions", 422)
            try:
                spec = row_owned(c, actor, measurement_specs, sid)
                evidence = row_owned(c, actor, case_evidence, spec["evidence_id"])
                if (evidence["case_id"] != case["id"] or spec["review_status"] != "approved"
                        or spec["needs_review"] or not source.validity(c, actor, evidence)["valid"]):
                    raise DomainError("REPORT_SPEC_INVALID", "Specification is not valid", 422)
            except DomainError:
                raise DomainError("REPORT_SPEC_INVALID", "Specification is not valid", 422) from None

    def in_basis(item, basis):
        return (set(map(str, item.evidence_ids)) <= basis[0]
                and set(map(str, item.observation_ids)) <= basis[1]
                and set(map(str, item.spec_ids)) <= basis[2])

    for claim in [*draft.confirmed_facts, *draft.diagnostic_findings]:
        check_refs(claim)
    if final:
        for claim in draft.confirmed_facts:
            basis = trusted_facts.get(claim.text)
            if basis is None or not in_basis(claim, basis):
                raise DomainError("REPORT_CLAIM_UNSUPPORTED", "Fact is not in current conclusions", 422)
        for claim in draft.diagnostic_findings:
            basis = trusted_findings.get(claim.text)
            if basis is None or not in_basis(claim, basis):
                raise DomainError("REPORT_CLAIM_UNSUPPORTED", "Finding is not in current conclusions", 422)
    if not final and draft.repair_actions:
        raise DomainError("PROGRESS_REPAIR_FORBIDDEN", "Progress report cannot recommend replacement", 422)
    actions = [*draft.repair_actions, *draft.verification_actions]
    ids = [a.id for a in actions]
    if len(ids) != len(set(ids)):
        raise DomainError("REPORT_ACTION_DUPLICATE", "Action IDs repeat", 422)
    signatures = [(a.target.casefold().strip(), a.instructions.casefold().strip()) for a in actions]
    if len(signatures) != len(set(signatures)):
        raise DomainError("REPORT_ACTION_DUPLICATE", "Equivalent actions repeat", 422)
    deps = {a.id: a.depends_on_action_ids for a in actions}
    visited, visiting = set(), set()

    def visit(node):
        if node in visiting:
            raise DomainError("REPORT_ACTION_CYCLE", "Action dependencies contain a cycle", 422)
        if node in visited:
            return
        visiting.add(node)
        for dependency in deps[node]:
            if dependency not in deps:
                raise DomainError("REPORT_ACTION_DEPENDENCY", "Action dependency is unknown", 422)
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for action in actions:
        check_refs(action)
        if final:
            trusted = trusted_repair_actions if action in draft.repair_actions else trusted_actions
            basis = trusted.get(action_key(action))
            if basis is None or not in_basis(action, basis):
                raise DomainError("REPORT_ACTION_UNSUPPORTED", "Action is not in approved conclusions", 422)
        visit(action.id)
    return body
