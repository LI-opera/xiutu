"""WP10 synthetic HTTP/PG harness; no paid model. No production observation writer."""

import copy
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from app.agents.state import PriorCheck, ProposalContext
from app.config import Settings
from app.infrastructure.orm import cases, chunks, observations
from app.services.proposal_service import ProposalService
from app.validators.support import ExtractiveSupport
from sqlalchemy import select, update
from test_document_ingest import docrig as docrig
from test_evidence_measurement import (
    approve,
    archived_bind,
    archived_case,
    compare,
    post,
    review,
    spec,
)
from test_evidence_measurement import indexed_rig as indexed_rig

pytestmark = pytest.mark.database
ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests/fixtures/wp10"


def record(name, data):
    if os.environ.get("WP10_EVIDENCE"):
        (Path(os.environ["WP10_EVIDENCE"]) / (name + "-" + uuid4().hex[:8] + ".json")).write_text(
            json.dumps(data, ensure_ascii=False, default=str, indent=2), encoding="utf-8"
        )


def prepare(r, content):
    body = r.upload(content).json()
    r.complete(body)
    response = review(r, body)
    assert response.status_code == 202, response.text
    proc, _ = r.worker(dict(body, run_id=response.json()["index_run_id"]), lease=30)
    assert proc.wait(timeout=60) == 0
    assert not r.state(body)["formal_usable"]
    case = archived_case(r)
    ctx = ProposalContext(
        r.actor, UUID(case["id"]), case["revision"], frozenset(["search_manuals"])
    )
    svc = ProposalService(
        r.store.engine,
        Settings(
            app_mode="test",
            retrieval_profile="synthetic",
            database_url=r.env["DATABASE_URL"],
        ),
    )

    def cite(text):
        with r.store.engine.connect() as c:
            rows = (
                c.execute(
                    select(chunks).where(chunks.c.document_version_id == UUID(body["version_id"]))
                )
                .mappings()
                .all()
            )
        row = next(x for x in rows if text in x["text"])
        start = row["text"].index(text)
        ev = archived_bind(
            r,
            case,
            dict(
                chunk_id=str(row["id"]),
                document_version_id=body["version_id"],
                index_id=r.state(body)["active_index_id"],
                quote=text,
                start=start,
                end=start + len(text),
            ),
        )
        return dict(
            text=text,
            references=[
                dict(evidence_id=ev["evidence_id"], document_version_id=body["version_id"])
            ],
        )

    return body, case, ctx, svc, cite


def test_demo_user_source(indexed_rig):
    r = indexed_rig
    src = (FIX / "cooling-synthetic.md").read_bytes()
    manifest = json.loads((FIX / "source.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(src).hexdigest() == manifest["sha256"] and manifest["synthetic"]
    body, case, ctx, svc, cite = prepare(r, src)
    line = next(x for x in src.decode().splitlines() if x.startswith("| P01 电动水泵 |"))
    grounded = cite(line)
    areas = dict(
        type="propose_areas",
        areas=[dict(component_key="P01", title="水泵物理区域", rationale=grounded)],
    )
    valid = svc.validate(ctx, areas)
    assert valid["accepted"] and len(valid["candidate"]["areas"]) == 1
    missing = dict(
        type="propose_step",
        component_key="P01",
        title="待补检查",
        purpose=grounded,
        input=dict(kind="measurement"),
    )
    gaps = svc.validate(ctx, missing)
    assert not gaps["accepted"]
    assert {"LOCATION_MISSING", "CONDITIONS_MISSING", "SPEC_REQUIRED"} <= {
        x["code"] for x in gaps["issues"]
    }
    wrong = copy.deepcopy(areas)
    wrong["areas"][0]["rationale"]["text"] = "P01 应立即更换且已排除其他部件"
    unsupported = svc.validate(ctx, wrong)
    assert not unsupported["accepted"] and any(
        x["code"] == "CLAIM_UNCERTAIN" for x in unsupported["issues"]
    )
    conclude = dict(
        type="conclude_area",
        component_key="P01",
        finding=grounded,
        assessment="temporarily_excluded",
    )
    untested = svc.validate(ctx, conclude)
    assert any(x["code"] == "NOT_CHECKED" for x in untested["issues"])
    print("SYNTHETIC ONLY: source fragment:", line)
    for label, value in [
        ("one-grounded-area", valid),
        ("missing-real-conditions-and-spec", gaps),
        ("unrelated-claim", unsupported),
        ("not-checked-not-excluded", untested),
    ]:
        print(label, json.dumps(value, ensure_ascii=False))
        record("demo-" + label, value)
    # Formal service cannot reuse a synthetic manifest even though all identifiers exist.
    formal = ProposalService(
        r.store.engine, Settings(app_mode="test", retrieval_profile="formal")
    ).validate(ctx, areas)
    assert not formal["accepted"]
    record("formal-refusal", formal)


def synthetic_step(cite):
    return dict(
        type="propose_step",
        component_key="P01",
        title="台架观察",
        purpose=cite("P01 是隔离台架的合成检查部件。"),
        location=cite("P01 位于隔离台架左侧。"),
        prerequisites=[cite("发动机关闭，engine=off。")],
        actions=[dict(**cite("检查 P01 外观。"), operation="inspect")],
        input=dict(kind="choice", choices=[cite("P01 未检查时不得排除。")]),
    )


def test_dkvb_guided_demo_step_is_bounded_and_source_backed(indexed_rig):
    content = (ROOT / "tests/fixtures/diagnosis-slice/dkvb-guided.md").read_bytes()
    _, _, ctx, svc, cite = prepare(indexed_rig, content)
    component = "增压空气系统"
    candidate = dict(
        type="propose_step",
        component_key=component,
        title="检查增压空气系统是否存在可定位漏点（DEMO）",
        purpose=cite(
            "增压空气系统局部泄漏检查用于确认有无可定位漏点，而不是用整个系统压降推断泄漏。"
        ),
        location=cite("增压空气系统位置见 S02-P1/P2 装配图。"),
        prerequisites=[cite("演示操作只填写已给出的模拟结果，不操作真实气源。")],
        actions=[dict(**cite("检查 增压空气系统 的局部泄漏。"), operation="inspect")],
        input=dict(
            kind="choice",
            choices=[
                cite("增压空气系统已定位局部泄漏。"),
                cite("增压空气系统未发现局部泄漏。"),
                cite("增压空气系统局部泄漏结果无法确定。"),
            ],
        ),
    )
    accepted = svc.validate(ctx, candidate)
    assert accepted["accepted"], accepted

    unsupported = copy.deepcopy(candidate)
    unsupported["location"]["text"] = "增压空气系统靠近发动机。"
    rejected = svc.validate(ctx, unsupported)
    assert not rejected["accepted"]
    # Hard field-role rejection happens before the slower support assessor.
    assert "LOCATION_UNCERTAIN" in {item["code"] for item in rejected["issues"]}


def test_hard_source_support_and_repetition(indexed_rig):
    r = indexed_rig
    body, case, ctx, svc, cite = prepare(r, (FIX / "extra-synthetic.md").read_bytes())
    candidate = synthetic_step(cite)
    good = svc.validate(ctx, candidate)
    assert good["accepted"], good
    samples = []
    for field in ["location", "prerequisites", "actions"]:
        bad = copy.deepcopy(candidate)
        bad[field] = None if field == "location" else []
        result = svc.validate(ctx, bad)
        assert not result["accepted"]
        samples.append(result)
    for defect in [
        "invented",
        "version",
        "owner",
        "case",
        "revision",
        "unsupported",
        "uncertain",
        "numeric",
        "malformed_support",
        "measurement_without_spec",
    ]:
        bad = copy.deepcopy(candidate)
        context = ctx
        service = svc
        if defect == "invented":
            bad["purpose"]["references"][0]["evidence_id"] = str(uuid4())
        elif defect == "version":
            bad["purpose"]["references"][0]["document_version_id"] = str(uuid4())
        elif defect == "owner":
            context = ProposalContext(uuid4(), ctx.case_id, ctx.revision)
        elif defect == "case":
            context = ProposalContext(ctx.actor, UUID(archived_case(r)["id"]), ctx.revision)
        elif defect == "revision":
            context = ProposalContext(ctx.actor, ctx.case_id, ctx.revision + 1)
        elif defect == "measurement_without_spec":
            bad["actions"] = [dict(**cite("测量 P01 的电压。"), operation="measure")]
        elif defect == "numeric":
            bad["actions"][0]["text"] = "检查 P01 的标准 99 V"
        else:

            class Judge:
                def assess(self, claim, quotes):
                    return dict(
                        verdict=defect, quote="", reason="Deterministic test of rejection branch"
                    )

            service = ProposalService(r.store.engine, svc.settings, Judge())
        result = service.validate(context, bad)
        assert not result["accepted"], (defect, result)
        samples.append(dict(defect=defect, result=result))
    history = ProposalContext(
        ctx.actor, ctx.case_id, ctx.revision, history=(PriorCheck(good["fingerprint"], "P01"),)
    )
    renamed = copy.deepcopy(candidate)
    renamed["title"] = "仅换标题"
    duplicate = svc.validate(history, renamed)
    assert any(x["code"] == "DUPLICATE_CHECK" for x in duplicate["issues"])
    for tool in [
        dict(name="compare_measurement", arguments={}),
        dict(name="search_manuals", arguments={"query": "x", "owner": "forged"}),
    ]:
        assert not svc.validate(ctx, dict(type="request_tools", calls=[tool]))["accepted"]
    assert svc.validate(
        ctx,
        dict(type="request_tools", calls=[dict(name="search_manuals", arguments={"query": "x"})]),
    )["accepted"]

    # Source revocation during support must be caught by final revalidation.
    class Revoke:
        done = False

        def assess(self, claim, quotes):
            if not self.done:
                self.done = True
                assert review(r, body, "revoked").status_code == 200
            return ExtractiveSupport().assess(claim, quotes)

    late = ProposalService(r.store.engine, svc.settings, Revoke()).validate(ctx, candidate)
    assert not late["accepted"] and any(x["code"] == "SOURCE_INVALID" for x in late["issues"])
    record("hard-gates", dict(samples=samples, duplicate=duplicate, revoked_during_support=late))


def test_spec_hard_numbers_retest_and_scope(indexed_rig):
    r = indexed_rig
    body, case, ctx, svc, cite = prepare(r, (FIX / "extra-synthetic.md").read_bytes())
    candidate = synthetic_step(cite)
    standard = next(
        x
        for x in (FIX / "extra-synthetic.md").read_text(encoding="utf-8").splitlines()
        if x.startswith("P01 synthetic standard")
    )
    std = cite(standard)
    eid = std["references"][0]["evidence_id"]
    made = spec(r, {"evidence_id": eid}, component_key="P01")
    sid = made["spec"]["id"]
    definition = made["spec"]["definition"]
    candidate["purpose"]["references"] += std["references"]
    candidate["actions"] = [dict(**cite("测量 P01 的电压。"), operation="measure")]
    candidate["input"] = dict(kind="measurement", measurements=[dict(**definition, spec_id=sid)])
    assert not svc.validate(ctx, candidate)["accepted"]
    assert approve(r, sid).status_code == 200
    good = svc.validate(ctx, candidate)
    assert good["accepted"], good
    badresults = []
    for field, value in [
        ("lower", "1.1"),
        ("upper", "3"),
        ("unit", "mV"),
        ("conditions", {"engine": "on"}),
        ("quantity", "pressure"),
    ]:
        bad = copy.deepcopy(candidate)
        bad["input"]["measurements"][0][field] = value
        result = svc.validate(ctx, bad)
        assert not result["accepted"]
        badresults.append(result)
    comparison_ids = [compare(r, sid, value=value, unit="V")["id"] for value in ["1.5", "3"]]
    obsids = []
    with r.store.engine.begin() as c:
        for identifier in comparison_ids:
            oid = c.execute(
                observations.insert()
                .values(
                    case_id=ctx.case_id,
                    kind="measurement",
                    payload=dict(component_key="P01", checked=True, comparison_id=identifier),
                    created_revision=ctx.revision,
                    actor_id=ctx.actor,
                )
                .returning(observations.c.id)
            ).scalar_one()
            obsids.append(oid)
    exclusion = svc.validate(
        ctx,
        dict(
            type="conclude_area",
            component_key="P01",
            finding=cite("P01 未检查时不得排除。"),
            assessment="temporarily_excluded",
            observation_ids=[str(obsids[0])],
        ),
    )
    assert any(x["code"] == "EXCLUSION_CONFLICT" for x in exclusion["issues"])
    context = ProposalContext(
        ctx.actor, ctx.case_id, ctx.revision, history=(PriorCheck(good["fingerprint"], "P01"),)
    )
    retest = copy.deepcopy(candidate)
    retest["retest"] = dict(
        reason=cite("P01 测量记录冲突，需要同工况复测。"), observation_ids=[str(x) for x in obsids]
    )
    result = svc.validate(context, retest)
    assert result["accepted"], result
    twice = ProposalContext(
        ctx.actor, ctx.case_id, ctx.revision, history=(PriorCheck(good["fingerprint"], "P01", 1),)
    )
    assert not svc.validate(twice, retest)["accepted"]
    one = copy.deepcopy(retest)
    one["retest"]["observation_ids"] = one["retest"]["observation_ids"][:1]
    assert not svc.validate(context, one)["accepted"]
    assert (
        post(
            r,
            "measurement-specs/" + sid + "/review",
            dict(decision="revoked", note="Synthetic revoke"),
        ).status_code
        == 200
    )
    assert not svc.validate(ctx, candidate)["accepted"]
    # Current mismatching vehicle must fail, even with an old frozen manifest.
    with r.store.engine.begin() as c:
        c.execute(
            update(cases).where(cases.c.id == ctx.case_id).values(vehicle_json={"model": "OTHER"})
        )
    mismatch = svc.validate(ctx, candidate)
    assert not mismatch["accepted"]
    record(
        "spec-and-retest",
        dict(
            spec=sid, bad_values=badresults, retest=result, mismatch=mismatch, synthetic_only=True
        ),
    )
