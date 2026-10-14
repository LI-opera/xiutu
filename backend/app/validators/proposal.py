"""WP10 read-only hard gate reusing WP06 source and specification validity."""

import json
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID

from sqlalchemy import select

from app.agents.conclusion_rules import TrustedConclusionRule
from app.agents.state import ConcludeArea, ProposeAreas, ProposeStep, RequestTools
from app.domain.policies import DomainError, check_revision
from app.infrastructure.orm import case_evidence, chunks, measurement_comparisons, measurement_specs
from app.repositories.observations import ObservationRepository
from app.services.evidence_scope import owned_case
from app.services.evidence_service import EvidenceService, row_owned
from app.tools.schemas import INPUTS
from app.validators.conclusion import validate_conclusion
from app.validators.repetition import action_key, normalize
from app.validators.support import (
    has_complete_context,
    has_numeric_standard,
    location_supported,
    operating_conditions,
    table_requires_spec,
)


def claims(proposal):
    if isinstance(proposal, ProposeAreas):
        return [
            ("areas", a.rationale, a.component_key)
            for top in proposal.areas
            for a in [top, *top.children]
        ]
    if isinstance(proposal, ProposeStep):
        out = [("purpose", proposal.purpose, proposal.component_key)]
        if proposal.location:
            out.append(("location", proposal.location, proposal.component_key))
        for name in ["prerequisites", "actions", "interpretation"]:
            out += [(name, c, proposal.component_key) for c in getattr(proposal, name)]
        out += [("choices", c, proposal.component_key) for c in proposal.input.choices]
        if proposal.retest:
            out.append(("retest", proposal.retest.reason, proposal.component_key))
        return out
    if isinstance(proposal, ConcludeArea):
        return [("finding", proposal.finding, proposal.component_key)]
    return []


def issue(code, path, detail):
    return dict(code=code, path=path, detail=detail)


class HardGate:
    def __init__(self, engine, settings, conclusion_rules=()):
        self.evidence = EvidenceService(engine, settings)
        self.settings = settings
        if len(conclusion_rules) > 16 or any(
            not isinstance(r, TrustedConclusionRule) for r in conclusion_rules
        ):
            raise ValueError("Only bounded trusted application rule objects are allowed")
        if len({r.rule_id for r in conclusion_rules}) != len(conclusion_rules):
            raise ValueError("Duplicate rule identity")
        self.conclusion_rules = MappingProxyType({r.rule_id: r for r in conclusion_rules})

    def load(self, c, context, proposal):
        case = owned_case(c, context.actor, context.case_id)
        check_revision(case["revision"], context.revision)
        issues = []
        quotes = {}
        provenance = []
        for path, claim, component in claims(proposal):
            if not claim.references:
                issues.append(issue("EVIDENCE_REQUIRED", path, "Current cited evidence required"))
            for ref in claim.references:
                ev = row_owned(c, context.actor, case_evidence, ref.evidence_id)
                if (
                    ev["case_id"] != context.case_id
                    or ev["document_version_id"] != ref.document_version_id
                ):
                    raise DomainError("CITATION_INVALID", "Evidence case/version mismatch")
                valid = self.evidence.validity(c, context.actor, ev)
                if not valid["valid"]:
                    issues.append(
                        issue("SOURCE_INVALID", path, "Evidence revoked or integrity invalid")
                    )
                elif valid["applicability"]["status"] != "matched":
                    issues.append(issue("SCOPE_NOT_MATCHED", path, "Exact applicability required"))
                if ev["profile"] != self.settings.retrieval_profile:
                    issues.append(issue("PROFILE_MISMATCH", path, "Profile not allowed"))
                if valid["valid"]:
                    source_text = c.execute(
                        select(chunks.c.text).where(chunks.c.id == ev["chunk_id"])
                    ).scalar_one()
                    if not has_complete_context(source_text, ev["start_offset"], ev["end_offset"]):
                        issues.append(
                            issue(
                                "CONTEXT_INCOMPLETE",
                                path,
                                "Quote must retain full paragraph or complete table row; isolated slices cannot prove support",
                            )
                        )
                if claim.text == ev["quote"].strip() and table_requires_spec(
                    ev["quote"], ev["locator"]
                ):
                    issues.append(
                        issue(
                            "STRUCTURED_SPEC_REQUIRED",
                            path,
                            "Table header units and applicability cannot be interpreted as a prose choice; use an approved structured spec",
                        )
                    )
                quotes[str(ref.evidence_id)] = ev["quote"]
                provenance.append(
                    dict(
                        evidence_id=str(ev["id"]),
                        document_version_id=str(ev["document_version_id"]),
                        chunk_id=str(ev["chunk_id"]),
                        index_id=str(ev["index_id"]),
                        hash=ev["content_hash"],
                        locator=ev["locator"],
                        synthetic=ev["profile"] == "synthetic",
                    )
                )
            if has_numeric_standard(claim.text):
                issues.append(
                    issue(
                        "STRUCTURED_SPEC_REQUIRED",
                        path,
                        "Numerical standards must be structured approved specs, not prose",
                    )
                )
            if path in ("areas", "location", "actions") and normalize(component) not in normalize(
                claim.text
            ):
                issues.append(
                    issue(
                        "COMPONENT_NOT_GROUNDED",
                        path,
                        "Physical object must be explicit in the cited claim",
                    )
                )
        if isinstance(proposal, RequestTools):
            searches = 0
            for call in proposal.calls:
                if call.name not in context.allowed_tools or call.name not in INPUTS:
                    issues.append(issue("TOOL_FORBIDDEN", "calls", "Tool not in trusted allowlist"))
                    continue
                try:
                    INPUTS[call.name].model_validate(call.arguments)
                except ValueError:
                    issues.append(
                        issue("TOOL_ARGUMENTS_INVALID", "calls", "Invalid tool arguments")
                    )
                searches += int(call.name == "search_manuals")
            if searches > 3:
                issues.append(
                    issue("TOOL_BUDGET_EXHAUSTED", "calls", "At most three search intentions")
                )
        if isinstance(proposal, ProposeStep):
            if not proposal.location:
                issues.append(issue("LOCATION_MISSING", "location", "Source location required"))
            if not proposal.prerequisites:
                issues.append(
                    issue(
                        "CONDITIONS_MISSING",
                        "prerequisites",
                        "Explicit source operating conditions required",
                    )
                )
            if not proposal.actions:
                issues.append(issue("ACTION_MISSING", "actions", "A sourced action is required"))
            if proposal.location and not location_supported(
                proposal.location.text, proposal.component_key
            ):
                issues.append(
                    issue(
                        "LOCATION_UNCERTAIN",
                        "location",
                        "A source-backed explicit spatial relation is required",
                    )
                )
            conditions = operating_conditions(proposal.prerequisites)
            if proposal.prerequisites and conditions is None:
                issues.append(
                    issue(
                        "CONDITIONS_UNCERTAIN",
                        "prerequisites",
                        "Operating conditions are outside the supported grammar",
                    )
                )
            for action in proposal.actions:
                if action_key(action, proposal.component_key) is None:
                    issues.append(
                        issue(
                            "ACTION_SEMANTICS_UNCERTAIN",
                            "actions",
                            "Operation cannot be verified from action wording",
                        )
                    )
            inp = proposal.input
            allowed_choices = {
                normalize(proposal.component_key + suffix)
                for suffix in (
                    "未检查时不得排除",
                    "外观完好",
                    "外观损坏",
                    "插头松动",
                    "插头牢固",
                    "外壳破损",
                    "外壳完整",
                    "已定位局部泄漏",
                    "未发现局部泄漏",
                    "局部泄漏结果无法确定",
                    "已完成模拟接头处理",
                    "模拟接头处理尚未完成",
                    "提交处理后复检记录",
                    "提交最终演示复检记录",
                )
            }
            for choice in inp.choices:
                if normalize(choice.text) not in allowed_choices:
                    issues.append(
                        issue(
                            "CHOICE_SEMANTICS_UNCERTAIN",
                            "input.choices",
                            "Only bounded nonnumerical observations are supported; numerical decisions require approved structured specs",
                        )
                    )
            if proposal.interpretation:
                issues.append(
                    issue(
                        "INTERPRETATION_UNCERTAIN",
                        "interpretation",
                        "Free-text diagnostic interpretation is not authorized by extraction; structured comparison is not a diagnosis",
                    )
                )
            if any(a.operation == "measure" for a in proposal.actions) and not inp.measurements:
                issues.append(
                    issue(
                        "SPEC_REQUIRED",
                        "input",
                        "Measurement actions require an approved numerical specification",
                    )
                )
            if inp.kind in ("measurement", "composite") and not inp.measurements:
                issues.append(issue("SPEC_REQUIRED", "input", "Measurement standard missing"))
            if inp.kind in ("choice", "composite") and not inp.choices:
                issues.append(issue("CHOICES_REQUIRED", "input", "Observable choices missing"))
            if inp.kind == "choice" and inp.measurements:
                issues.append(
                    issue("INPUT_KIND_MISMATCH", "input", "Choice cannot conceal measurements")
                )
            if inp.kind == "measurement" and inp.choices:
                issues.append(
                    issue("INPUT_KIND_MISMATCH", "input", "Measurement cannot conceal choices")
                )
            action_quantities = {
                key[2]
                for a in proposal.actions
                if (key := action_key(a, proposal.component_key)) and key[0] == "measure"
            }
            if action_quantities != {m.quantity for m in inp.measurements}:
                issues.append(
                    issue(
                        "MEASUREMENT_USE_MISMATCH",
                        "actions",
                        "Measurement objects must match the approved input quantities",
                    )
                )
            referenced = {UUID(k) for k in quotes}
            for asserted in inp.measurements:
                spec = row_owned(c, context.actor, measurement_specs, asserted.spec_id)
                if (
                    spec["evidence_id"] not in referenced
                    or asserted.evidence_id != spec["evidence_id"]
                ):
                    issues.append(
                        issue(
                            "SPEC_SOURCE_MISMATCH",
                            "input",
                            "Spec must use this proposal's cited evidence",
                        )
                    )
                ev = row_owned(c, context.actor, case_evidence, spec["evidence_id"])
                if ev["case_id"] != context.case_id:
                    raise DomainError("CITATION_INVALID", "Spec case mismatch")
                if (
                    spec["needs_review"]
                    or spec["review_status"] != "approved"
                    or not self.evidence.validity(c, context.actor, ev)["valid"]
                ):
                    issues.append(
                        issue("SPEC_INVALID", "input", "Spec is not currently approved and valid")
                    )
                definition = spec["definition"]
                if conditions != definition["conditions"]:
                    issues.append(
                        issue(
                            "SPEC_CONDITIONS_MISMATCH",
                            "prerequisites",
                            "Actual step conditions must equal the approved specification conditions",
                        )
                    )
                if normalize(asserted.component_key) != normalize(proposal.component_key):
                    issues.append(issue("SPEC_COMPONENT_MISMATCH", "input", "Wrong component"))
                for k in [
                    "component_key",
                    "quantity",
                    "unit",
                    "conditions",
                    "lower_inclusive",
                    "upper_inclusive",
                    "lower",
                    "upper",
                ]:
                    actual = getattr(asserted, k)
                    expected = definition[k]
                    if k in ("lower", "upper") and actual is not None and expected is not None:
                        actual, expected = Decimal(actual), Decimal(expected)
                    if actual != expected:
                        issues.append(
                            issue(
                                "SPEC_VALUE_MISMATCH",
                                "input." + k,
                                "Approved specification differs",
                            )
                        )
        observations = []
        if isinstance(proposal, ConcludeArea) or (
            isinstance(proposal, ProposeStep) and proposal.retest
        ):
            observations = ObservationRepository(c).read(context.case_id, None, context.revision)
            byid = {str(o["id"]): o for o in observations}
            ids = (
                proposal.observation_ids
                if isinstance(proposal, ConcludeArea)
                else proposal.retest.observation_ids
            )
            for oid in ids:
                if str(oid) not in byid:
                    issues.append(
                        issue(
                            "OBSERVATION_INVALID",
                            "observation_ids",
                            "Not an effective observation of this case/revision",
                        )
                    )
            if isinstance(proposal, ConcludeArea) and proposal.assessment in (
                "hypothesis",
                "temporarily_excluded",
            ):
                if not ids:
                    issues.append(
                        issue(
                            "NOT_CHECKED",
                            "observation_ids",
                            "No checked observation; cannot conclude",
                        )
                    )
                for oid in ids:
                    obs = byid.get(str(oid))
                    payload = obs["payload"] if obs else {}
                    if (
                        payload.get("component_key") != proposal.component_key
                        or payload.get("checked") is not True
                    ):
                        issues.append(
                            issue(
                                "NOT_CHECKED",
                                "observation_ids",
                                "Checked component observation required",
                            )
                        )
                        continue
                    # Exclusion requires an actual current successful comparison, not a model boolean.
                    if (
                        proposal.assessment == "temporarily_excluded"
                        and proposal.support_rule_id is None
                    ):
                        try:
                            comp = row_owned(
                                c,
                                context.actor,
                                measurement_comparisons,
                                UUID(payload.get("comparison_id", "")),
                            )
                            view = self.evidence.get_comparison(
                                context.actor, comp["id"], connection=c
                            )
                            if (
                                comp["case_id"] != context.case_id
                                or not view["current_validity"]["valid"]
                                or comp["result"]["outcome"] != "within_range"
                                or comp["result"]["spec_definition"]["component_key"]
                                != proposal.component_key
                            ):
                                raise ValueError()
                        except (ValueError, DomainError):
                            issues.append(
                                issue(
                                    "EXCLUSION_UNSUPPORTED",
                                    "observation_ids",
                                    "Current checked comparison required; not a diagnosis",
                                )
                            )
        if (
            isinstance(proposal, ConcludeArea)
            and proposal.assessment == "temporarily_excluded"
            and proposal.support_rule_id is None
        ):
            # Do not cherry-pick a normal measurement while ignoring conflicting current records.
            for obs in observations:
                payload = obs["payload"]
                if payload.get("component_key") != proposal.component_key:
                    continue
                try:
                    comp = row_owned(
                        c,
                        context.actor,
                        measurement_comparisons,
                        UUID(payload.get("comparison_id", "")),
                    )
                    view = self.evidence.get_comparison(context.actor, comp["id"], connection=c)
                    if (
                        comp["case_id"] != context.case_id
                        or not view["current_validity"]["valid"]
                        or comp["result"]["outcome"] != "within_range"
                    ):
                        raise ValueError()
                except (ValueError, DomainError):
                    issues.append(
                        issue(
                            "EXCLUSION_CONFLICT",
                            "observation_ids",
                            "Unresolved component records prevent exclusion",
                        )
                    )
        if isinstance(proposal, ProposeStep) and proposal.retest:
            groups = {}
            if normalize(proposal.retest.reason.text) != normalize(
                proposal.component_key + " 测量记录冲突，需要同工况复测。"
            ):
                issues.append(
                    issue(
                        "RETEST_REASON_UNCERTAIN",
                        "retest",
                        "Reason must identify this component and same-condition measurement conflict",
                    )
                )
            wanted = {str(x) for x in proposal.retest.observation_ids}
            for obs in observations:
                if str(obs["id"]) not in wanted:
                    continue
                try:
                    if obs["payload"].get("checked") is not True or normalize(
                        obs["payload"].get("component_key", "")
                    ) != normalize(proposal.component_key):
                        raise ValueError()
                    comp = row_owned(
                        c,
                        context.actor,
                        measurement_comparisons,
                        UUID(obs["payload"].get("comparison_id", "")),
                    )
                    view = self.evidence.get_comparison(context.actor, comp["id"], connection=c)
                    if (
                        comp["case_id"] != context.case_id
                        or not view["current_validity"]["valid"]
                        or normalize(comp["result"]["spec_definition"]["component_key"])
                        != normalize(proposal.component_key)
                    ):
                        raise ValueError()
                    if not any(
                        str(m.spec_id) == str(comp["spec_id"])
                        and m.conditions == comp["result"]["input"]["conditions"]
                        for m in proposal.input.measurements
                    ):
                        raise ValueError()
                    definition = comp["result"]["spec_definition"]
                    group = (
                        normalize(definition["component_key"]),
                        str(comp["spec_id"]),
                        definition["quantity"],
                        json.dumps(
                            comp["result"]["input"]["conditions"],
                            sort_keys=True,
                            ensure_ascii=False,
                        ),
                    )
                    groups.setdefault(group, set()).add(comp["result"]["outcome"])
                except (ValueError, KeyError, DomainError):
                    issues.append(
                        issue(
                            "RETEST_SOURCE_INVALID",
                            "retest",
                            "Conflict comparison not valid for this check",
                        )
                    )
            required = {
                (
                    normalize(m.component_key),
                    str(m.spec_id),
                    m.quantity,
                    json.dumps(m.conditions, sort_keys=True, ensure_ascii=False),
                )
                for m in proposal.input.measurements
            }
            if not required or any(
                not {"within_range", "out_of_range"} <= groups.get(key, set()) for key in required
            ):
                issues.append(
                    issue(
                        "RETEST_REASON_UNSUPPORTED",
                        "retest",
                        "Two contradictory current comparisons under the same standard required",
                    )
                )
        conclusion_support = None
        if isinstance(proposal, ConcludeArea) and proposal.assessment in (
            "hypothesis",
            "temporarily_excluded",
        ):
            rule_issues, conclusion_support = validate_conclusion(
                c,
                context,
                proposal,
                observations,
                self.evidence,
                self.settings,
                self.conclusion_rules,
            )
            issues.extend(rule_issues)
        return dict(
            conclusion_support=conclusion_support,
            issues=issues,
            quotes=quotes,
            provenance=provenance,
            observations=observations,
            case=case,
        )
