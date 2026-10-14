from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.api.dependencies import authenticated, writing
from app.api.legacy_case_policy import (
    reject_legacy_creation,
    require_template_case,
    retire_legacy_case_route,
)
from app.domain.policies import DomainError
from app.domain.schemas import (
    AreaActivationResult,
    AreaConclusionResult,
    CaseList,
    CaseSnapshot,
    CreateCase,
    DiagnosisAreaList,
    DiagnosisView,
    EnqueuedAction,
    ObservationList,
    ResumeDiagnosis,
    StartDiagnosis,
    WorkbenchView,
)
from app.services.area_service import AreaAction
from app.services.correction_service import CorrectObservation
from app.services.observation_service import SubmitObservation
from app.services.workbench_observation_service import PlanExpand, TopicAnswer, TopicService
from app.services.workbench_templates import is_template
from app.services.workbench_v2_projection import project as project_workbench_v2
from app.topics.dkvb_b01 import bound as dkvb_b01_bound
from app.topics.dkvb_b02 import bound as dkvb_b02_bound
from app.topics.dkvb_v2 import WIRED
from app.topics.dkvb_v2 import bound as dkvb_v2_bound
from app.topics.dkvb_v2 import catalog as dkvb_v2_catalog

router = APIRouter(prefix="/api/v2/cases", tags=["cases"])


@router.get("/{case_id}/workbench-v2")
def get_workbench_v2(case_id: UUID, request: Request,
                     principal=Depends(authenticated)):
    """Version-locked formal case state plus read-only topic definition.

    The observation and diagnosis services remain the only write/routing
    authorities. This endpoint never synthesizes a saved answer from UI state.
    """
    case = request.app.state.case_service.get(principal.actor_id, case_id)
    if is_template(case) or dkvb_b01_bound(case) or dkvb_b02_bound(case):
        return JSONResponse(content=TopicService(request.app.state.case_service).get(principal.actor_id, case_id),
                            headers={"Cache-Control": "no-store"})
    if not dkvb_v2_bound(case):
        raise DomainError("TOPIC_NOT_BOUND", "This case uses the existing formal workbench", 404)
    diagnosis = request.app.state.diagnosis_read_service.current(principal.actor_id, case_id)
    observations = request.app.state.observation_service.list(principal.actor_id, case_id)
    if case["revision"] != diagnosis["revision"] or case["revision"] != observations["revision"]:
        raise DomainError("WORKBENCH_REVISION_CHANGED", "Case changed while loading; retry", 409)
    topic, _ = dkvb_v2_catalog()
    return JSONResponse(content=jsonable_encoder({
        "case": case, "diagnosis": diagnosis, "observations": observations,
        "topic": topic, "view": project_workbench_v2(topic, case, diagnosis, observations), "writable": [
            {"check_id": check, "formal_option_id": formal,
             "question_id": question, "option_id": option}
            for (check, formal), (question, option) in WIRED.items()
        ],
    }), headers={"Cache-Control": "no-store"})


@router.post("/{case_id}/topic-observations")
def save_topic_observation(case_id: UUID, body: TopicAnswer, request: Request,
                           principal=Depends(writing),
                           idempotency_key: str = Header(min_length=1, max_length=128,
                                                         pattern=r"^[A-Za-z0-9._:-]+$")):
    require_template_case(request, principal.actor_id, case_id)
    status, result = TopicService(request.app.state.case_service).save(
        principal.actor_id, case_id, body, idempotency_key)
    return JSONResponse(status_code=status, content=result, headers={"Cache-Control": "no-store"})


@router.post("/{case_id}/topic-observations/{observation_id}/correct")
def correct_topic_observation(case_id: UUID, observation_id: UUID, body: TopicAnswer,
                              request: Request, principal=Depends(writing),
                              idempotency_key: str = Header(min_length=1, max_length=128,
                                                            pattern=r"^[A-Za-z0-9._:-]+$")):
    require_template_case(request, principal.actor_id, case_id)
    status, result = TopicService(request.app.state.case_service).save(
        principal.actor_id, case_id, body, idempotency_key, observation_id)
    return JSONResponse(status_code=status, content=result, headers={"Cache-Control": "no-store"})


@router.post("/{case_id}/topic-plan/expand")
def expand_topic_plan(case_id: UUID, body: PlanExpand, request: Request,
                      principal=Depends(writing),
                      idempotency_key: str = Header(min_length=1, max_length=128,
                                                    pattern=r"^[A-Za-z0-9._:-]+$")):
    require_template_case(request, principal.actor_id, case_id)
    status, result = TopicService(request.app.state.case_service).expand(
        principal.actor_id, case_id, body, idempotency_key)
    return JSONResponse(status_code=status, content=result, headers={"Cache-Control": "no-store"})


@router.get("/{case_id}/topic-observations/history")
def topic_history(case_id: UUID, request: Request, principal=Depends(authenticated),
                  after_revision: int = Query(default=0, ge=0),
                  after_id: UUID | None = None, limit: int = Query(default=100, ge=1, le=200)):
    return TopicService(request.app.state.case_service).history(
        principal.actor_id, case_id, after_revision, str(after_id) if after_id else None, limit)


@router.post("/{case_id}/diagnosis/runs", response_model=EnqueuedAction, status_code=202)
def start_diagnosis(case_id: UUID, body: StartDiagnosis, request: Request,
                    principal=Depends(writing),
                    idempotency_key: str = Header(min_length=1, max_length=128,
                                                  pattern=r"^[A-Za-z0-9._:-]+$")):
    retire_legacy_case_route(request, principal.actor_id, case_id)


@router.post("/{case_id}/diagnosis/resume", status_code=202)
def resume_diagnosis(case_id: UUID, body: ResumeDiagnosis, request: Request,
                     principal=Depends(writing),
                     idempotency_key: str = Header(min_length=1, max_length=128,
                                                   pattern=r"^[A-Za-z0-9._:-]+$")):
    # WP-11's direct saved-UUID recovery remains a trusted internal fixture
    # path. A public caller must submit a validated observation atomically.
    from app.domain.policies import DomainError
    raise DomainError("OBSERVATION_SUBMIT_REQUIRED",
                      "Submit the current check through /observations")


@router.post("/{case_id}/observations", response_model=EnqueuedAction, status_code=202)
def submit_observation(case_id: UUID, body: SubmitObservation, request: Request,
                       principal=Depends(writing),
                       idempotency_key: str = Header(min_length=1, max_length=128,
                                                     pattern=r"^[A-Za-z0-9._:-]+$")):
    retire_legacy_case_route(request, principal.actor_id, case_id)


@router.get("/{case_id}/observations", response_model=ObservationList)
def list_observations(case_id: UUID, request: Request,
                      principal=Depends(authenticated)):
    return request.app.state.observation_service.list(principal.actor_id, case_id)


@router.post("/{case_id}/observations/{observation_id}/correct", response_model=EnqueuedAction, status_code=202)
def correct_observation(case_id: UUID, observation_id: UUID, body: CorrectObservation,
                        request: Request, principal=Depends(writing),
                        idempotency_key: str = Header(min_length=1, max_length=128,
                                                      pattern=r"^[A-Za-z0-9._:-]+$")):
    retire_legacy_case_route(request, principal.actor_id, case_id)


@router.get("/{case_id}/diagnosis", response_model=DiagnosisView)
def current_diagnosis(case_id: UUID, request: Request, principal=Depends(authenticated)):
    return request.app.state.diagnosis_read_service.current(principal.actor_id, case_id)


@router.get("/{case_id}/diagnosis/areas", response_model=DiagnosisAreaList)
def list_diagnosis_areas(case_id: UUID, request: Request,
                         principal=Depends(authenticated)):
    return request.app.state.area_service.list(principal.actor_id, case_id)


@router.get("/{case_id}/workbench-view", response_model=WorkbenchView)
def get_workbench_view(case_id: UUID, request: Request,
                       principal=Depends(authenticated)):
    return request.app.state.workbench_view_service.get(principal.actor_id, case_id)


@router.post("/{case_id}/diagnosis/areas/{area_id}/activate", response_model=AreaActivationResult)
def activate_diagnosis_area(case_id: UUID, area_id: UUID, body: AreaAction,
                            request: Request, principal=Depends(writing),
                            idempotency_key: str = Header(min_length=1, max_length=128,
                                                          pattern=r"^[A-Za-z0-9._:-]+$")):
    retire_legacy_case_route(request, principal.actor_id, case_id)


@router.post("/{case_id}/diagnosis/areas/{area_id}/conclude", response_model=AreaConclusionResult)
def conclude_diagnosis_area(case_id: UUID, area_id: UUID, body: AreaAction,
                            request: Request, principal=Depends(writing),
                            idempotency_key: str = Header(min_length=1, max_length=128,
                                                          pattern=r"^[A-Za-z0-9._:-]+$")):
    retire_legacy_case_route(request, principal.actor_id, case_id)


@router.post("", response_model=CaseSnapshot, status_code=201)
def create_case(
    body: CreateCase,
    request: Request,
    principal=Depends(writing),
    idempotency_key: str = Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"),
):
    reject_legacy_creation(body)
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
