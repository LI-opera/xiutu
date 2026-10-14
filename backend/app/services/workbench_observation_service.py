"""Version-bound, append-only observations for frozen question templates."""
from copy import deepcopy
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import select, text, update

from app.domain.policies import DomainError, check_revision
from app.infrastructure.orm import case_analyses, cases, observations
from app.infrastructure.uow import UnitOfWork
from app.repositories.cases import CaseRepository
from app.services.run_service import idempotent, lock_case
from app.services.workbench_answer_validation import validate_answer
from app.services.workbench_topic_workflow import workflow_for


class TopicAnswer(BaseModel):
    expected_revision: int = Field(ge=0)
    topic_version: str
    question_id: str
    option_ids: list[str] = Field(default_factory=list, max_length=20)
    fields: dict[str, object] = Field(default_factory=dict)
    note: str = Field(default="", max_length=2000)
    unavailable_reason: str = Field(default="", max_length=2000)
    batch_id: str | None = None
    round_id: str | None = None
    retest_frames: list[dict[str, object]] = Field(default_factory=list, max_length=3)
    correction_reason: str | None = Field(default=None, max_length=1000)
    related_analysis_id: UUID | None = None


class PlanExpand(BaseModel):
    expected_revision: int = Field(ge=0)
    area_id: str


class TopicService:
    def __init__(self, case_service):
        self.case_service = case_service
        self.engine = case_service.engine

    @staticmethod
    def _rows(conn, case_id, version):
        # Full read, not the legacy 50/100 observation window. Stable ordering
        # permits a separately paged history without truncating the projection.
        return conn.execute(select(observations).where(
            observations.c.case_id == case_id,
            observations.c.payload["topic_version"].astext == version)
            .order_by(observations.c.created_revision, observations.c.id)).mappings().all()

    @staticmethod
    def _topic(row):
        from app.services.workbench_templates import FrozenTemplate, is_template
        if is_template(row):
            return FrozenTemplate(row)
        from app.topics import dkvb_b01, dkvb_b02
        version = ((row.get("intake_snapshot") or {}).get("topic_binding") or {}).get("version")
        module = {dkvb_b01.TOPIC_VERSION: dkvb_b01,
                  dkvb_b02.TOPIC_VERSION: dkvb_b02}.get(version)
        if module is None:
            raise DomainError("TOPIC_NOT_BOUND", "病例未绑定可执行的新专题", 404)
        module.require_bound(row)
        return module

    @staticmethod
    def _serialize(record, effective):
        return {"id": str(record["id"]), "question_id": record["payload"]["question_id"],
                "payload": record["payload"], "round_id": record["payload"].get("round_id"),
                "created_revision": record["created_revision"],
                "supersedes_id": str(record["supersedes_id"]) if record["supersedes_id"] else None,
                "correction_reason": record["correction_reason"],
                "effective": record["id"] not in effective}

    def _view(self, conn, row):
        from app.services.workbench_templates import is_template, template_projection
        module = self._topic(row)
        case = self.case_service.with_active(conn, row)
        rows = self._rows(conn, row["id"], module.TOPIC_VERSION)
        superseded = {record["supersedes_id"] for record in rows if record["supersedes_id"]}
        topic, _ = module.catalog()
        if is_template(row):
            projection = template_projection
        else:
            from app.services.workbench_b01_projection import project
            projection = project
        return jsonable_encoder({"case": case, "topic": topic,
            "plan": row["intake_snapshot"]["topic_plan"],
            "observations": [self._serialize(record, superseded) for record in rows],
            "view": projection(row, rows, case.get("report_gate"), topic),
            "mode": "server_saved_" + module.TOPIC_VERSION, "ai_model_connected": False})

    def get(self, actor, case_id):
        with UnitOfWork(self.engine) as uow:
            row = CaseRepository(uow.connection).get(actor, case_id)
            if row is None:
                raise DomainError("NOT_FOUND", "Case not found", 404)
            self._topic(row)
            view = self._view(uow.connection, row)
            current = uow.connection.execute(select(cases.c.revision).where(cases.c.id == case_id)).scalar_one()
            if current != row["revision"]:
                raise DomainError("WORKBENCH_REVISION_CHANGED", "病例已更新，请重新加载", 409)
            return view

    def history(self, actor, case_id, after_revision=0, after_id=None, limit=100):
        if not 1 <= limit <= 200 or after_revision < 0:
            raise DomainError("VALIDATION_ERROR", "分页参数无效", 422)
        with UnitOfWork(self.engine) as uow:
            row = CaseRepository(uow.connection).get(actor, case_id)
            if row is None:
                raise DomainError("NOT_FOUND", "Case not found", 404)
            module = self._topic(row)
            rows = self._rows(uow.connection, case_id, module.TOPIC_VERSION)
            superseded = {r["supersedes_id"] for r in rows if r["supersedes_id"]}
            filtered = [r for r in rows if (r["created_revision"], str(r["id"])) >
                        (after_revision, after_id or "")]
            page = filtered[:limit]
            return {"items": [self._serialize(r, superseded) for r in page],
                    "next": {"revision": page[-1]["created_revision"], "id": str(page[-1]["id"])}
                    if len(filtered) > limit else None, "total": len(rows)}

    @staticmethod
    def _effective(rows, question_id, round_id):
        from app.services.legacy_topic_answer_rules import effective_legacy_observation
        return effective_legacy_observation(rows, question_id, round_id)

    @staticmethod
    def _validate_answer(topic, plan, rows, body, original=None):
        return validate_answer(topic, plan, rows, body, original,
                               effective=workflow_for(topic).effective)

    @staticmethod
    def _prerequisites(q, plan, rows, body, topic=None):
        topic_explicit = topic is not None
        if topic is None:
            from app.topics import dkvb_b01
            topic = dkvb_b01.catalog()[0]
        return workflow_for(topic).prerequisites(q, plan, rows, body, show_labels=topic_explicit)

    @staticmethod
    def _repair_round(plan, existing, option_ids, original_id):
        # Compatibility entry for existing B01/B02 callers.
        from app.topics import dkvb_b01
        return workflow_for(dkvb_b01.catalog()[0]).begin_round(plan, existing, option_ids, original_id)

    def save(self, actor, case_id, body, key, original_id=None):
        with UnitOfWork(self.engine) as uow:
            conn = uow.connection
            row = lock_case(conn, actor, case_id)
            module = self._topic(row)
            # idempotency_keys.route_scope is varchar(100); keep exact target
            # identity without using the much longer public URL.
            from app.services.workbench_templates import is_template
            scope_version = "tpl1" if is_template(row) else module.TOPIC_VERSION
            scope = f"{scope_version}:{'correct' if original_id else 'save'}:{case_id}" + (f":{original_id}" if original_id else "")
            def action():
                check_revision(row["revision"], body.expected_revision)
                from app.services.template_case_history import require_open
                require_open(row)
                topic, _ = module.catalog()
                rows = self._rows(conn, case_id, module.TOPIC_VERSION)
                snap = deepcopy(row["intake_snapshot"])
                plan = snap["topic_plan"]
                q = next((q for q in topic["questions"] if q["id"] == body.question_id), None)
                if not q:
                    raise DomainError("QUESTION_UNKNOWN", "问题不存在", 422)
                workflow = workflow_for(topic, template_bound=is_template(row))
                if body.related_analysis_id:
                    if q["id"] != workflow.repair_id:
                        raise DomainError("ANALYSIS_LINK_SCOPE", "仅实际处理可关联病例建议", 422)
                    linked = conn.execute(select(case_analyses.c.id).where(
                        case_analyses.c.id == body.related_analysis_id,
                        case_analyses.c.case_id == case_id,
                        case_analyses.c.owner_id == actor,
                        case_analyses.c.status == "current")).scalar_one_or_none()
                    if linked is None:
                        raise DomainError("ANALYSIS_LINK_INVALID", "关联建议不存在或尚未完成", 422)
                round_id = workflow.initial_round(q, plan, body)
                existing = workflow.effective(rows, body.question_id, round_id if workflow.round_scoped(q) else None)
                if original_id:
                    if not existing or existing["id"] != original_id:
                        raise DomainError("CORRECTION_CONFLICT", "当前有效记录已变化，请同步后重试", 409)
                elif existing:
                    workflow.allow_new_record(q, existing, plan, body)
                if q["id"] == workflow.repair_id:
                    round_id = workflow.begin_round(plan, existing, body.option_ids, original_id)
                if workflow.round_scoped(q) and body.round_id and q["id"] != workflow.repair_id and body.round_id != round_id:
                    raise DomainError("ROUND_MISMATCH", "复检轮次已经变化", 409)
                q, fields, unavailable = validate_answer(
                    topic, plan, rows, body, existing, effective=workflow.effective)
                workflow.after_answer(q, body, plan)
                missing = workflow.prerequisites(q, plan, rows, body)
                if missing:
                    raise DomainError("PREREQUISITE_MISSING", "执行此操作尚缺少前置条件", 422, details={"missing": missing})
                # Recording an optional observation does not make the whole
                # area, or even that question, required for first advice.
                plan["version"] += 1
                snap["topic_plan"] = plan
                revision = row["revision"] + 1
                conn.execute(update(cases).where(cases.c.id == case_id).values(
                    revision=revision, intake_snapshot=snap, updated_at=text("clock_timestamp()")))
                identifier = uuid4()
                option_changed = bool(existing and existing["payload"].get("option_ids", []) != body.option_ids)
                payload = {"topic_id": topic["topic_id"], "topic_version": topic["version"],
                           "topic_content_hash": module.binding()["content_hash"],
                           "question_id": q["id"], "option_ids": body.option_ids,
                           "fields": fields, "note": body.note.strip(),
                           "retest_frames": workflow.retest_frames(q, body),
                           "unavailable_reason": (body.unavailable_reason.strip() or "原因未提供") if unavailable else "",
                           "batch_id": body.batch_id, "round_id": round_id,
                           "source_refs": q["source_refs"], "source": "USER_OBSERVATION",
                           "related_analysis_id": str(body.related_analysis_id) if body.related_analysis_id else None,
                           "operation_type": ("user_reselection" if option_changed else "user_record_update") if original_id else "user_selection",
                           "instance_id": f"{q['id']}:{round_id or 'before-repair'}"}
                conn.execute(observations.insert().values(
                    id=identifier, case_id=case_id, area_id=None, step_id=None,
                    kind="unavailable" if unavailable else "measurement" if q["answer_kind"] == "numeric_with_choice" else "choice",
                    payload=payload, created_revision=revision, supersedes_id=original_id,
                    correction_reason=((body.correction_reason or "").strip() or ("用户改选选项" if option_changed else "用户更新观测字段")) if original_id else None,
                    actor_id=actor))
                fresh = conn.execute(select(cases).where(cases.c.id == case_id)).mappings().one()
                return 200, {"observation_id": str(identifier), "revision": revision,
                             "view": self._view(conn, fresh)}
            return idempotent(conn, actor, scope, key, body.model_dump(mode="json"), action)

    def expand(self, actor, case_id, body, key):
        with UnitOfWork(self.engine) as uow:
            conn = uow.connection
            row = lock_case(conn, actor, case_id)
            module = self._topic(row)
            def action():
                check_revision(row["revision"], body.expected_revision)
                from app.services.template_case_history import require_open
                require_open(row)
                topic, _ = module.catalog()
                if body.area_id not in {a["id"] for a in topic["areas"]}:
                    raise DomainError("AREA_UNKNOWN", "区域不存在", 422)
                snap = deepcopy(row["intake_snapshot"])
                plan = snap["topic_plan"]
                if body.area_id not in plan["expanded_area_ids"]:
                    plan["expanded_area_ids"].append(body.area_id)
                    for q in topic["questions"]:
                        if q["area_id"] == body.area_id and q["phase"] == "diagnostic_observation" and q["answer_kind"] not in {"automatic_derived", "conditional_operation"} and q["id"] not in plan["required_question_ids"]:
                            plan["required_question_ids"].append(q["id"])
                    plan["version"] += 1
                    conn.execute(update(cases).where(cases.c.id == case_id).values(
                        revision=row["revision"]+1, intake_snapshot=snap, updated_at=text("clock_timestamp()")))
                fresh = conn.execute(select(cases).where(cases.c.id == case_id)).mappings().one()
                return 200, self._view(conn, fresh)
            return idempotent(conn, actor, f"{module.TOPIC_VERSION}:expand:{case_id}", key,
                              body.model_dump(mode="json"), action)
