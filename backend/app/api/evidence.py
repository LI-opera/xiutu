from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse

from app.api.dependencies import writing
from app.domain.retrieval import ReindexInput, ReindexResponse, SearchInput, SearchResponse

router = APIRouter(tags=["retrieval"])


@router.post("/api/v2/evidence/search", response_model=SearchResponse)
def search(body: SearchInput, request: Request, principal=Depends(writing)):
    return request.app.state.retrieval_service.search(principal.actor_id, body)


@router.post(
    "/api/v2/documents/{document_id}/versions/{version_id}/reindex",
    status_code=202,
    response_model=ReindexResponse,
)
def reindex(
    document_id: UUID,
    version_id: UUID,
    body: ReindexInput,
    request: Request,
    principal=Depends(writing),
    idempotency_key: str = Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"),
):
    status, response = request.app.state.index_service.reindex(
        principal.actor_id, document_id, version_id, body, idempotency_key
    )
    return JSONResponse(status_code=status, content=response)
