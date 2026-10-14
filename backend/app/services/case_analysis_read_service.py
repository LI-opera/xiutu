"""Owned B02 historical analysis lists, details and retained diagnostics."""

from sqlalchemy import select

from app.domain.policies import DomainError
from app.infrastructure.orm import case_analyses, cases, runs
from app.infrastructure.uow import UnitOfWork
from app.services.case_analysis_projection import (MAX_INPUT_CHARS, PROMPT_VERSION,
    _current_snapshot, _gate, _question_targets, configured_mode)
from app.services.workbench_b01_service import TopicService
from app.topics import dkvb_b02


class CaseAnalysisReadService:
    def __init__(self, case_service, settings):
        self.engine, self.case_service, self.settings = case_service.engine, case_service, settings

    def _view(self, conn, row):
        dkvb_b02.require_bound(row)
        return TopicService(self.case_service)._view(conn, row)

    def _body(self, row, run, current_case, current_view):
        stale = row["input_revision"] != current_case["revision"] or (
            current_case["intake_snapshot"].get("topic_binding") or {}).get("content_hash") != row["topic_hash"]
        status = ("stale" if row["status"] == "current" and stale else
                  "failed" if row["status"] == "failed" or run["status"] in {"failed", "cancelled"} else
                  "completed" if row["status"] == "current" else run["status"])
        snap = row["snapshot_json"]
        unresolved_ids = list(snap["synthesis"].get("missing_question_ids", [])) + [
            item["question_id"] for item in snap["synthesis"].get("unavailable", [])]
        target = {item["question_id"]: item["target_question_id"] for item in
                  _question_targets(current_view["topic"],
                                    [q["id"] for q in current_view["topic"]["questions"]],
                                    snap["observations"])}
        return {"id": str(row["id"]), "case_id": str(row["case_id"]), "run_id": str(row["run_id"]),
                "status": status, "input_revision": row["input_revision"],
                "current_revision": current_case["revision"], "stale": stale,
                "generation": "模型替身验证结果，非真实 AI 生成" if row["mode"] == "stub" else "真实模型生成",
                "mode": row["mode"], "provider": row["provider"], "model": row["model"],
                "prompt_version": row["prompt_version"], "allowed_scope": row["allowed_scope"],
                "content": row["content_json"] if row["status"] == "current" else None,
                "error_code": row["error_code"] or (run["error_json"] or {}).get("code"),
                "error_message": ("生成内容超出本次补充检查范围，本次未发布；病例记录未改变。"
                                  if row["error_code"] == "ANALYSIS_SCOPE_EXCEEDED" else
                                  "模型响应的受限诊断记录保存失败，本次未发布；病例记录未改变。"
                                  if row["error_code"] == "ANALYSIS_DIAGNOSTIC_STORE_FAILED" else
                                  "模型响应格式未通过校验，本次未发布；病例记录未改变。"
                                  if row["error_code"] in {"MODEL_JSON_INVALID_NO_RETRY", "MODEL_SCHEMA_INVALID_NO_RETRY"} else
                                  "分析失败；病例记录未改变。" if row["status"] == "failed" else None),
                "basis": {"observation_ids": [item["id"] for item in snap["observations"]],
                          "observations": snap["observations"],
                          "sources": snap["source_context"]["excerpts"],
                          "editorial_cards": snap["source_context"]["editorial_cards"],
                          "images": snap["source_context"]["image_references"],
                          "editorial_rules": snap.get("editorial_thresholds", []),
                          "supported_action_ids": list(snap.get("action_catalog", {}).get("actions", {})),
                          "unresolved_questions": _question_targets(current_view["topic"], unresolved_ids,
                                                                   snap["observations"]),
                          "questions": [
                              {"id": q["id"], "title": q["title"], "answer_kind": q["answer_kind"],
                               "target_question_id": target.get(q["id"]) if
                               q.get("stage") != "S0" or q["id"] == "IN-08" else None}
                              for q in current_view["topic"]["questions"]],
                          "missing_body_source_refs": snap["source_context"]["missing_body_source_refs"]},
                "post_analysis_retest": [item for item in current_case["intake_snapshot"].get("topic_plan", {}).get("rounds", [])
                                         if item["id"] not in {round_item["id"] for round_item in snap["plan"]["rounds"]}],
                "linked_treatments": [item["id"] for item in current_view["observations"]
                                      if item["effective"] and item["question_id"] == "RET-01" and
                                      item["payload"].get("related_analysis_id") == str(row["id"])],
                "current_retest": {qid: current_view["view"]["derived"].get(qid)
                                   for qid in ("RET-07", "RET-08") if current_view["view"]["derived"].get(qid)},
                "created_at": row["created_at"].isoformat()}

    def list(self, actor, case_id):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            row = c.execute(select(cases).where(cases.c.id == case_id, cases.c.owner_id == actor)).mappings().one_or_none()
            if row is None:
                raise DomainError("NOT_FOUND", "Case not found", 404)
            view = self._view(c, row)
            entries = c.execute(select(case_analyses, runs.c.status.label("run_status"), runs.c.error_json.label("run_error"))
                .join(runs, case_analyses.c.run_id == runs.c.id)
                .where(case_analyses.c.case_id == case_id, case_analyses.c.owner_id == actor)
                .order_by(case_analyses.c.created_at.desc(), case_analyses.c.id.desc()).limit(30)).mappings().all()
            mode = configured_mode(self.settings)
            gate = _gate(view)
            preview = _current_snapshot(view)["source_context"] if gate["allowed"] else None
            return {"case_id": str(case_id), "gate": gate, "configuration": {**mode,
                    "input_char_limit": MAX_INPUT_CHARS,
                    "max_output_tokens": self.settings.case_analysis_max_output_tokens,
                    "max_real_calls_per_request": 1, "prompt_version": PROMPT_VERSION},
                    "preview": {"excerpts": preview["excerpts"], "missing_body_source_refs": preview["missing_body_source_refs"],
                                "editorial_card_count": len(preview["editorial_cards"]),
                                "image_references": preview["image_references"]} if preview else None,
                    "items": [self._body(item, {"status": item["run_status"], "error_json": item["run_error"]}, row, view)
                              for item in entries]}

    def get(self, actor, case_id, analysis_id):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            row = c.execute(select(cases).where(cases.c.id == case_id, cases.c.owner_id == actor)).mappings().one_or_none()
            if row is None:
                raise DomainError("NOT_FOUND", "Case not found", 404)
            view = self._view(c, row)
            result = c.execute(select(case_analyses, runs.c.status.label("run_status"), runs.c.error_json.label("run_error"))
                .join(runs, case_analyses.c.run_id == runs.c.id)
                .where(case_analyses.c.id == analysis_id, case_analyses.c.case_id == case_id,
                       case_analyses.c.owner_id == actor)).mappings().one_or_none()
            if result is None:
                raise DomainError("NOT_FOUND", "Analysis not found", 404)
            return self._body(result, {"status": result["run_status"], "error_json": result["run_error"]}, row, view)

    def diagnostic(self, actor, case_id, analysis_id):
        """Development operator only; never included in ordinary workbench views."""
        if self.settings.app_mode != "test":
            raise DomainError("ANALYSIS_DIAGNOSTIC_FORBIDDEN", "诊断响应仅在隔离开发环境可查看", 403)
        with UnitOfWork(self.engine) as u:
            row = u.connection.execute(select(case_analyses).join(cases, cases.c.id == case_analyses.c.case_id)
                .where(case_analyses.c.id == analysis_id, case_analyses.c.case_id == case_id,
                       case_analyses.c.owner_id == actor, cases.c.owner_id == actor)).mappings().one_or_none()
            if row is None:
                raise DomainError("NOT_FOUND", "Analysis not found", 404)
            diagnostic = row["diagnostic_json"] or {}
            if not diagnostic:
                return {"analysis_id": str(analysis_id), "availability": "not_retained",
                        "reason": "历史分析当时未保留模型响应，无法恢复具体触发字段"}
            from datetime import datetime, timezone
            expires = diagnostic.get("retained_until")
            if expires and datetime.fromisoformat(expires) < datetime.now(timezone.utc):
                return {"analysis_id": str(analysis_id), "availability": "expired"}
            return {"analysis_id": str(analysis_id), "input_revision": row["input_revision"],
                    "availability": "retained", "diagnostic": diagnostic}

