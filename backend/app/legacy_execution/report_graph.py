"""Bounded report graph. Checkpoints hold draft output, never business authority."""

import os
from typing import TypedDict
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select, update

from app.domain.policies import DomainError
from app.infrastructure.model_factory import llm_factory
from app.infrastructure.model_gateway import ModelError
from app.infrastructure.orm import reports, runs
from app.services.report_policy import final_gate, snapshot
from app.services.report_read_service import current_validity
from app.validators.report import ReportDraft, validate_draft


def progress_draft(snap, gate):
    case = snap["case"]
    confirmed = []
    unresolved = []
    for obs in snap["observations"].values():
        step = snap["steps"].get(obs["step_id"])
        title = (step["candidate_json"].get("title", "已保存检查") if step else "已保存检查")
        payload = obs["payload"]
        if obs["kind"] == "unavailable" or not obs["payload"].get("checked"):
            reason = str(payload.get("reason") or payload.get("selected") or "尚无有效观察")
            unresolved.append("检查待补：" + title[:120] + "（" + reason[:200] + "）")
        else:
            detail = str(payload.get("selected") or "")[:200]
            measures = payload.get("measurements", [])
            if measures:
                detail += "；测量：" + "、".join(
                    f"{item['value']} {item['unit']}（{item['outcome']}）"
                    for item in measures if isinstance(item, dict)
                    and all(k in item for k in ("value", "unit", "outcome")))[:500]
            confirmed.append({"text": "已保存检查：" + title[:120] +
                              "；观察类型：" + obs["kind"] +
                              ("；观察值：" + detail if detail else "") +
                              "；其含义仍需复核",
                              "observation_ids": [str(obs["id"])], "evidence_ids": [],
                              "spec_ids": []})
    for area in snap["areas"]:
        card = snap["cards"].get(area["id"])
        if area["status"] != "completed" or card is None:
            unresolved.append("区域仍有未完成检查：" + area["title"])
        elif card["assessment"] in {"unknown", "conflicting", "needs_input"}:
            unresolved.append("区域仍需复核：" + area["title"] + "（" + card["assessment"] + "）")
    unresolved.extend("报告门禁缺项：" + item["code"] for item in gate["blocking_items"])
    if not case["corpus_manifest"]:
        unresolved.append("会话没有已冻结的允许资料")
    return ReportDraft(scope="当前病例进度；不是最终维修报告",
        confirmed_facts=confirmed, diagnostic_findings=[],
        unresolved_items=list(dict.fromkeys(unresolved))[:40],
        repair_actions=[], verification_actions=[],
        limitations=["不能据此确诊、排除或确定换件", "资料与车型适配仍须人工核实"]
    ).model_dump(mode="json")


def _render_and_stage(store, lease, stopped, *, settings, gateway_factory=None):
    with store.engine.connect() as c:
        run = c.execute(select(runs).where(runs.c.id == lease.job["run_id"])).mappings().one()
        report = c.execute(select(reports).where(reports.c.run_id == run["id"])).mappings().one()
        if report["content_json"]:
            return report["content_json"]
        snap = snapshot(c, report["owner_id"], report["case_id"], settings)
        gate = final_gate(c, report["owner_id"], snap, settings)
        if (snap["case"]["revision"] != report["input_revision"] or
                snap["case"]["graph_epoch"] != report["graph_epoch"] or
                snap["case"]["corpus_manifest"] != report["manifest_json"]):
            return {"_stale": True}
        if stopped.is_set():
            raise ModelError("REPORT_INTERRUPTED")
        if report["kind"] == "progress":
            draft = progress_draft(snap, gate)
        else:
            if not gate["allowed"]:
                return {"_stale": True}
            if gateway_factory is None and os.environ.get("XIUTU_WP13_PAID") != "1":
                raise ModelError("MODEL_CALL_DISABLED")
            factory = gateway_factory or (lambda: llm_factory(
                settings, paid=True, turn_id=str(run["id"]), resume_existing=True,
                prompt_version="wp13-v1", max_model_calls=2,
                max_output_tokens=settings.diagnosis_max_output_tokens))
            gateway = factory()
            # Only server-frozen, bounded card data is offered. The model may
            # arrange trusted actions; it cannot grant itself new source IDs.
            cards = []
            for area in snap["areas"]:
                card = snap["cards"].get(area["id"])
                if card is not None and area["status"] != "retired":
                    cards.append({"component_key": area["component_key"],
                                  "assessment": card["assessment"],
                                  "content": card["content_json"]})
            import json
            try:
                draft = gateway.generate_structured(ReportDraft, [
                    SystemMessage(content="Draft a bounded JSON report from trusted cards only. "
                        "Do not invent repair actions, specifications, citations or numeric values. "
                        "Copy diagnostic findings and report_actions exactly from a current card, "
                        "or leave them empty. Do not invent confirmed facts."),
                    HumanMessage(content=json.dumps({"cards": cards}, ensure_ascii=False)),
                ]).model_dump(mode="json")
            finally:
                gateway.close()
    # One durable draft per logical run: a replacement worker cannot purchase
    # another model answer after a crash before final publication.
    with lease.mutex:
        with lease.connection.begin():
            job, current_run = store._valid(lease)
            if job["kind"] != "report" or current_run["status"] != "running":
                raise DomainError("REPORT_RUN_STALE", "Report run is no longer active")
            existing = lease.connection.execute(select(reports).where(
                reports.c.run_id == current_run["id"]).with_for_update()).mappings().one()
            if existing["content_json"]:
                return existing["content_json"]
            if draft.get("_stale"):
                return draft
            lease.connection.execute(update(reports).where(reports.c.id == existing["id"])
                                     .values(content_json=draft))
            store._finish_valid(lease, job["lease_until"])
    return draft


class ReportState(TypedDict, total=False):
    report_id: str
    stale: bool
    conclusion_ids: list[str]
    draft: dict


class ReportGraph:
    """A separate LangGraph; only references and a candidate flow between nodes."""

    def __init__(self, store, lease, stopped, settings, gateway_factory):
        self.store, self.lease, self.stopped = store, lease, stopped
        self.settings, self.gateway_factory = settings, gateway_factory
        nodes = ("load_frozen_snapshot", "collect_conclusions", "detect_conflicts",
                 "synthesize_plan", "validate_claims")
        builder = StateGraph(ReportState)
        for name in nodes:
            builder.add_node(name, getattr(self, name))
        builder.add_edge(START, nodes[0])
        for left, right in zip(nodes, nodes[1:]):
            builder.add_edge(left, right)
        builder.add_edge(nodes[-1], END)
        self.graph = builder.compile()

    def _facts(self, state):
        with self.store.engine.connect() as c:
            report = c.execute(select(reports).where(
                reports.c.id == UUID(state["report_id"]))).mappings().one()
            snap = snapshot(c, report["owner_id"], report["case_id"], self.settings)
            return report, snap

    def load_frozen_snapshot(self, state):
        if self.stopped.is_set():
            raise ModelError("REPORT_INTERRUPTED")
        report, snap = self._facts(state)
        with self.store.engine.connect() as c:
            reasons = current_validity(c, report["owner_id"], report, self.settings, snap)["reasons"]
        return {"stale": bool(reasons)}

    def collect_conclusions(self, state):
        if state["stale"]:
            return {}
        report, snap = self._facts(state)
        current = [str(card["id"]) for card in snap["cards"].values()]
        return {"conclusion_ids": current,
                "stale": set(current) != set(report["conclusion_ids"])}

    def detect_conflicts(self, state):
        if state["stale"]:
            return {}
        report, snap = self._facts(state)
        if report["kind"] != "final":
            return {}
        with self.store.engine.connect() as c:
            gate = final_gate(c, report["owner_id"], snap, self.settings)
        return {"stale": not gate["allowed"]}

    def synthesize_plan(self, state):
        if state["stale"]:
            return {"draft": {"_stale": True}}
        return {"draft": _render_and_stage(self.store, self.lease, self.stopped,
            settings=self.settings, gateway_factory=self.gateway_factory)}

    def validate_claims(self, state):
        draft = state["draft"]
        if draft.get("_stale"):
            return {}
        report, snap = self._facts(state)
        with self.store.engine.connect() as c:
            validate_draft(c, report["owner_id"], snap, draft, self.settings,
                           final=report["kind"] == "final")
        return {}

    def execute(self):
        with self.store.engine.connect() as c:
            run = c.execute(select(runs).where(
                runs.c.id == self.lease.job["run_id"])).mappings().one()
            report = c.execute(select(reports).where(reports.c.run_id == run["id"])).mappings().one()
        return self.graph.invoke({"report_id": str(report["id"])})["draft"]


def run_report(store, lease, stopped, *, settings=None, gateway_factory=None):
    from app.config import load_settings

    settings = settings or store.settings or load_settings(
        project_env=os.environ.get("XIUTU_LOAD_PROJECT_ENV") == "1")
    return ReportGraph(store, lease, stopped, settings, gateway_factory).execute()
