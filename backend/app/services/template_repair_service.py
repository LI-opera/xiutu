"""Actual treatment and later retest for cases bound to a frozen area template."""
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, update, func

from app.domain.policies import DomainError
from app.infrastructure.orm import cases, template_repair_rounds as rounds
from app.infrastructure.uow import UnitOfWork
from app.services.write_guards import lock_case
from app.services.workbench_templates import is_template


def _areas(row):
    if not is_template(row):
        raise DomainError("TEMPLATE_REPAIR_NOT_APPLICABLE", "此入口仅用于匹配模板病例。", 404)
    return {area["id"]: area["title"] for area in row["intake_snapshot"]["template_content"]["areas"]}


class TemplateRepairService:
    def __init__(self, engine, topic_service=None):
        self.engine = engine
        # Writes post-repair re-checks as ordinary records; optional for read-only callers.
        self.topic_service = topic_service

    def get(self, actor, case_id):
        with UnitOfWork(self.engine) as uow:
            row = lock_case(uow.connection, actor, case_id)
            areas = _areas(row)
            records = uow.connection.execute(select(rounds).where(rounds.c.case_id == case_id)
                .order_by(rounds.c.created_at.desc(), rounds.c.id.desc())).mappings().all()
        return jsonable_encoder({"revision": row["revision"], "areas": areas,
                                 "rounds": [dict(record) for record in records]})

    def record_repair(self, actor, case_id, body):
        if not body.repair_action.strip():
            raise DomainError("REPAIR_ACTION_REQUIRED", "请填写实际完成的处理。", 422)
        with UnitOfWork(self.engine) as uow:
            conn = uow.connection
            case = lock_case(conn, actor, case_id, body.expected_revision)
            from app.services.template_case_history import require_open
            require_open(case)
            if body.area_id not in _areas(case):
                raise DomainError("AREA_NOT_MATCHED", "处理区域不属于本病例的匹配模板。", 422)
            active = conn.execute(select(rounds.c.id).where(rounds.c.case_id == case_id,
                rounds.c.area_id == body.area_id, rounds.c.retested_at.is_(None))).scalar_one_or_none()
            if active:
                raise DomainError("RETEST_PENDING", "此区域已有未复检的处理，请先记录复检结果。", 409)
            identifier = uuid4()
            conn.execute(rounds.insert().values(id=identifier, case_id=case_id,
                area_id=body.area_id, repair_action=body.repair_action.strip(),
                repair_note=body.repair_note.strip(), pre_repair_revision=case["revision"]))
            conn.execute(update(cases).where(cases.c.id == case_id).values(
                revision=cases.c.revision + 1, updated_at=func.now()))
        return self.get(actor, case_id)

    def record_retest(self, actor, case_id, round_id, body):
        if not body.retest_evidence.strip():
            raise DomainError("RETEST_EVIDENCE_REQUIRED", "请填写处理后新取得的复检证据。", 422)
        with UnitOfWork(self.engine) as uow:
            conn = uow.connection
            case = lock_case(conn, actor, case_id, body.expected_revision)
            from app.services.template_case_history import require_open
            require_open(case)
            areas = _areas(case)
            record = conn.execute(select(rounds).where(rounds.c.id == round_id,
                rounds.c.case_id == case_id).with_for_update()).mappings().one_or_none()
            if not record:
                raise DomainError("REPAIR_ROUND_NOT_FOUND", "处理轮次不存在。", 404)
            if record["retested_at"] is not None:
                raise DomainError("RETEST_ALREADY_RECORDED", "本轮复检已保存；如再次处理，请建立新轮次。", 409)
            if body.next_area_id and (body.next_area_id not in areas or body.next_area_id == record["area_id"]):
                raise DomainError("NEXT_AREA_INVALID", "下一排查区域必须是本病例的另一个匹配区域。", 422)
            rechecks = getattr(body, "observations", None) or []
            if len({item.question_id for item in rechecks}) != len(rechecks):
                raise DomainError("RETEST_QUESTION_DUPLICATE", "同一复检项目只能提交一次。", 422)
            for item in rechecks:
                case = self._write_recheck(conn, actor, case, record, item)
            conn.execute(update(rounds).where(rounds.c.id == round_id).values(
                retest_condition=body.retest_condition, retest_outcome=body.retest_outcome,
                retest_evidence=body.retest_evidence.strip(), next_area_id=body.next_area_id,
                retested_at=func.now()))
            conn.execute(update(cases).where(cases.c.id == case_id).values(
                revision=cases.c.revision + 1, updated_at=func.now()))
        return self.get(actor, case_id)

    def _write_recheck(self, conn, actor, case, record, item):
        """Save one re-checked question as a new record that supersedes the pre-repair one.

        The old answer stays in history; summaries, rule calculations and AI input then use
        the post-repair value. Returns the refreshed case row.
        """
        from app.services.workbench_observation_service import TopicAnswer
        from app.services.workbench_topic_workflow import workflow_for

        if self.topic_service is None:
            raise DomainError("RETEST_RECORDS_UNAVAILABLE", "当前服务未启用复检记录保存。", 503)
        module = self.topic_service._topic(case)
        topic, _ = module.catalog()
        q = next((q for q in topic["questions"] if q["id"] == item.question_id), None)
        if q is None or q.get("area_id") != record["area_id"]:
            raise DomainError("RETEST_QUESTION_INVALID", "复检项目不属于本轮处理区域。", 422)
        if (q.get("capture") or {}).get("batch_id_required"):
            raise DomainError("RETEST_BATCH_UNSUPPORTED",
                              "成组采集的读数暂不支持在复检中单项重录，请写入复检证据。", 422)
        rows = self.topic_service._rows(conn, case["id"], module.TOPIC_VERSION)
        existing = workflow_for(topic).effective(rows, q["id"], None)
        answer = TopicAnswer(expected_revision=case["revision"], topic_version=topic["version"],
                             question_id=q["id"], option_ids=item.option_ids, fields=item.fields,
                             note=item.note, unavailable_reason=item.unavailable_reason,
                             correction_reason="处理后复检")
        self.topic_service._write(conn, actor, case, module, answer,
                                  existing["id"] if existing else None,
                                  extra_payload={"repair_round_id": str(record["id"]),
                                                 "operation_type": "post_repair_recheck"})
        return conn.execute(select(cases).where(cases.c.id == case["id"])).mappings().one()
