"""Owned, user-requested case advice separate from final report routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse

from app.api.dependencies import authenticated, writing
from app.domain.case_analysis import RequestCaseAnalysis
from app.api.legacy_case_policy import retire_legacy_case_route

router = APIRouter(prefix="/api/v2/cases/{case_id}/analyses", tags=["case-analyses"])


@router.get("")
def list_case_analyses(case_id: UUID, request: Request, principal=Depends(authenticated)):
    return request.app.state.case_analysis_read_service.list(principal.actor_id, case_id)


@router.get("/preflight")
def preflight_case_analysis(case_id: UUID, request: Request, principal=Depends(authenticated)):
    retire_legacy_case_route(request, principal.actor_id, case_id)


@router.get("/{analysis_id}")
def get_case_analysis(case_id: UUID, analysis_id: UUID, request: Request,
                      principal=Depends(authenticated)):
    return request.app.state.case_analysis_read_service.get(principal.actor_id, case_id, analysis_id)


@router.get("/{analysis_id}/diagnostic")
def get_case_analysis_diagnostic(case_id: UUID, analysis_id: UUID, request: Request,
                                 principal=Depends(authenticated)):
    return JSONResponse(content=request.app.state.case_analysis_read_service.diagnostic(
        principal.actor_id, case_id, analysis_id), headers={"Cache-Control": "no-store"})


@router.post("", status_code=202)
def request_case_analysis(case_id: UUID, body: RequestCaseAnalysis, request: Request,
                          principal=Depends(writing),
                          idempotency_key: str = Header(min_length=1, max_length=128,
                                                        pattern=r"^[A-Za-z0-9._:-]+$")):
    retire_legacy_case_route(request, principal.actor_id, case_id)
