from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse

from app.api.dependencies import authenticated, writing
from app.api.legacy_case_policy import retire_legacy_case_route
from app.domain.measurements import (
    BindEvidence,
    CaseSearch,
    CompareInput,
    ComparisonRecord,
    ComparisonView,
    EvidenceView,
    SpecInput,
    SpecReview,
    SpecView,
)
from app.domain.retrieval import SearchResponse

router = APIRouter(tags=["evidence-specifications"])
Key = Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


def reply(result):
    status, body = result
    return JSONResponse(status_code=status, content=body)


@router.post("/api/v2/cases/{case_id}/evidence", status_code=201, response_model=EvidenceView)
def bind(
    case_id: UUID,
    body: BindEvidence,
    request: Request,
    principal=Depends(writing),
    idempotency_key: str = Key,
):
    retire_legacy_case_route(request, principal.actor_id, case_id)


@router.get("/api/v2/evidence/{evidence_id}", response_model=EvidenceView)
def get_evidence(evidence_id: UUID, request: Request, principal=Depends(authenticated)):
    return request.app.state.evidence_service.get(principal.actor_id, evidence_id)


@router.post("/api/v2/cases/{case_id}/evidence/search", response_model=SearchResponse)
def case_search(case_id: UUID, body: CaseSearch, request: Request, principal=Depends(writing)):
    return request.app.state.evidence_service.search(principal.actor_id, case_id, body)


@router.post("/api/v2/measurement-specs", status_code=201, response_model=SpecView)
def create_spec(
    body: SpecInput, request: Request, principal=Depends(writing), idempotency_key: str = Key
):
    return reply(
        request.app.state.evidence_service.create_spec(principal.actor_id, body, idempotency_key)
    )


@router.get("/api/v2/measurement-specs/{spec_id}", response_model=SpecView)
def get_spec(spec_id: UUID, request: Request, principal=Depends(authenticated)):
    return request.app.state.evidence_service.get_spec(principal.actor_id, spec_id)


@router.post("/api/v2/measurement-specs/{spec_id}/review", response_model=SpecView)
def review_spec(
    spec_id: UUID,
    body: SpecReview,
    request: Request,
    principal=Depends(writing),
    idempotency_key: str = Key,
):
    return reply(
        request.app.state.evidence_service.review_spec(
            principal.actor_id, spec_id, body, idempotency_key
        )
    )


@router.post(
    "/api/v2/measurement-specs/{spec_id}/compare", status_code=201, response_model=ComparisonRecord
)
def compare(
    spec_id: UUID,
    body: CompareInput,
    request: Request,
    principal=Depends(writing),
    idempotency_key: str = Key,
):
    return reply(
        request.app.state.evidence_service.compare(
            principal.actor_id, spec_id, body, idempotency_key
        )
    )


@router.get("/api/v2/measurement-comparisons/{comparison_id}", response_model=ComparisonView)
def comparison(comparison_id: UUID, request: Request, principal=Depends(authenticated)):
    return request.app.state.evidence_service.get_comparison(principal.actor_id, comparison_id)
