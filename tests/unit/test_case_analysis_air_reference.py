"""Narrow checks for the new document scope and explicit paid-context grant."""
import copy

import pytest

from app.domain.policies import DomainError
from app.services.case_analysis_air_reference import reference_context, authorize_context_window
from app.legacy_execution.case_analysis import model_payload

CASE = "17c8ddf4-fd43-44cc-8f2c-f922d922b8af"


def test_reference_is_case_bound_and_replaces_old_excerpts():
    context = reference_context(CASE)
    assert reference_context("another-case") is None
    assert context["document"]["sections"] == ["scope", *range(1, 12), 14, 16]
    assert len(context["excerpts"]) == 14
    assert all(item["id"].startswith("AIR-REF-1-") for item in context["excerpts"])
    assert all(item["model_read_image"] is False for item in context["image_references"])
    assert not context["editorial_cards"]


def test_new_context_grant_requires_exact_case_revision_key_and_hash():
    context = reference_context(CASE)
    snap = {"source_context": context}
    env = {"XIUTU_C19_ALLOWED_CONTEXT_HASH": context["hash"],
           "XIUTU_C05_ALLOWED_CASE_ID": CASE, "XIUTU_C05_ALLOWED_REVISION": "60",
           "XIUTU_C05_ALLOWED_KEY": "explicit-one-shot"}
    assert authorize_context_window(snap, CASE, 60, "explicit-one-shot", {}) is None
    grant = authorize_context_window(snap, CASE, 60, "explicit-one-shot", env)
    assert grant["context_hash"] == context["hash"]
    for key in env:
        changed = {**env, key: "wrong"}
        with pytest.raises(DomainError):
            authorize_context_window(snap, CASE, 60, "explicit-one-shot", changed)


def test_new_prompt_grant_is_bound_to_current_contract():
    context = reference_context(CASE)
    snap = {"source_context": context, "prompt_version": "dkvb-c19-v4",
            "output_contract_version": "case-advice-open-c19-v2"}
    env = {"XIUTU_C19_ALLOWED_CONTEXT_HASH": context["hash"],
           "XIUTU_C19_ALLOWED_PROMPT_VERSION": "dkvb-c19-v4",
           "XIUTU_C05_ALLOWED_CASE_ID": CASE, "XIUTU_C05_ALLOWED_REVISION": "60",
           "XIUTU_C05_ALLOWED_KEY": "explicit-one-shot"}
    grant = authorize_context_window(snap, CASE, 60, "explicit-one-shot", env)
    assert grant["prompt_version"] == "dkvb-c19-v4"
    assert grant["output_contract_version"] == "case-advice-open-c19-v2"
    for changed in ({**snap, "prompt_version": "dkvb-c19-v3"},
                    {**snap, "output_contract_version": "case-advice-open-c19-v1"}):
        with pytest.raises(DomainError):
            authorize_context_window(changed, CASE, 60, "explicit-one-shot", env)


def test_wire_compaction_preserves_facts_and_entire_selected_prose():
    snap = {"output_contract_version": "case-advice-open-c19-v1", "prompt_version": "dkvb-c19-v1",
            "source_context": reference_context(CASE), "synthesis": {"facts": []},
            "observations": [{"id": "fact", "question_id": "AIR-15", "question": "漏点",
                              "fields": {"location": {"value": "具体位置", "unit": None}},
                              "note": "模拟，非实测", "option_ids": ["connector"],
                              "unavailable_reason": "", "round_id": None}],
            "paid_context_grant": {"key_sha256": "not-model-data"}}
    before = copy.deepcopy(snap)
    wire = model_payload(snap)
    assert snap == before
    assert wire["observations"][0]["fields"] == snap["observations"][0]["fields"]
    assert wire["observations"][0]["option_ids"] == ["connector"]
    assert wire["shared_observation_note"] == "模拟，非实测"
    assert [s["text"] for s in wire["source_context"]["excerpts"]] == [
        s["text"] for s in snap["source_context"]["excerpts"]]
    assert "paid_context_grant" not in wire
