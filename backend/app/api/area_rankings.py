from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.dependencies import authenticated, writing

router = APIRouter(prefix="/api/v2/cases", tags=["area-rankings"])


class RankRequest(BaseModel):
    expected_revision: int = Field(ge=0)


@router.get("/{case_id}/area-ranking")
def get_area_ranking(case_id: UUID, request: Request, principal=Depends(authenticated)):
    return request.app.state.area_ranking_service.get(principal.actor_id, case_id)


@router.post("/{case_id}/area-ranking")
def start_area_ranking(case_id: UUID, body: RankRequest, request: Request,
                       principal=Depends(writing)):
    return request.app.state.area_ranking_service.start(
        principal.actor_id, case_id, body.expected_revision)
