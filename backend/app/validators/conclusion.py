"""Two bounded reviewed relations; no document text is executable policy."""

import hashlib
import json
from uuid import UUID

from app.domain.policies import DomainError
from app.infrastructure.orm import case_evidence, measurement_comparisons, measurement_specs
from app.services.evidence_service import row_owned


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_conclusion(c, context, proposal, observations, evidence, settings, rules):
    def failure(code, detail):
        return [dict(code=code, path="assessment", detail=detail)], None

    rule = rules.get(proposal.support_rule_id)
    if rule is None:
        return failure(
            "ASSESSMENT_UNCERTAIN",
            "No trusted reviewed support mapping; quote equality or within_range is insufficient",
        )
    if (
        rule.owner_id != context.actor
        or rule.case_id != context.case_id
        or rule.profile != settings.retrieval_profile
        or rule.component_key != proposal.component_key
    ):
        return failure(
            "SUPPORT_RULE_SCOPE_MISMATCH", "Rule ownership, case, profile or object differs"
        )
    exclusion = rule.kind == "housing_intact_comparison_exclusion"
    assessment = "temporarily_excluded" if exclusion else "hypothesis"
    scope = "housing_damage" if exclusion else "contact_fault"
    if proposal.assessment != assessment or proposal.conclusion_scope != scope:
        return failure(
            "CONCLUSION_SCOPE_MISMATCH", "Candidate exceeds the reviewed assessment or cause scope"
        )
    ev = row_owned(c, context.actor, case_evidence, rule.evidence_id)
    valid = evidence.validity(c, context.actor, ev)
    if (
        ev["case_id"] != context.case_id
        or ev["document_version_id"] != rule.document_version_id
        or ev["profile"] != rule.profile
        or ev["authorization_epoch"] != rule.authorization_epoch
        or not valid["valid"]
        or valid["applicability"]["status"] != "matched"
        or hashlib.sha256(ev["quote"].encode()).hexdigest() != rule.quote_sha256
    ):
        return failure("SUPPORT_SOURCE_INVALID", "Reviewed source binding is no longer valid")
    if (
        len(proposal.finding.references) != 1
        or proposal.finding.references[0].evidence_id != rule.evidence_id
        or proposal.finding.references[0].document_version_id != rule.document_version_id
        or proposal.finding.text != ev["quote"]
    ):
        return failure(
            "SUPPORT_SOURCE_MISMATCH",
            "Finding must cite the exact reviewed source, not invent a wider conclusion",
        )

    selected = set(proposal.observation_ids)
    effective = {o["id"] for o in observations}
    if not selected or not selected <= effective:
        return failure("OBSERVATION_INVALID", "Current case/revision observations required")
    conditions = {"engine": rule.engine}
    field, expected = ("housing_state", "intact") if exclusion else ("connector_state", "detached")
    matched = []
    # Inspect all effective records for this object/field, not just model-selected evidence.
    for obs in observations:
        payload = obs["payload"]
        if payload.get("component_key") != rule.component_key or field not in payload:
            continue
        if (
            obs["actor_id"] != context.actor
            or obs["kind"] == "unavailable"
            or payload.get("checked") is not True
            or payload.get("conditions") != conditions
            or payload[field] != expected
        ):
            return failure(
                "SUPPORT_PREMISE_CONFLICT",
                "Relevant observations are unchecked, mismatched or conflicting",
            )
        if obs["id"] in selected:
            matched.append(str(obs["id"]))
    if not matched:
        return failure(
            "SUPPORT_PREMISE_MISSING",
            "Selected observations do not establish the reviewed state premise",
        )

    comparison_ids = []
    if exclusion:
        spec = row_owned(c, context.actor, measurement_specs, rule.spec_id)
        definition = spec["definition"]
        sev = row_owned(c, context.actor, case_evidence, spec["evidence_id"])
        sv = evidence.validity(c, context.actor, sev)
        if (
            sev["case_id"] != context.case_id
            or not sv["valid"]
            or sv["applicability"]["status"] != "matched"
            or spec["needs_review"]
            or spec["review_status"] != "approved"
            or definition["component_key"] != rule.component_key
            or definition["conditions"] != conditions
            or digest(definition) != rule.spec_definition_sha256
        ):
            return failure(
                "SUPPORT_SPEC_INVALID", "Exact approved specification/source/conditions required"
            )
        for obs in observations:
            payload = obs["payload"]
            if payload.get("component_key") != rule.component_key or "comparison_id" not in payload:
                continue
            try:
                comp = row_owned(
                    c, context.actor, measurement_comparisons, UUID(payload["comparison_id"])
                )
                if comp["spec_id"] != rule.spec_id:
                    if obs["id"] in selected:
                        return failure(
                            "SUPPORT_COMPARISON_MISMATCH",
                            "Selected comparison uses another specification",
                        )
                    continue
                view = evidence.get_comparison(context.actor, comp["id"], connection=c)
                result = comp["result"]
                if (
                    obs["actor_id"] != context.actor
                    or obs["kind"] == "unavailable"
                    or payload.get("checked") is not True
                    or payload.get("conditions") != conditions
                    or comp["case_id"] != context.case_id
                    or not view["current_validity"]["valid"]
                    or result["input"]["conditions"] != conditions
                    or digest(result["spec_definition"]) != rule.spec_definition_sha256
                    or result["outcome"] != "within_range"
                ):
                    return failure(
                        "SUPPORT_COMPARISON_INVALID",
                        "Same-spec comparison is invalid, conflicting or not qualified",
                    )
                if obs["id"] in selected:
                    comparison_ids.append(str(comp["id"]))
            except (ValueError, TypeError, KeyError, DomainError):
                return failure(
                    "SUPPORT_COMPARISON_INVALID", "Comparison cannot be used for this conclusion"
                )
        if not comparison_ids:
            return failure(
                "SUPPORT_PREMISE_MISSING",
                "A selected current qualified comparison is required in addition to intact housing",
            )
    statement = (
        f"仅在列明工况下暂时排除 {rule.component_key} 的外壳破损；其他原因未定，不表示整个部件正常。"
        if exclusion
        else f"{rule.component_key} 的接触不良仅为待验证假设，尚未确诊。"
    )
    return [], dict(
        rule_id=str(rule.rule_id),
        rule_hash=digest(rule.model_dump(mode="json")),
        reviewed_by=str(rule.reviewed_by),
        reviewed_at=rule.reviewed_at.isoformat(),
        evidence_id=str(rule.evidence_id),
        document_version_id=str(rule.document_version_id),
        assessment=assessment,
        component_key=rule.component_key,
        scope=scope,
        conditions=conditions,
        statement=statement,
        other_causes="unknown",
        confirmed=False,
        observation_ids=matched,
        comparison_ids=comparison_ids,
        synthetic=rule.profile == "synthetic",
    )
