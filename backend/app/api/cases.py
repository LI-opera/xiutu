from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse

from app.api.dependencies import authenticated, writing
from app.domain.schemas import CaseList, CaseSnapshot, CreateCase
from app.services.workbench_observation_service import PlanExpand, TopicAnswer, TopicService

router = APIRouter(prefix="/api/v2/cases", tags=["cases"])

IdempotencyKey = Annotated[str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]


@router.get("/{case_id}/workbench-v2")
def get_workbench_v2(case_id: UUID, request: Request,
                     principal=Depends(authenticated)):
    """Case state plus its frozen template and the projected view (read only)."""
    return JSONResponse(content=TopicService(request.app.state.case_service).get(principal.actor_id, case_id),
                        headers={"Cache-Control": "no-store"})


@router.post("/{case_id}/topic-observations")
def save_topic_observation(case_id: UUID, body: TopicAnswer, request: Request,
                           idempotency_key: IdempotencyKey, principal=Depends(writing)):
    status, result = TopicService(request.app.state.case_service).save(
        principal.actor_id, case_id, body, idempotency_key)
    return JSONResponse(status_code=status, content=result, headers={"Cache-Control": "no-store"})


@router.post("/{case_id}/topic-observations/{observation_id}/correct")
def correct_topic_observation(case_id: UUID, observation_id: UUID, body: TopicAnswer,
                              request: Request, idempotency_key: IdempotencyKey,
                              principal=Depends(writing)):
    status, result = TopicService(request.app.state.case_service).save(
        principal.actor_id, case_id, body, idempotency_key, observation_id)
    return JSONResponse(status_code=status, content=result, headers={"Cache-Control": "no-store"})


@router.post("/{case_id}/topic-plan/expand")
def expand_topic_plan(case_id: UUID, body: PlanExpand, request: Request,
                      idempotency_key: IdempotencyKey, principal=Depends(writing)):
    status, result = TopicService(request.app.state.case_service).expand(
        principal.actor_id, case_id, body, idempotency_key)
    return JSONResponse(status_code=status, content=result, headers={"Cache-Control": "no-store"})


@router.get("/{case_id}/topic-observations/history")
def topic_history(case_id: UUID, request: Request, principal=Depends(authenticated),
                  after_revision: int = Query(default=0, ge=0),
                  after_id: UUID | None = None, limit: int = Query(default=100, ge=1, le=200)):
    return TopicService(request.app.state.case_service).history(
        principal.actor_id, case_id, after_revision, str(after_id) if after_id else None, limit)


@router.post("", response_model=CaseSnapshot, status_code=201)
def create_case(body: CreateCase, request: Request, idempotency_key: IdempotencyKey,
                principal=Depends(writing)):
    status, body = request.app.state.case_service.create(principal.actor_id, body, idempotency_key)
    return JSONResponse(status_code=status, content=body, headers={"Cache-Control": "no-store"})


@router.get("", response_model=CaseList)
def list_cases(
    request: Request,
    principal=Depends(authenticated),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None, min_length=1, max_length=512),
    scope: Literal['all', 'daily', 'test'] = Query(default='all'),
):
    return request.app.state.case_service.list(principal.actor_id, limit, cursor, scope=scope)


@router.get("/{case_id}", response_model=CaseSnapshot)
def get_case(case_id: UUID, request: Request, principal=Depends(authenticated)):
    return request.app.state.case_service.get(principal.actor_id, case_id)
