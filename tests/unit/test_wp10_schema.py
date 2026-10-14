import json
from uuid import uuid4

import pytest
from app.legacy_execution.proposer import ProposalRunner
from app.agents.state import ProposalEnvelope, ProposalTurn, ProposeStep
from app.validators.repetition import action_semantics, fingerprint
from app.validators.support import ExtractiveSupport, ModelSupport, has_numeric_standard
from pydantic import ValidationError
from test_wp09_contracts import rig


def claim(text="检查 P01 外观"):
    return dict(
        text=text, references=[dict(evidence_id=str(uuid4()), document_version_id=str(uuid4()))]
    )


def step():
    return dict(
        type="propose_step",
        component_key="P01",
        title="检查外观",
        purpose=claim(),
        location=claim("P01 左侧"),
        prerequisites=[claim("冷车")],
        actions=[dict(**claim(), operation="inspect")],
        input=dict(kind="choice", choices=[claim("未见渗漏")]),
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"owner": "forged"},
        {"status": "completed"},
        {"id": str(uuid4())},
        {"profile": "synthetic"},
        {"next_node": "fixed"},
    ],
)
def test_model_cannot_set_identity(extra):
    with pytest.raises(ValidationError):
        ProposalEnvelope.model_validate(dict(step(), **extra))


def test_nested_schema_and_nonphysical_unit():
    s = step()
    s["input"]["choices"][0]["next_node"] = "fixed"
    with pytest.raises(ValidationError):
        ProposalEnvelope.model_validate(s)
    s = step()
    s["input"] = dict(
        kind="measurement",
        measurements=[
            dict(
                spec_id=str(uuid4()),
                evidence_id=str(uuid4()),
                component_key="P01",
                quantity="voltage",
                unit="Ux",
                lower="1",
                upper="2",
                conditions={"engine": "off"},
            )
        ],
    )
    with pytest.raises(ValidationError):
        ProposalEnvelope.model_validate(s)


@pytest.mark.parametrize(
    "type_", ["request_tools", "propose_areas", "propose_step", "conclude_area", "need_input"]
)
def test_union(type_):
    bodies = {
        "request_tools": dict(calls=[dict(name="search_manuals", arguments={"query": "冷却"})]),
        "propose_areas": dict(areas=[dict(component_key="P01", title="P01", rationale=claim())]),
        "propose_step": {k: v for k, v in step().items() if k != "type"},
        "conclude_area": dict(component_key="P01", finding=claim(), assessment="not_checked"),
        "need_input": dict(missing=["缺少正式规格"]),
    }
    assert ProposalEnvelope.model_validate(dict(type=type_, **bodies[type_])).root.type == type_


def test_areas_not_fixed_and_depth_bound():
    body = dict(
        type="propose_areas", areas=[dict(component_key="P01", title="水泵", rationale=claim())]
    )
    assert len(ProposalEnvelope.model_validate(body).root.areas) == 1
    body["areas"] *= 9
    with pytest.raises(ValidationError):
        ProposalEnvelope.model_validate(body)


def test_support_not_quote_existence_or_substring():
    check = ExtractiveSupport()
    assert (
        check.assess("P01 尚未检查，不能排除", ["P01 尚未检查，不能排除"])["verdict"] == "supported"
    )
    assert check.assess("不能排除", ["P01 尚未检查，不能排除"])["verdict"] == "uncertain"
    assert check.assess("P01 正常", ["P01 尚未检查，不能排除"])["verdict"] == "uncertain"


@pytest.mark.parametrize(
    "title,action", [("新标题", "检查 P01 外观"), ("另一个说法", "查看 P01 外观")]
)
def test_semantic_fingerprint_ignores_title(title, action):
    a = ProposeStep.model_validate(step())
    b = a.model_copy(deep=True)
    b.title = title
    b.actions[0].text = action
    assert fingerprint(a) == fingerprint(b)
    assert action_semantics(b.actions[0]) == "inspect"
    b.actions[0].operation = "measure"
    assert action_semantics(b.actions[0]) is None


@pytest.mark.parametrize("text", ["标准 12 V", "扭矩 10 Nm", "虚构 10 Ux", "阈值 12（单位未定义）"])
def test_numeric_prose_needs_spec(text):
    assert has_numeric_standard(text)


class Rejecting:
    def validate(self, context, raw):
        return dict(
            accepted=False,
            disposition="needs_input",
            issues=[dict(code="CLAIM_UNSUPPORTED", path="action", detail="no source")],
            published=False,
        )


@pytest.mark.parametrize("mode", ["success", "invalid", "business", "budget"])
def test_single_shared_repair_and_budget(tmp_path, mode):
    good = json.dumps(dict(type="need_input", missing=["缺少工况"]))
    answers = [
        dict(role="assistant", content="invalid"),
        dict(role="assistant", content=good if mode == "success" else "invalid"),
    ]
    if mode == "business":
        answers = [dict(role="assistant", content=good)] * 2
    g, ledger, seen = rig(tmp_path, answers)

    class Service:
        def validate(self, c, raw):
            return dict(accepted=True, disposition="needs_input", issues=[], published=False)

    turn = ProposalTurn()
    runner = ProposalRunner(g, Rejecting() if mode == "business" else Service())
    if mode == "budget":
        g.calls = 5
    try:
        result = runner.run(object(), [], turn)
        assert result["disposition"] == "needs_input" and not result["published"]
        assert len(seen) == (0 if mode == "budget" else 2)
        if mode != "budget":
            assert turn.repair_used and turn.attempts == 2
        if mode in ("invalid", "business"):
            assert not result["accepted"]
        if mode != "budget":
            exhausted = runner.run(object(), [], turn)
            assert exhausted["issues"][0]["code"] == "REPAIR_EXHAUSTED" and len(seen) == 2
    finally:
        g.close()


def test_model_support_uses_actual_sdk_and_quote_guard(tmp_path):
    g, ledger, seen = rig(
        tmp_path,
        [
            dict(
                role="assistant",
                content=json.dumps(dict(verdict="supported", quote="invented", reason="claimed")),
            )
        ],
    )
    try:
        assert ModelSupport(g).assess("P01正常", ["P01未知"])["verdict"] == "uncertain"
        assert len(seen) == 1
    finally:
        g.close()


@pytest.mark.parametrize(
    "text,quote,allowed",
    [
        ("不能认定P01正常。", "P01正常。", False),
        ("不能认定\nP01正常。", "P01正常。", False),
        ("P01正常，但必须先检查。", "P01正常", False),
        ("P01尚未检查。\n\n下一段", "P01尚未检查。", True),
        ("| P01 | 未检查 |\n| H01 | 未检查 |", "| P01 | 未检查 |", True),
        ("完整段落\n包括条件。", "完整段落\n包括条件。", True),
    ],
)
def test_complete_source_context(text, quote, allowed):
    from app.validators.support import has_complete_context

    start = text.index(quote)
    assert has_complete_context(text, start, start + len(quote)) is allowed


def test_next_step_prompt_used_without_paid_call(tmp_path):
    from types import SimpleNamespace

    g, _, seen = rig(
        tmp_path,
        [dict(role="assistant", content=json.dumps(dict(type="need_input", missing=["缺项"])))],
    )

    class Service:
        def validate(self, c, raw):
            return dict(accepted=True, disposition="needs_input", issues=[], published=False)

    try:
        ProposalRunner(g, Service()).run(SimpleNamespace(history=(object(),)), [], ProposalTurn())
        assert "Changing a title" in seen[0]["messages"][0]["content"]
    finally:
        g.close()
