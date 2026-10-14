from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from app.api.dependencies import authenticated, writing
from app.domain.schemas import EnqueuedAction, FinalReportGate, ReportList, ReportView, RequestReport
from app.api.legacy_case_policy import retire_legacy_case_route

router = APIRouter(prefix="/api/v2/cases/{case_id}/reports", tags=["reports"])


@router.get("/gate", response_model=FinalReportGate)
def report_gate(case_id: UUID, request: Request, principal=Depends(authenticated)):
    return request.app.state.report_read_service.gate(principal.actor_id, case_id)


@router.post("", response_model=EnqueuedAction, status_code=202)
def request_report(case_id: UUID, body: RequestReport, request: Request,
                   principal=Depends(writing),
                   idempotency_key: str = Header(min_length=1, max_length=128,
                                                 pattern=r"^[A-Za-z0-9._:-]+$")):
    retire_legacy_case_route(request, principal.actor_id, case_id)


@router.get("", response_model=ReportList)
def list_reports(case_id: UUID, request: Request, principal=Depends(authenticated)):
    return request.app.state.report_read_service.list(principal.actor_id, case_id)


@router.get("/{report_id}", response_model=ReportView)
def get_report(case_id: UUID, report_id: UUID, request: Request,
               principal=Depends(authenticated)):
    return request.app.state.report_read_service.get(principal.actor_id, case_id, report_id)
