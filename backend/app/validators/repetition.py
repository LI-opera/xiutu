"""Deterministic action semantics, never title equality or a fixed diagnostic tree."""

import hashlib
import json
import re
import unicodedata

ALIASES = {
    "inspect": ("检查", "查看", "观察", "inspect", "check"),
    "measure": ("测量", "测定", "measure"),
    "read": ("读取", "读取记录", "read"),
    "actuate": ("执行输出测试", "驱动", "actuate"),
}


def normalize(value):
    return re.sub(r"[\s，。,:：;；_\-]+", "", unicodedata.normalize("NFKC", value).casefold())


# Finite source-backed grammar; unsupported wording never becomes a valid key.
OBJECTS = {
    "inspect": {"外观": "appearance", "插头": "connector", "外壳": "housing", "局部泄漏": "localized_leak"},
    "measure": {"电压": "voltage", "电阻": "resistance", "压力": "pressure", "温度": "temperature"},
    "read": {"故障码": "fault_codes", "记录": "records"},
    "actuate": {"输出": "output"},
}


def action_key(action, component):
    text = normalize(action.text)
    for verb in ALIASES.get(action.operation, ()):
        prefix = normalize(verb) + normalize(component)
        if text.startswith(prefix):
            target = text[len(prefix) :].removeprefix("的")
            obj = OBJECTS[action.operation].get(target)
            if obj:
                return action.operation, normalize(component), obj
    return None


def action_semantics(action):
    for verb in ALIASES.get(action.operation, ()):
        match = re.fullmatch(
            re.escape(verb) + r"\s*([A-Za-z][A-Za-z0-9_-]*)\s*(?:的)?\s*(.+?)[。.]?", action.text
        )
        if match and action_key(action, match[1]):
            return action.operation
    return None


def fingerprint(step):
    body = dict(
        component=normalize(step.component_key),
        operations=sorted(
            {
                action_key(a, step.component_key)
                or (a.operation, normalize(step.component_key), "unsupported")
                for a in step.actions
            }
        ),
        measurements=sorted(
            [(m.quantity, m.unit, str(m.spec_id)) for m in step.input.measurements]
        ),
        conditions=sorted(normalize(p.text) for p in step.prerequisites),
        spec_conditions=sorted(
            json.dumps(m.conditions, sort_keys=True, ensure_ascii=False)
            for m in step.input.measurements
        ),
    )
    return (
        "v2:"
        + hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    )
