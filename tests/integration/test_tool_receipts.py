"""WP07 receipt v2 regressions; synthetic fixtures and real PostgreSQL services."""

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from app.infrastructure.orm import (
    chunks,
    measurement_comparisons,
    observations,
    tool_calls,
    tool_executions,
)
from app.services.evidence_scope import owner_lock
from app.tools.registry import langchain_tool
from sqlalchemy import select, text, update
from test_business_tools import application, call, record
from test_business_tools import indexed_rig as indexed_rig
from test_document_ingest import docrig as docrig
from test_document_ingest import wait
from test_evidence_measurement import (
    approve,
    archived_bind,
    archived_case,
    archived_citation,
    document,
    post,
    review,
    spec,
)

pytestmark = pytest.mark.database
save = record


def setup(r, conditions=None, timeout=10000):
    document(r)
    case = archived_case(r)
    ev = archived_bind(r, case, archived_citation(r, case))
    sid = spec(r, ev, **({"conditions": conditions} if conditions else {}))["spec"]["id"]
    assert approve(r, sid).status_code == 200
    ex, ctx = application(r, case, timeout_ms=timeout)
    return case, sid, ex, ctx


def persisted(r, ctx):
    with r.store.engine.connect() as c:
        rows = (
            c.execute(select(tool_calls).where(tool_calls.c.execution_id == ctx.execution_id))
            .mappings()
            .all()
        )
        assert ctx.cookie not in json.dumps(
            [dict(x) for x in rows], default=str
        ) and ctx.capability not in json.dumps([dict(x) for x in rows], default=str)
        used = c.execute(
            select(tool_executions.c.used).where(tool_executions.c.id == ctx.execution_id)
        ).scalar_one()
        cid = c.execute(
            select(tool_executions.c.case_id).where(tool_executions.c.id == ctx.execution_id)
        ).scalar_one()
        comps = (
            c.execute(
                select(measurement_comparisons.c.id).where(measurement_comparisons.c.case_id == cid)
            )
            .scalars()
            .all()
        )
        idem = [
            c.execute(
                text("select count(*) from idempotency_keys where key=:k"),
                {"k": "tool-" + str(x["id"])},
            ).scalar_one()
            for x in rows
        ]
        return dict(
            calls=[
                {
                    k: x[k]
                    for k in [
                        "id",
                        "status",
                        "attempts",
                        "cancel_requested",
                        "error_code",
                        "result_summary",
                    ]
                }
                for x in rows
            ],
            used=used,
            comparisons=list(map(str, comps)),
            idempotency_counts=idem,
        )


@pytest.mark.parametrize("key", ["text", "payload", "_restore_note", "_restore_text"])
def test_legal_condition_keys_replay_losslessly(indexed_rig, key):
    r = indexed_rig
    case, sid, ex, ctx = setup(r, {key: "off"})
    args = dict(spec_id=sid, value="1", unit="V", conditions={key: "off"})
    first = call(ex, ctx, "compare_measurement", args, "legal-compare")
    again = call(ex, ctx, "compare_measurement", args, "legal-compare")
    found = call(
        ex,
        ctx,
        "get_measurement_spec",
        dict(component_key="SYNTHETIC-COMPONENT", quantity="voltage"),
        "legal-spec",
    )
    found_again = call(
        ex,
        ctx,
        "get_measurement_spec",
        dict(component_key="SYNTHETIC-COMPONENT", quantity="voltage"),
        "legal-spec",
    )
    assert first["ok"] and found["ok"]
    save(
        "condition-key-" + key,
        dict(
            key=key,
            first=first,
            replay=again,
            spec=found,
            spec_replay=found_again,
            persisted=persisted(r, ctx),
        ),
    )
    assert again == first and found_again == found, (
        "Valid dynamic condition keys must round-trip unchanged"
    )


def test_marker_input_cannot_fetch_other_owner_chunk(indexed_rig):
    r = indexed_rig
    case, sid, ex, ctx = setup(r)
    other, headers, actor = r.api()
    foreign = r.upload(
        b"# Synthetic foreign owner\n\nAUDIT-PRIVATE-CORPUS-CONTENT-NOT-REAL.\n",
        client=other,
        headers=headers,
    ).json()
    p, _ = r.worker(foreign)
    assert p.wait(timeout=20) == 0
    assert r.client.get(r.path(foreign)).status_code == 404
    with r.store.engine.connect() as c:
        chunk = (
            c.execute(
                select(chunks).where(chunks.c.document_version_id == UUID(foreign["version_id"]))
            )
            .mappings()
            .first()
        )
    denied = call(
        ex,
        ctx,
        "get_evidence_context",
        dict(chunk_id=str(chunk["id"]), document_version_id=foreign["version_id"]),
    )
    assert not denied["ok"]
    args = dict(
        spec_id=sid,
        value="1",
        unit="V",
        conditions={
            "engine": "off",
            "_restore_text": "true",
            "chunk_id": str(chunk["id"]),
            "document_version_id": foreign["version_id"],
            "content_hash": chunk["text_hash"],
        },
    )
    first = call(ex, ctx, "compare_measurement", args, "crafted-replay")
    again = call(ex, ctx, "compare_measurement", args, "crafted-replay")
    leaked = (
        again.get("data", {}).get("input", {}).get("conditions", {}).get("text") == chunk["text"]
    )
    save(
        "marker-cross-owner",
        dict(
            foreign_owner=str(actor),
            authorized_owner=str(r.actor),
            ordinary_context=denied,
            first=first,
            replay=again,
            foreign_text_in_replay=leaked,
            persisted=persisted(r, ctx),
        ),
    )
    assert first["ok"]
    assert not leaked, (
        "Replay must never resolve model-supplied restoration markers into foreign chunks"
    )


def test_revoked_then_approved_comparison_keeps_review_requirement(indexed_rig):
    r = indexed_rig
    case, sid, ex, ctx = setup(r)
    args = dict(spec_id=sid, value="1", unit="V", conditions={"engine": "off"})
    first = call(ex, ctx, "compare_measurement", args, "history")
    assert first["ok"]
    assert (
        post(
            r,
            "measurement-specs/" + sid + "/review",
            dict(decision="revoked", note="Synthetic audit revocation"),
        ).status_code
        == 200
    )
    refused = call(ex, ctx, "compare_measurement", args, "history")
    assert not refused["ok"]
    assert approve(r, sid).status_code == 200
    view = r.client.get("/api/v2/measurement-comparisons/" + first["data"]["comparison_id"])
    assert view.status_code == 200
    replay = call(ex, ctx, "compare_measurement", args, "history")
    fresh = call(ex, ctx, "compare_measurement", args, "fresh-after-review")
    assert fresh["ok"]
    save(
        "comparison-review-history",
        dict(first=first, revoked=refused, current_http=view.json(), replay=replay, fresh=fresh),
    )
    assert replay["error"]["code"] == "COMPARISON_INVALID"
    after = persisted(r, ctx)
    assert after["used"] == 2 and len(after["comparisons"]) == 2
    assert after["idempotency_counts"] == [1, 1]
    assert all(x["attempts"] == 1 for x in after["calls"])
    save("comparison-review-counts", after)
    assert not view.json()["current_validity"]["valid"]
    assert not replay["ok"] or replay["data"].get("current_validity", {}).get("valid") is False, (
        "Old comparison needing review must not be exposed as currently authorized success"
    )


def test_combined_nested_business_keys_and_five_replays(indexed_rig):
    r = indexed_rig
    conditions = {"text": "off", "payload": "off", "_restore_note": "off", "_restore_text": "true"}
    case, sid, ex, ctx = setup(r, conditions)
    quote = archived_citation(r, case)
    area = uuid4()
    payload = {
        "text": "SYNTHETIC opaque observation",
        "payload": {
            "_restore_text": True,
            "text": "nested",
            "payload": [conditions, {"_restore_note": "keep"}],
        },
        "_restore_text": True,
        "chunk_id": quote["chunk_id"],
        "document_version_id": quote["document_version_id"],
    }
    with r.store.engine.begin() as c:
        c.execute(
            observations.insert().values(
                case_id=UUID(case["id"]),
                actor_id=r.actor,
                area_id=area,
                kind="unavailable",
                created_revision=0,
                payload=payload,
            )
        )
    requests = [
        ("search_manuals", dict(query="voltage")),
        (
            "get_evidence_context",
            dict(
                chunk_id=quote["chunk_id"],
                document_version_id=quote["document_version_id"],
                neighbors=2,
            ),
        ),
        ("get_measurement_spec", dict(component_key="SYNTHETIC-COMPONENT", quantity="voltage")),
        ("compare_measurement", dict(spec_id=sid, value="1", unit="V", conditions=conditions)),
        ("get_case_observations", dict(at_revision=0, area_id=str(area))),
    ]
    answers = {}
    for name, args in requests:
        first = call(ex, ctx, name, args, name)
        assert first["ok"], first
        assert call(ex, ctx, name, args, name) == first
        sdk = langchain_tool(ex, ctx, name, name)
        msg = sdk.invoke(dict(type="tool_call", name=name, args=args, id="synthetic-call"))
        assert msg.tool_call_id == "synthetic-call" and json.loads(msg.content) == first
        answers[name] = first
    assert answers["get_case_observations"]["data"]["observations"][0]["payload"] == payload
    assert answers["compare_measurement"]["data"]["input"]["conditions"] == conditions
    assert (
        answers["get_measurement_spec"]["data"]["candidates"][0]["definition"]["conditions"]
        == conditions
    )
    before = persisted(r, ctx)
    assert (
        before["used"] == 5
        and len(before["comparisons"]) == 1
        and sum(before["idempotency_counts"]) == 1
    )
    raw = json.dumps(before["calls"], default=str)
    assert "SYNTHETIC opaque observation" not in raw and "SYNTHETIC ONLY: voltage" not in raw
    assert all(x["result_summary"]["receipt_version"] == 2 for x in before["calls"])
    assert all(x["attempts"] == 1 for x in before["calls"])
    # Replay after active index switch keeps original authorized frozen index.
    from test_indexes import reindex

    with r.store.engine.connect() as c:
        from app.infrastructure.orm import document_versions

        version = (
            c.execute(
                select(document_versions).where(
                    document_versions.c.id == UUID(quote["document_version_id"])
                )
            )
            .mappings()
            .one()
        )
    body = dict(document_id=str(version["document_id"]), version_id=str(version["id"]))
    rebuilt = reindex(r, body).json()
    worker, _ = r.worker(dict(body, run_id=rebuilt["run_id"]), lease=10)
    assert worker.wait(timeout=30) == 0
    assert call(ex, ctx, *requests[0], "search_manuals") == answers["search_manuals"]
    assert quote["index_id"] != rebuilt["index_id"]
    # Source revocation blocks both first use and saved replay.
    review(r, body, "revoked")
    for key in ("search_manuals", "new-after-revoke"):
        assert call(ex, ctx, *requests[0], key)["error"]["code"] == "SOURCE_INVALID"
    ctx.auth.revoke(ctx.cookie)
    assert call(ex, ctx, *requests[4], "get_case_observations")["error"]["code"] == "UNAUTHORIZED"
    assert persisted(r, ctx) == before
    save(
        "v2-five-replay",
        dict(
            results=answers,
            used=5,
            comparison_count=1,
            frozen_index=True,
            revoked_and_logout_denied=True,
        ),
    )


def test_old_receipt_refused_without_repeat_or_budget(indexed_rig):
    r = indexed_rig
    case, sid, ex, ctx = setup(r)
    args = dict(
        spec_id=sid, value="1", unit="V", conditions={"engine": "off", "_restore_text": "true"}
    )
    first = call(ex, ctx, "compare_measurement", args, "old")
    assert first["ok"]
    before = persisted(r, ctx)
    # Unversioned v1 is deliberately not upgraded or recursively interpreted.
    with r.store.engine.begin() as c:
        c.execute(
            update(tool_calls)
            .where(tool_calls.c.execution_id == ctx.execution_id)
            .values(result_summary=first)
        )
    results = [call(ex, ctx, "compare_measurement", args, "old") for _ in range(2)]
    assert all(x["error"]["code"] == "RECEIPT_UNSUPPORTED" for x in results)
    after = persisted(r, ctx)
    assert after["used"] == before["used"] == 1 and after["comparisons"] == before["comparisons"]
    assert after["idempotency_counts"] == [1] and after["calls"][0]["attempts"] == 1
    assert (
        after["calls"][0]["result_summary"] == first and after["calls"][0]["status"] == "succeeded"
    )
    assert (
        r.client.get(
            "/api/v2/measurement-comparisons/" + first["data"]["comparison_id"]
        ).status_code
        == 200
    )
    save("legacy-receipt", dict(results=results, persisted=after))


@pytest.mark.parametrize("change", ["comparison_id", "spec_id", "input"])
def test_comparison_receipt_must_match_original_call(indexed_rig, change):
    r = indexed_rig
    case, sid, ex, ctx = setup(r)
    args = dict(spec_id=sid, value="1", unit="V", conditions={"engine": "off"})
    first = call(ex, ctx, "compare_measurement", args, "original")
    second = call(ex, ctx, "compare_measurement", dict(args, value="2"), "other")
    assert first["ok"] and second["ok"]
    with r.store.engine.begin() as c:
        row = (
            c.execute(
                select(tool_calls).where(
                    tool_calls.c.execution_id == ctx.execution_id,
                    tool_calls.c.call_key == "original",
                )
            )
            .mappings()
            .one()
        )
        receipt = deepcopy(row["result_summary"])
        if change == "comparison_id":
            receipt["answer"]["data"] = deepcopy(second["data"])
        elif change == "spec_id":
            receipt["answer"]["data"]["spec_id"] = str(uuid4())
        else:
            receipt["answer"]["data"]["input"]["conditions"]["text"] = "tampered"
        c.execute(
            update(tool_calls).where(tool_calls.c.id == row["id"]).values(result_summary=receipt)
        )
    result = call(ex, ctx, "compare_measurement", args, "original")
    assert result["error"]["code"] == "SOURCE_INVALID"
    after = persisted(r, ctx)
    assert (
        after["used"] == 2
        and len(after["comparisons"]) == 2
        and after["idempotency_counts"] == [1, 1]
    )
    save("comparison-association-" + change, dict(result=result, used=after["used"]))


@pytest.mark.parametrize("mismatch", ["area", "revision", "case"])
def test_observation_restore_rechecks_original_request(indexed_rig, mismatch):
    r = indexed_rig
    case = archived_case(r)
    other = archived_case(r)
    area = uuid4()
    target = uuid4()
    from app.infrastructure.orm import cases

    with r.store.engine.begin() as c:
        c.execute(update(cases).where(cases.c.id == UUID(case["id"])).values(revision=2))
        for oid, cid, ar, rev in [
            (uuid4(), case["id"], area, 0),
            (
                target,
                other["id"] if mismatch == "case" else case["id"],
                uuid4() if mismatch == "area" else area,
                2 if mismatch == "revision" else 0,
            ),
        ]:
            c.execute(
                observations.insert().values(
                    id=oid,
                    case_id=UUID(cid),
                    actor_id=r.actor,
                    area_id=ar,
                    kind="unavailable",
                    created_revision=rev,
                    payload={"text": "synthetic-private-observation"},
                )
            )
    ex, ctx = application(r, case)
    args = dict(at_revision=0, area_id=str(area))
    first = call(ex, ctx, "get_case_observations", args, "obs")
    assert first["ok"]
    with r.store.engine.begin() as c:
        row = (
            c.execute(select(tool_calls).where(tool_calls.c.execution_id == ctx.execution_id))
            .mappings()
            .one()
        )
        receipt = deepcopy(row["result_summary"])
        receipt["answer"]["data"]["observations"][0]["id"] = str(target)
        c.execute(
            update(tool_calls).where(tool_calls.c.id == row["id"]).values(result_summary=receipt)
        )
    replay = call(ex, ctx, "get_case_observations", args, "obs")
    assert replay["error"][
        "code"
    ] == "SOURCE_INVALID" and "synthetic-private-observation" not in json.dumps(replay)
    assert persisted(r, ctx)["used"] == 1
    save("observation-scope-" + mismatch, replay)


def test_concurrent_success_replay_consumes_nothing(indexed_rig):
    r = indexed_rig
    case, sid, ex, ctx = setup(r)
    args = dict(spec_id=sid, value="1", unit="V", conditions={"engine": "off", "text": "keep"})
    first = call(ex, ctx, "compare_measurement", args, "replay")
    assert first["ok"]
    before = persisted(r, ctx)
    blocker = r.store.engine.connect()
    tx = blocker.begin()
    owner_lock(blocker, r.actor)
    pid = blocker.execute(text("select pg_backend_pid()")).scalar_one()
    try:
        with ThreadPoolExecutor(2) as pool:
            futures = [
                pool.submit(call, ex, ctx, "compare_measurement", args, "replay") for _ in range(2)
            ]

            def waiting():
                with r.store.engine.connect() as c:
                    rows = (
                        c.execute(
                            text(
                                "select pid,wait_event,clock_timestamp() as at from pg_stat_activity where :p=ANY(pg_blocking_pids(pid))"
                            ),
                            {"p": pid},
                        )
                        .mappings()
                        .all()
                    )
                    return [dict(x) for x in rows] if len(rows) == 2 else None

            try:
                observed = wait(waiting, seconds=5)
            finally:
                tx.commit()
            answers = [f.result(timeout=10) for f in futures]
        assert answers == [first, first] and persisted(r, ctx) == before
        save(
            "concurrent-replay",
            dict(
                waits=observed,
                comparison_count=1,
                used=before["used"],
                idempotency=before["idempotency_counts"],
            ),
        )
    finally:
        if tx.is_active:
            tx.rollback()
        blocker.close()


def test_saved_chunk_reference_is_not_authority(indexed_rig):
    r = indexed_rig
    case, sid, ex, ctx = setup(r)
    quote = archived_citation(r, case)
    args = dict(chunk_id=quote["chunk_id"], document_version_id=quote["document_version_id"])
    first = call(ex, ctx, "get_evidence_context", args, "context")
    assert first["ok"]
    other, headers, _ = r.api()
    foreign = r.upload(
        b"# Synthetic owner B\n\nDO-NOT-RESTORE-FOREIGN-TEXT", client=other, headers=headers
    ).json()
    p, _ = r.worker(foreign)
    assert p.wait(timeout=20) == 0
    with r.store.engine.begin() as c:
        chunk = (
            c.execute(
                select(chunks).where(chunks.c.document_version_id == UUID(foreign["version_id"]))
            )
            .mappings()
            .first()
        )
        row = (
            c.execute(select(tool_calls).where(tool_calls.c.execution_id == ctx.execution_id))
            .mappings()
            .one()
        )
        receipt = deepcopy(row["result_summary"])
        ref = receipt["answer"]["data"]["chunks"][0]
        ref.update(
            chunk_id=str(chunk["id"]),
            document_version_id=foreign["version_id"],
            content_hash=chunk["text_hash"],
            locator=chunk["locator_json"],
        )
        c.execute(
            update(tool_calls).where(tool_calls.c.id == row["id"]).values(result_summary=receipt)
        )
    replay = call(ex, ctx, "get_evidence_context", args, "context")
    assert replay["error"]["code"] == "CORPUS_NOT_ALLOWED" and "DO-NOT-RESTORE" not in json.dumps(
        replay
    )
    assert persisted(r, ctx)["used"] == 1
    save("saved-chunk-authorization", replay)


@pytest.mark.parametrize(
    "fault,expected", [("schema", "OUTPUT_INVALID"), ("size", "RESULT_TOO_LARGE")]
)
def test_replay_validates_output_and_envelope_size(indexed_rig, fault, expected):
    r = indexed_rig
    case = archived_case(r)
    ex, ctx = application(r, case)
    args = dict(at_revision=0)
    first = call(ex, ctx, "get_case_observations", args, "empty")
    assert first["ok"]
    with r.store.engine.begin() as c:
        row = (
            c.execute(select(tool_calls).where(tool_calls.c.execution_id == ctx.execution_id))
            .mappings()
            .one()
        )
        receipt = deepcopy(row["result_summary"])
        if fault == "schema":
            receipt["answer"]["data"]["unexpected"] = "synthetic"
        else:
            receipt["answer"]["provenance"] = [{"synthetic": "x" * 65536}]
        c.execute(
            update(tool_calls).where(tool_calls.c.id == row["id"]).values(result_summary=receipt)
        )
    replay = call(ex, ctx, "get_case_observations", args, "empty")
    assert replay["error"]["code"] == expected
    assert persisted(r, ctx)["used"] == 1
    save("replay-limit-" + fault, dict(code=replay["error"]["code"], budget_unchanged=True))
