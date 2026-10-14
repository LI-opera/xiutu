"""Formal regressions promoted from r1 counterexamples; assertions retained."""

import copy
import json
import os
from pathlib import Path

import pytest
from app.agents.state import PriorCheck, ProposalContext, ProposeStep
from app.infrastructure.orm import observations
from app.validators.repetition import fingerprint
from test_document_ingest import docrig as docrig
from test_evidence_measurement import approve, compare, spec
from test_evidence_measurement import indexed_rig as indexed_rig
from test_wp10_proposals import FIX, prepare, synthetic_step

EXTRA = """

发动机运转，engine=on。

检查 P01 插头。

检查 P01 外壳。

检查 P01 电压是否为一伏。

| 部件 | 电压合格范围（V），仅engine=off |
|---|---|
| P01 | 1–2 |
"""


def save(name, data):
    if os.environ.get("WP10_EVIDENCE"):
        (Path(os.environ["WP10_EVIDENCE"]) / (name + ".json")).write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )


def measurement(r, cite, candidate):
    standard = next(
        x
        for x in (FIX / "extra-synthetic.md").read_text(encoding="utf-8").splitlines()
        if x.startswith("P01 synthetic standard")
    )
    std = cite(standard)
    made = spec(r, {"evidence_id": std["references"][0]["evidence_id"]}, component_key="P01")
    sid = made["spec"]["id"]
    assert approve(r, sid).status_code == 200
    candidate["purpose"]["references"] += std["references"]
    candidate["actions"] = [dict(**cite("测量 P01 的电压。"), operation="measure")]
    candidate["input"] = dict(
        kind="measurement", measurements=[dict(**made["spec"]["definition"], spec_id=sid)]
    )
    return sid


@pytest.mark.parametrize(
    "mode",
    [
        "valid",
        "multi_claim",
        "location_role",
        "condition_conflict",
        "table_numeric",
        "chinese_number",
        "within_exclusion",
        "distinct_action",
    ],
)
def test_business_boundaries(indexed_rig, mode):
    r = indexed_rig
    _, _, ctx, svc, cite = prepare(r, (FIX / "extra-synthetic.md").read_bytes() + EXTRA.encode())
    proposal = synthetic_step(cite)
    good = svc.validate(ctx, proposal)
    assert good["accepted"], good
    expected = False
    context = ctx
    if mode == "valid":
        expected = True
    elif mode == "multi_claim":
        proposal["purpose"]["text"] += " H01已经排除。"
    elif mode == "location_role":
        proposal["location"] = cite("P01 是隔离台架的合成检查部件。")
    elif mode == "condition_conflict":
        measurement(r, cite, proposal)
        proposal["prerequisites"] = [cite("发动机运转，engine=on。")]
    elif mode == "table_numeric":
        proposal["input"]["choices"] = [cite("| P01 | 1–2 |")]
    elif mode == "chinese_number":
        proposal["actions"] = [dict(**cite("检查 P01 电压是否为一伏。"), operation="inspect")]
    elif mode == "within_exclusion":
        sid = measurement(r, cite, proposal)
        comp = compare(r, sid, value="1.5", unit="V")
        with r.store.engine.begin() as c:
            oid = c.execute(
                observations.insert()
                .values(
                    case_id=ctx.case_id,
                    kind="measurement",
                    payload=dict(component_key="P01", checked=True, comparison_id=comp["id"]),
                    created_revision=ctx.revision,
                    actor_id=ctx.actor,
                )
                .returning(observations.c.id)
            ).scalar_one()
        proposal = dict(
            type="conclude_area",
            component_key="P01",
            finding=cite("P01 是隔离台架的合成检查部件。"),
            assessment="temporarily_excluded",
            observation_ids=[str(oid)],
        )
    elif mode == "distinct_action":
        first = copy.deepcopy(proposal)
        first["actions"] = [dict(**cite("检查 P01 插头。"), operation="inspect")]
        one = svc.validate(ctx, first)
        assert one["accepted"], one
        proposal["actions"] = [dict(**cite("检查 P01 外壳。"), operation="inspect")]
        assert svc.validate(ctx, proposal)["accepted"]
        context = ProposalContext(
            ctx.actor, ctx.case_id, ctx.revision, history=(PriorCheck(one["fingerprint"], "P01"),)
        )
        expected = True
    result = svc.validate(context, proposal)
    save(mode, dict(expected_accepted=expected, proposal=proposal, result=result))
    assert result["accepted"] is expected, result
    if mode == "table_numeric":
        assert "STRUCTURED_SPEC_REQUIRED" in {x["code"] for x in result["issues"]}


def test_distinct_component_and_conditions():
    # Independent comparison of keys, not using the implementation to choose expected equality.
    def claim(text):
        return dict(text=text)

    base = dict(
        type="propose_step",
        component_key="P01",
        title="x",
        purpose=claim("x"),
        location=claim("P01左侧"),
        prerequisites=[claim("发动机关闭")],
        actions=[dict(**claim("检查 P01 插头"), operation="inspect")],
        input=dict(kind="choice", choices=[claim("未检查")]),
    )
    a = ProposeStep.model_validate(base)
    b = a.model_copy(deep=True)
    b.component_key = "H01"
    c = a.model_copy(deep=True)
    c.prerequisites[0].text = "发动机运转"
    assert fingerprint(a) != fingerprint(b) and fingerprint(a) != fingerprint(c)


def test_retest_requires_same_measurement_conflict(indexed_rig):
    r = indexed_rig
    content = (
        (FIX / "extra-synthetic.md").read_bytes()
        + "\n\n测量 P01 的电阻。\n\nP01 synthetic resistance: 1 to 2 ohm inclusive, engine=off. Additional audit synthetic only.\n".encode()
    )
    _, _, ctx, svc, cite = prepare(r, content)
    candidate = synthetic_step(cite)
    voltage = measurement(r, cite, candidate)
    claim = cite(
        "P01 synthetic resistance: 1 to 2 ohm inclusive, engine=off. Additional audit synthetic only."
    )
    made = spec(
        r,
        dict(evidence_id=claim["references"][0]["evidence_id"]),
        component_key="P01",
        quantity="resistance",
        unit="ohm",
    )
    resistance = made["spec"]["id"]
    assert approve(r, resistance).status_code == 200
    candidate["purpose"]["references"] += claim["references"]
    candidate["input"]["measurements"].append(
        dict(**made["spec"]["definition"], spec_id=resistance)
    )
    candidate["actions"].append(dict(**cite("测量 P01 的电阻。"), operation="measure"))
    prior = svc.validate(ctx, candidate)
    assert prior["accepted"], prior
    results = [
        compare(r, voltage, value="1.5", unit="V"),
        compare(r, resistance, value="3", unit="ohm", quantity="resistance"),
    ]
    ids = []
    with r.store.engine.begin() as c:
        for comp in results:
            ids.append(
                str(
                    c.execute(
                        observations.insert()
                        .values(
                            case_id=ctx.case_id,
                            kind="measurement",
                            payload=dict(
                                component_key="P01", checked=True, comparison_id=comp["id"]
                            ),
                            created_revision=ctx.revision,
                            actor_id=ctx.actor,
                        )
                        .returning(observations.c.id)
                    ).scalar_one()
                )
            )
    candidate["retest"] = dict(
        reason=cite("P01 测量记录冲突，需要同工况复测。"), observation_ids=ids
    )
    history = ProposalContext(
        ctx.actor, ctx.case_id, ctx.revision, history=(PriorCheck(prior["fingerprint"], "P01"),)
    )
    result = svc.validate(history, candidate)
    save(
        "unrelated-measurement-conflict",
        dict(proposal=candidate, comparisons=results, result=result),
    )
    assert not result["accepted"], result


@pytest.mark.parametrize(
    "defect",
    [
        "valid",
        "single",
        "wrong_case",
        "invalid_comparison",
        "second",
        "old_history",
        "wrong_quantity",
        "unrelated_reason",
    ],
)
def test_retest_association_and_history(indexed_rig, defect):
    from uuid import UUID

    from test_evidence_measurement import archived_case, post

    r = indexed_rig
    _, _, ctx, svc, cite = prepare(r, (FIX / "extra-synthetic.md").read_bytes())
    candidate = synthetic_step(cite)
    sid = measurement(r, cite, candidate)
    prior = svc.validate(ctx, candidate)
    assert prior["accepted"], prior
    comps = [compare(r, sid, value=v, unit="V") for v in ("1.5", "3")]
    case_id = ctx.case_id
    if defect == "wrong_case":
        case_id = UUID(archived_case(r)["id"])
    ids = []
    with r.store.engine.begin() as c:
        for comp in comps:
            ids.append(
                str(
                    c.execute(
                        observations.insert()
                        .values(
                            case_id=case_id,
                            kind="measurement",
                            payload=dict(
                                component_key="P01", checked=True, comparison_id=comp["id"]
                            ),
                            created_revision=ctx.revision,
                            actor_id=ctx.actor,
                        )
                        .returning(observations.c.id)
                    ).scalar_one()
                )
            )
    candidate["retest"] = dict(
        reason=cite("P01 测量记录冲突，需要同工况复测。"), observation_ids=ids
    )
    fp = prior["fingerprint"]
    if defect == "single":
        candidate["retest"]["observation_ids"] = ids[:1]
    elif defect == "invalid_comparison":
        assert (
            post(
                r,
                "measurement-specs/" + sid + "/review",
                dict(decision="revoked", note="synthetic revoke"),
            ).status_code
            == 200
        )
        assert approve(r, sid).status_code == 200
        assert (
            svc.gate.evidence.get_comparison(ctx.actor, UUID(comps[0]["id"]))["current_validity"][
                "valid"
            ]
            is False
        )
    elif defect == "old_history":
        fp = fp.removeprefix("v2:")
    elif defect == "wrong_quantity":
        candidate["actions"] = [dict(**cite("检查 P01 外观。"), operation="inspect")]
    elif defect == "unrelated_reason":
        candidate["retest"]["reason"] = cite("P01 是隔离台架的合成检查部件。")
    history = ProposalContext(
        ctx.actor,
        ctx.case_id,
        ctx.revision,
        history=(PriorCheck(fp, "P01", int(defect == "second")),),
    )
    result = svc.validate(history, candidate)
    save("retest-" + defect, result)
    assert result["accepted"] is (defect == "valid"), result
    if defect == "old_history":
        assert "HISTORY_UNSUPPORTED" in {i["code"] for i in result["issues"]}
