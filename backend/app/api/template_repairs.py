from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.dependencies import authenticated, writing

router = APIRouter(prefix="/api/v2/cases", tags=["template-repairs"])


class LifecycleInput(BaseModel):
    expected_revision: int = Field(ge=0)
    closed: bool


@router.post("/{case_id}/template-lifecycle")
def lifecycle(case_id: UUID, body: LifecycleInput, request: Request, principal=Depends(writing)):
    from app.services.template_case_history import set_closed
    return set_closed(request.app.state.case_service.engine, principal.actor_id, case_id, body.expected_revision, body.closed)


class RepairInput(BaseModel):
    expected_revision: int = Field(ge=0)
    area_id: str = Field(min_length=1, max_length=80)
    repair_action: str = Field(min_length=1, max_length=4000)
    repair_note: str = Field(default="", max_length=4000)


# One question re-answered after the repair; saved as an ordinary record.
class RecheckInput(BaseModel):
    question_id: str = Field(min_length=1, max_length=80)
    option_ids: list[str] = Field(min_length=1, max_length=20)
    fields: dict[str, object] = Field(default_factory=dict)
    note: str = Field(default="", max_length=2000)
    unavailable_reason: str = Field(default="", max_length=2000)


class RetestInput(BaseModel):
    expected_revision: int = Field(ge=0)
    retest_condition: str = Field(pattern="^(same|different|unavailable)$")
    retest_outcome: str = Field(pattern="^(resolved|persists|uncertain)$")
    retest_evidence: str = Field(min_length=1, max_length=4000)
    next_area_id: str | None = None
    observations: list[RecheckInput] = Field(default_factory=list, max_length=40)


@router.get("/{case_id}/template-repairs")
def get_repairs(case_id: UUID, request: Request, principal=Depends(authenticated)):
    return request.app.state.template_repair_service.get(principal.actor_id, case_id)


@router.post("/{case_id}/template-repairs")
def save_repair(case_id: UUID, body: RepairInput, request: Request, principal=Depends(writing)):
    return request.app.state.template_repair_service.record_repair(principal.actor_id, case_id, body)


@router.post("/{case_id}/template-repairs/{round_id}/retest")
def save_retest(case_id: UUID, round_id: UUID, body: RetestInput, request: Request,
                principal=Depends(writing)):
    return request.app.state.template_repair_service.record_retest(principal.actor_id, case_id, round_id, body)
