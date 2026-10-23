"""Vehicle -> stored complete template. No LLM, fuzzy guess or hidden routing."""
import hashlib
import json
import re
from copy import deepcopy

from sqlalchemy import select

from app.domain.policies import DomainError
from app.infrastructure.orm import workbench_template_matches, workbench_templates
from app.services.template_projection import build_plan, project_template

FLOW = "template-match-v1"


def content_hash(content):
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def normalize_vehicle(vehicle):
    result = dict(vehicle)
    brand = (result.get("brand") or "").strip()
    model = (result.get("model") or "").strip()
    result["brand"] = {"VW": "大众", "VOLKSWAGEN": "大众", "一汽大众": "大众",
                       "一汽-大众": "大众"}.get(brand.upper(), brand)
    result["model"] = {"TAYRON": "探岳", "大众探岳": "探岳", "一汽大众探岳": "探岳"}.get(model.upper(), model)
    result["engine_code"] = (result.get("engine_code") or "").strip().upper() or None
    return result


def _active_matches(matches):
    """Choose the newest version only within the same template/applicability.

    Different template IDs or engine variants remain separate candidates so
    an omitted optional engine never silently chooses a vehicle identity.
    """
    by_applicability = {}
    for item in matches:
        key = (item["template_id"], item["engine_code"], item["brand"], item["model"],
               item["year_from"], item["year_to"], item["fault_code"])
        by_applicability.setdefault(key, []).append(item)

    def version_key(item):
        return tuple((1, int(part)) if part.isdecimal() else (0, part.casefold())
                     for part in re.split(r"(\d+)", item["version"]) if part)

    return [max(group, key=version_key) for group in by_applicability.values()]


def resolve_template(conn, data):
    vehicle = normalize_vehicle(data.vehicle.model_dump(mode="json"))
    if not vehicle.get("brand") or not vehicle.get("year") or not data.fault_codes:
        raise DomainError("INTAKE_REQUIRED", "请填写品牌、车型、年份、故障码和主诉摘要。", 422)
    # First package deliberately supports one code at a time; never ignore an extra code.
    if len(data.fault_codes) != 1:
        raise DomainError("MULTIPLE_CODES_NOT_CONFIGURED", "本阶段请使用一个故障码匹配；多故障码合并尚未配置。", 422)
    matches = list(conn.execute(select(workbench_template_matches).where(
        workbench_template_matches.c.brand == vehicle["brand"],
        workbench_template_matches.c.model == vehicle["model"],
        workbench_template_matches.c.year_from <= vehicle["year"],
        workbench_template_matches.c.year_to >= vehicle["year"],
        workbench_template_matches.c.fault_code == data.fault_codes[0])).mappings())
    if not matches:
        raise DomainError("TEMPLATE_NOT_FOUND", "暂无适用模板。目前已配置：大众探岳 2019 / DKVB，P0299 或 P0236。", 422)
    # Missing optional engine information must not block an unambiguous match.
    # Keep the user's engine unknown; the template is not a vehicle identity claim.
    if vehicle["engine_code"]:
        matches = [item for item in matches if item["engine_code"] == vehicle["engine_code"]]
    matches = _active_matches(matches)
    keys = {(item["template_id"], item["version"]) for item in matches}
    if not keys:
        raise DomainError("TEMPLATE_NOT_FOUND", "此发动机尚无适用模板，未套用其他车型的题目。", 422)
    if len(keys) != 1:
        raise DomainError("TEMPLATE_AMBIGUOUS", "当前信息对应多个排查模板，尚不能唯一选择；可补充发动机代码缩小范围，或核对模板适用配置。", 409)
    template_id, version = next(iter(keys))
    template = conn.execute(select(workbench_templates).where(
        workbench_templates.c.template_id == template_id,
        workbench_templates.c.version == version)).mappings().one()
    if content_hash(template["content_json"]) != template["content_hash"]:
        raise DomainError("TEMPLATE_CONTENT_CHANGED", "模板版本内容不一致，请检查资料配置。", 409)
    return template, vehicle


def frozen_snapshot(conn, data):
    template, vehicle = resolve_template(conn, data)
    topic = deepcopy(template["content_json"])
    intake = data.topic_intake or {}
    intake = {"symptom_condition": intake.get("symptom_condition") or "unprovided",
              "safety_gate": intake.get("safety_gate") or "unprovided"}
    if intake["symptom_condition"] not in {"unprovided", "mid_load", "high_load", "all_load", "intermittent"} or intake["safety_gate"] not in {"unprovided", "none", "caution", "stop_now", "unavailable"}:
        raise DomainError("INTAKE_INVALID", "工况或安全风险选项无效。", 422)
    plan = build_plan(topic, intake)
    return {"workbench_flow": FLOW, "vehicle": vehicle,
            "fault_description": data.fault_description, "fault_codes": data.fault_codes,
            "synthetic": False, "demo": True, "formal_usable": False,
            "template_binding": {"template_id": template["template_id"], "version": template["version"],
                                 "title": template["title"], "content_hash": template["content_hash"]},
            "template_content": topic, "topic_plan": plan,
            "source_scope": "资料包编辑性排查模板；用户录入，不预置现场观察；非厂家完整故障树"}


def is_template(case):
    return (case.get("intake_snapshot") or {}).get("workbench_flow") == FLOW


class FrozenTemplate:
    """Adapter lets the existing observation service use case-frozen questions."""
    def __init__(self, case):
        snap = case["intake_snapshot"]
        self.topic = snap["template_content"]
        self.claim = snap["template_binding"]
        self.TOPIC_VERSION = self.topic["version"]
        if content_hash(self.topic) != self.claim["content_hash"]:
            raise DomainError("TEMPLATE_SNAPSHOT_INVALID", "病例模板快照不一致", 409)

    def catalog(self):
        return self.topic, self.claim["content_hash"]

    def binding(self):
        return {"content_hash": self.claim["content_hash"]}


def template_projection(case, records, topic):
    return project_template(case, records, topic)
