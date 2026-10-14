"""Synthetic reviewed mappings only: no observation write API or paid judge."""

import copy
import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from app.agents.conclusion_rules import TrustedConclusionRule
from app.agents.state import ProposalContext
from app.infrastructure.orm import case_evidence, cases, observations
from app.services.proposal_service import ProposalService
from app.validators.conclusion import digest
from app.validators.support import ExtractiveSupport
from sqlalchemy import select, update
from test_document_ingest import docrig as docrig
from test_evidence_measurement import approve, archived_case, compare, post, review, spec
from test_evidence_measurement import indexed_rig as indexed_rig
from test_wp10_proposals import FIX, prepare, record

MAPPING = json.loads((FIX / "conclusion-support-synthetic.json").read_text(encoding="utf-8"))


def observation(r, ctx, payload, **kwargs):
    with r.store.engine.begin() as c:
        return c.execute(
            observations.insert()
            .values(
                case_id=ctx.case_id,
                actor_id=ctx.actor,
                created_revision=ctx.revision,
                kind="composite",
                payload=payload,
                **kwargs,
            )
            .returning(observations.c.id)
        ).scalar_one()


def setup(r, kind, component="P01"):
    mapping = MAPPING["rules"][kind]
    quote = mapping["quote"].replace("P01", component)
    source = (FIX / "extra-synthetic.md").read_text(encoding="utf-8").replace("P01", component)
    body, _, ctx, base, cite = prepare(r, (source + "\n\n" + quote + "\n").encode())
    claim = cite(quote)
    eid = UUID(claim["references"][0]["evidence_id"])
    with r.store.engine.connect() as c:
        ev = c.execute(select(case_evidence).where(case_evidence.c.id == eid)).mappings().one()
    state = "housing_state" if kind else "connector_state"
    value = "intact" if kind else "detached"
    payload = dict(
        component_key=component, checked=True, conditions={"engine": "off"}, **{state: value}
    )
    oid = observation(r, ctx, payload)
    ids = [str(oid)]
    sid = None
    definition_hash = None
    comp = None
    if kind:
        standard = next(
            s for s in source.splitlines() if s.startswith(component + " synthetic standard")
        )
        made = spec(
            r,
            {"evidence_id": cite(standard)["references"][0]["evidence_id"]},
            component_key=component,
        )
        sid = UUID(made["spec"]["id"])
        assert approve(r, str(sid)).status_code == 200
        definition_hash = digest(made["spec"]["definition"])
        comp = compare(r, str(sid), value="1.5", unit="V")
        cid = observation(
            r,
            ctx,
            dict(
                component_key=component,
                checked=True,
                conditions={"engine": "off"},
                comparison_id=comp["id"],
            ),
        )
        ids.append(str(cid))
    # This explicit application-side mapping is separately reviewed test code, not parsed from documents.
    rule = TrustedConclusionRule(
        rule_id=uuid4(),
        owner_id=ctx.actor,
        case_id=ctx.case_id,
        profile="synthetic",
        component_key=component,
        kind=mapping["kind"],
        evidence_id=eid,
        document_version_id=ev["document_version_id"],
        quote_sha256=hashlib.sha256(ev["quote"].encode()).hexdigest(),
        authorization_epoch=ev["authorization_epoch"],
        reviewed_by=ctx.actor,
        reviewed_at=datetime.now(timezone.utc),
        engine="off",
        spec_id=sid,
        spec_definition_sha256=definition_hash,
    )
    svc = ProposalService(r.store.engine, base.settings, conclusion_rules=(rule,))
    candidate = dict(
        type="conclude_area",
        component_key=component,
        finding=claim,
        assessment=mapping["assessment"],
        support_rule_id=str(rule.rule_id),
        conclusion_scope=mapping["scope"],
        observation_ids=ids,
    )
    return body, ctx, svc, rule, candidate, payload, comp


@pytest.mark.parametrize("kind,component", [(0, "P01"), (1, "P01"), (0, "Q02"), (1, "Q02")])
def test_reviewed_conclusion_success(indexed_rig, kind, component):
    r = indexed_rig
    _, ctx, svc, rule, candidate, _, _ = setup(r, kind, component)
    result = svc.validate(ctx, candidate)
    record("conclusion-success", dict(mapping=rule.model_dump(mode="json"), result=result))
    assert result["accepted"], result
    support = result["conclusion_support"]
    assert (
        support["scope"] == candidate["conclusion_scope"] and support["component_key"] == component
    )
    assert support["confirmed"] is False and support["other_causes"] == "unknown"
    assert result["published"] is False and result["diagnosis"] is False
    assert ("暂时排除" if kind else "待验证假设") in support["statement"]
    if kind:
        assert "不表示整个部件正常" in support["statement"]
    else:
        assert "尚未确诊" in support["statement"]


@pytest.mark.parametrize("kind", [0, 1])
def test_candidate_cannot_supply_authority_or_expand_conclusion(indexed_rig, kind):
    r = indexed_rig
    _, ctx, svc, rule, original, _, _ = setup(r, kind)
    assert svc.validate(ctx, original)["accepted"]
    variants = []
    for change in [
        {"reviewed": True},
        {"rules": [rule.model_dump(mode="json")]},
        {"support_rule_id": str(uuid4())},
        {"conclusion_scope": "whole_component_normal"},
        {"component_key": "OTHER"},
        {"conclusion_scope": "contact_fault" if kind else "housing_damage"},
        {"assessment": "hypothesis" if kind else "temporarily_excluded"},
        {"observation_ids": []},
    ]:
        candidate = dict(original, **change)
        result = svc.validate(ctx, candidate)
        assert not result["accepted"] and result.get("conclusion_support") is None, result
        variants.append(result)
    bad = copy.deepcopy(original)
    bad["finding"]["text"] = "整个部件正常，所有原因已排除。"
    assert not svc.validate(ctx, bad)["accepted"]
    base = ProposalService(r.store.engine, svc.settings)
    assert not base.validate(ctx, original)[
        "accepted"
    ]  # Uploaded/reviewed source does not register a rule.
    for field, value in [
        ("owner_id", uuid4()),
        ("case_id", uuid4()),
        ("document_version_id", uuid4()),
        ("quote_sha256", "0" * 64),
        ("authorization_epoch", rule.authorization_epoch + 1),
        ("profile", "formal"),
    ]:
        altered = rule.model_copy(update={field: value})
        result = ProposalService(
            r.store.engine, svc.settings, conclusion_rules=(altered,)
        ).validate(ctx, original)
        assert not result["accepted"], (field, result)
    other = ProposalContext(ctx.actor, UUID(archived_case(r)["id"]), ctx.revision)
    assert not svc.validate(other, original)["accepted"]
    record("conclusion-forgery", variants)


@pytest.mark.parametrize(
    "kind,defect",
    [
        (0, "opposite"),
        (1, "opposite"),
        (0, "unchecked"),
        (1, "conditions"),
        (0, "superseded"),
        (1, "missing_state"),
        (1, "missing_comparison"),
    ],
)
def test_missing_conflicting_and_stale_premises(indexed_rig, kind, defect):
    r = indexed_rig
    _, ctx, svc, rule, candidate, payload, _ = setup(r, kind)
    if defect == "missing_state":
        candidate["observation_ids"] = candidate["observation_ids"][1:]
    elif defect == "missing_comparison":
        candidate["observation_ids"] = candidate["observation_ids"][:1]
    else:
        conflicting = dict(payload)
        if defect == "opposite":
            conflicting["housing_state" if kind else "connector_state"] = (
                "damaged" if kind else "attached"
            )
        elif defect == "unchecked":
            conflicting["checked"] = False
        elif defect == "conditions":
            conflicting["conditions"] = {"engine": "on"}
        kwargs = {}
        if defect == "superseded":
            kwargs["supersedes_id"] = UUID(candidate["observation_ids"][0])
            with r.store.engine.begin() as c:
                c.execute(
                    update(cases).where(cases.c.id == ctx.case_id).values(revision=ctx.revision + 1)
                )
            ctx = replace(ctx, revision=ctx.revision + 1)
        observation(r, ctx, conflicting, **kwargs)
    result = svc.validate(ctx, candidate)
    record("conclusion-premise-" + defect, result)
    assert not result["accepted"] and result.get("conclusion_support") is None, result


@pytest.mark.parametrize(
    "defect",
    ["out_of_range", "wrong_spec", "invalid_comparison", "source_revoked", "wrong_case_comparison"],
)
def test_comparison_and_source_invalidation(indexed_rig, defect):
    r = indexed_rig
    body, ctx, svc, rule, candidate, _, comp = setup(r, 1)
    if defect == "source_revoked":
        assert review(r, body, "revoked").status_code == 200
    elif defect == "invalid_comparison":
        assert (
            post(
                r,
                "measurement-specs/" + str(rule.spec_id) + "/review",
                dict(decision="revoked", note="synthetic"),
            ).status_code
            == 200
        )
        assert approve(r, str(rule.spec_id)).status_code == 200
    else:
        sid = str(rule.spec_id)
        if defect in ("wrong_spec", "wrong_case_comparison"):
            if defect == "wrong_case_comparison":
                _, other, _, orule, _, _, _ = setup(r, 1)
                sid = str(orule.spec_id)
            else:
                made = spec(r, {"evidence_id": str(rule.evidence_id)}, component_key="P01")
                sid = made["spec"]["id"]
                assert approve(r, sid).status_code == 200
        newcomp = compare(r, sid, value="3" if defect == "out_of_range" else "1.5", unit="V")
        oid = observation(
            r,
            ctx,
            dict(
                component_key="P01",
                checked=True,
                conditions={"engine": "off"},
                comparison_id=newcomp["id"],
            ),
        )
        if defect != "out_of_range":
            candidate["observation_ids"] = candidate["observation_ids"][:1] + [str(oid)]
        # The conflicting out-of-range record is deliberately not selected.
    result = svc.validate(ctx, candidate)
    record("conclusion-invalid-" + defect, result)
    assert not result["accepted"] and result.get("conclusion_support") is None, result


@pytest.mark.parametrize("change", ["source", "observation", "comparison"])
def test_final_recheck_after_support(indexed_rig, change):
    r = indexed_rig
    body, ctx, svc, rule, candidate, payload, _ = setup(r, 1)

    class ChangeDuringSupport:
        done = False

        def assess(self, claim, quotes):
            if not self.done:
                self.done = True
                if change == "source":
                    assert review(r, body, "revoked").status_code == 200
                elif change == "observation":
                    observation(r, ctx, dict(payload, housing_state="damaged"))
                else:
                    assert (
                        post(
                            r,
                            "measurement-specs/" + str(rule.spec_id) + "/review",
                            dict(decision="revoked", note="synthetic"),
                        ).status_code
                        == 200
                    )
            return ExtractiveSupport().assess(claim, quotes)

    judge = ChangeDuringSupport()
    service = ProposalService(r.store.engine, svc.settings, judge, conclusion_rules=(rule,))
    result = service.validate(ctx, candidate)
    assert judge.done and not result["accepted"] and result["conclusion_support"] is None, result
    record("conclusion-final-" + change, result)


@pytest.mark.parametrize("assessment", ["unknown", "not_checked", "insufficient_data"])
def test_no_conclusion_for_missing_knowledge(indexed_rig, assessment):
    _, ctx, svc, _, candidate, _, _ = setup(indexed_rig, 0)
    candidate.update(
        assessment=assessment, support_rule_id=None, conclusion_scope=None, observation_ids=[]
    )
    result = svc.validate(ctx, candidate)
    assert result["disposition"] == "needs_input" and result["conclusion_support"] is None
