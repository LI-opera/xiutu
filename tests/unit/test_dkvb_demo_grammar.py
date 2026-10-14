from types import SimpleNamespace

from app.validators.repetition import action_key
from app.validators.support import location_supported, operating_conditions


def test_bounded_dkvb_demo_grammar_accepts_only_explicit_forms():
    component = "增压空气系统"
    assert location_supported("增压空气系统位置见 S02-P1/P2 装配图。", component)
    assert not location_supported("增压空气系统在发动机左边。", component)
    assert operating_conditions([SimpleNamespace(
        text="演示操作只填写已给出的模拟结果，不操作真实气源。"
    )]) == {"demo_input": "provided", "real_pressure": "forbidden"}
    assert operating_conditions([SimpleNamespace(text="可以向实车加压。")]) is None
    assert action_key(SimpleNamespace(text="检查 增压空气系统 的局部泄漏。", operation="inspect"), component) == (
        "inspect", "增压空气系统", "localized_leak"
    )
    assert action_key(SimpleNamespace(text="确认 增压空气系统 一定漏气。", operation="inspect"), component) is None
