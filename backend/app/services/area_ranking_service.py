"""One optional AI ordering of an already matched, case-frozen area subset."""
import json
import os
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.domain.policies import DomainError
from app.infrastructure.model_gateway import DeepSeekGateway, ModelError
from app.infrastructure.orm import case_area_rankings
from app.infrastructure.uow import UnitOfWork
from app.services.workbench_templates import is_template

PROMPT_VERSION = "area-semantic-rank-v1"


class RankedArea(BaseModel):
    model_config = ConfigDict(extra="forbid")
    area_id: str
    reason: str = Field(min_length=4, max_length=180)


class RankingProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    areas: list[RankedArea]


def ranking_input(case):
    snap = case["intake_snapshot"]
    return {
        "complaint": case["fault_description"],
        "fault_codes": case["fault_codes"],
        "symptom_condition": snap.get("topic_plan", {}).get("intake", {}).get("symptom_condition", "unprovided"),
        "candidates": [
            {"area_id": area["id"], "title": area["title"], "description": area["description"]}
            for area in snap["template_content"]["areas"]
        ],
    }


def validate_ranking(proposal, candidates):
    ids = [entry["area_id"] for entry in candidates]
    received = [entry.area_id for entry in proposal.areas]
    if len(received) != len(ids) or set(received) != set(ids) or len(set(received)) != len(received):
        raise DomainError("AREA_RANKING_INVALID", "AI 排序没有完整保留匹配区域，已使用模板顺序。", 502)
    return {"areas": [item.model_dump() for item in proposal.areas]}


class AreaRankingService:
    def __init__(self, case_service, settings):
        self.case_service = case_service
        self.settings = settings

    def _case(self, actor, case_id):
        case = self.case_service.get(actor, case_id)
        if not is_template(case):
            raise DomainError("AREA_RANKING_NOT_APPLICABLE", "此病例未绑定区域匹配模板。", 404)
        return case

    def _row(self, case_id):
        with UnitOfWork(self.case_service.engine) as uow:
            return uow.connection.execute(select(case_area_rankings).where(
                case_area_rankings.c.case_id == case_id)).mappings().first()

    def get(self, actor, case_id):
        case = self._case(actor, case_id)
        fallback = [area["area_id"] for area in ranking_input(case)["candidates"]]
        row = self._row(case_id)
        if row is None:
            return {"status": "not_requested", "source": "template", "order": fallback, "reasons": {},
                    "available": self._authorized(case_id), "error_code": None,
                    "model": None, "requested_at": None, "finished_at": None}
        if row["status"] != "completed":
            uncertain = (row["status"] == "running" and
                         (datetime.now(timezone.utc) - row["created_at"]).total_seconds() > 120)
            return {"status": "failed" if uncertain else row["status"], "source": "template",
                    "order": fallback, "reasons": {}, "available": False,
                    "error_code": "REQUEST_OUTCOME_UNKNOWN" if uncertain else row["error_code"],
                    "model": row["model"], "requested_at": row["created_at"].isoformat(),
                    "finished_at": row["updated_at"].isoformat() if row["status"] == "failed" else None}
        result = row["result_json"] or {}
        try:
            proposal = RankingProposal.model_validate(result)
            validate_ranking(proposal, ranking_input(case)["candidates"])
        except (ValueError, DomainError):
            return {"status": "failed", "source": "template", "order": fallback, "reasons": {},
                    "available": False, "error_code": "STORED_RANKING_INVALID",
                    "model": row["model"], "requested_at": row["created_at"].isoformat(),
                    "finished_at": row["updated_at"].isoformat()}
        return {"status": "completed", "source": "ai", "order": [item.area_id for item in proposal.areas],
                "reasons": {item.area_id: item.reason for item in proposal.areas},
                "available": False, "error_code": None, "model": row["model"],
                "requested_at": row["created_at"].isoformat(),
                "finished_at": row["updated_at"].isoformat()}

    def _isolated_database(self):
        from app.infrastructure.db_target import validate_target
        try:
            validate_target(self.settings.database_url.get_secret_value(), "test")
        except (ValueError, AttributeError):
            return False
        return True

    def _authorized(self, case_id):
        if (os.environ.get("XIUTU_AREA_RANKING_PAID_AUTHORIZED") != "1"
                or not self.settings.deepseek_api_key):
            return False
        if os.environ.get("XIUTU_AREA_RANKING_ALLOWED_CASE_ID") == str(case_id):
            return True
        # Standing consent applies only to the isolated, loopback WP15 workspace.
        # The POST endpoint still requires an authenticated, CSRF-protected click;
        # the unique case row limits each case to one provider attempt.
        return (os.environ.get("XIUTU_AREA_RANKING_LOCAL_TESTING") == "1"
                and self.settings.app_mode == "test"
                and self._isolated_database()
                and self.settings.local_dev_auto_identity
                and self.settings.app_origin == "http://localhost:5215")

    def start(self, actor, case_id, expected_revision):
        case = self._case(actor, case_id)
        if expected_revision != case["revision"]:
            raise DomainError("REVISION_CONFLICT", "病例版本已改变，请刷新后重试。", 409)
        existing = self._row(case_id)
        if existing is not None:
            return self.get(actor, case_id)
        if not self._authorized(case_id):
            raise DomainError("AREA_RANKING_MODEL_UNAVAILABLE", "此病例尚未开放真实 AI 排序；当前按模板顺序显示。", 503)
        payload = ranking_input(case)
        with UnitOfWork(self.case_service.engine) as uow:
            inserted = uow.connection.execute(insert(case_area_rankings).values(
                case_id=case_id, status="running", model=self.settings.deepseek_model,
                prompt_version=PROMPT_VERSION, input_json=payload,
            ).on_conflict_do_nothing(index_elements=["case_id"]).returning(case_area_rankings.c.case_id)).scalar_one_or_none()
        if inserted is None:
            return self.get(actor, case_id)
        status, result, error = "failed", None, "MODEL_UNKNOWN"
        gateway = None
        try:
            gateway = DeepSeekGateway(self.settings, paid=True, turn_id=f"area-rank-{case_id}",
                                      prompt_version=PROMPT_VERSION, max_model_calls=1,
                                      max_output_tokens=768)
            proposal = gateway.generate_structured_once(RankingProposal, [
                SystemMessage(content=(
                    "仅为已匹配的排查区域排序，不增删区域。根据用户主诉、故障码、症状工况与区域职责的语义相关性，"
                    "从建议先查到后查排列。每区用一句中文说明与输入的关联；不得推断未检查的事实或宣称确诊。"
                    "若没有足以区分的线索，保持候选原顺序并说明依据不足。只返回 JSON。"
                )),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ])
            result = validate_ranking(proposal, payload["candidates"])
            status, error = "completed", None
        except ModelError as exc:
            error = str(exc)[:80]
        except DomainError as exc:
            error = exc.code
        finally:
            if gateway is not None:
                gateway.close()
            with UnitOfWork(self.case_service.engine) as uow:
                uow.connection.execute(update(case_area_rankings).where(
                    case_area_rankings.c.case_id == case_id).values(
                    status=status, result_json=result, error_code=error,
                    updated_at=func.now()))
        return self.get(actor, case_id)
