from uuid import UUID
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from app.api.dependencies import authenticated, writing
from app.services.area_analysis_service import MATCHED_SCOPE_ID

router = APIRouter(prefix="/api/v2/cases", tags=["area-analyses"])


class AreaAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)


@router.get("/{case_id}/matched-areas/analysis")
def get_matched_areas_analysis(case_id: UUID, request: Request, principal=Depends(authenticated)):
    return request.app.state.area_analysis_service.get(principal.actor_id, case_id, MATCHED_SCOPE_ID)


@router.post("/{case_id}/matched-areas/analysis")
def start_matched_areas_analysis(case_id: UUID, body: AreaAnalysisRequest, request: Request,
                                 principal=Depends(writing)):
    return request.app.state.area_analysis_service.start(
        principal.actor_id, case_id, MATCHED_SCOPE_ID, body.expected_revision)


@router.get("/{case_id}/areas/{area_id}/analysis")
def get_area_analysis(case_id: UUID, area_id: str, request: Request, principal=Depends(authenticated)):
    return request.app.state.area_analysis_service.get(principal.actor_id, case_id, area_id)


@router.post("/{case_id}/areas/{area_id}/analysis")
def start_area_analysis(case_id: UUID, area_id: str, body: AreaAnalysisRequest, request: Request,
                        principal=Depends(writing)):
    return request.app.state.area_analysis_service.start(
        principal.actor_id, case_id, area_id, body.expected_revision)
