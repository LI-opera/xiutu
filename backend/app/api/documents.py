from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import authenticated, writing
from app.domain.documents import (
    ChunkList,
    DocumentList,
    ReviewInput,
    ReviewResponse,
    UploadResponse,
    VersionResponse,
)
from app.infrastructure.upload import Upload

router = APIRouter(prefix="/api/v2/documents", tags=["documents"])


@router.post(
    "",
    status_code=202,
    response_model=UploadResponse,
    responses={200: {"model": UploadResponse, "description": "Same document/hash/metadata reused"}},
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file", "metadata"],
                        "properties": {
                            "file": {"type": "string", "format": "binary"},
                            "metadata": {
                                "type": "string",
                                "description": "JSON DocumentInput; optional document_id adds a version",
                            },
                        },
                        "additionalProperties": False,
                    }
                }
            },
        }
    },
)
async def upload_document(
    request: Request,
    principal=Depends(writing),
    idempotency_key: str = Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"),
):
    service = request.app.state.document_service
    upload = Upload(service.storage, request.app.state.settings.upload_max_bytes)
    try:
        data = await upload.receive(request)
        status, body = await run_in_threadpool(
            service.upload, principal.actor_id, data, upload, idempotency_key
        )
        return JSONResponse(status_code=status, content=body)
    finally:
        # Always inspect references after transaction exit, including cancellation/ambiguous commit.
        await run_in_threadpool(service.cleanup_candidate, upload.key)


@router.get("", response_model=DocumentList)
def list_documents(
    request: Request,
    principal=Depends(authenticated),
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None, min_length=1, max_length=512),
):
    return request.app.state.document_service.list(principal.actor_id, limit, cursor)


@router.get("/{document_id}/versions/{version_id}", response_model=VersionResponse)
def get_version(
    document_id: UUID, version_id: UUID, request: Request, principal=Depends(authenticated)
):
    return request.app.state.document_service.get(principal.actor_id, document_id, version_id)


@router.get("/{document_id}/versions/{version_id}/chunks", response_model=ChunkList)
def get_chunks(
    document_id: UUID,
    version_id: UUID,
    request: Request,
    principal=Depends(authenticated),
    limit: int = Query(50, ge=1, le=100),
    cursor: int = Query(-1, ge=-1),
):
    return request.app.state.document_service.read_chunks(
        principal.actor_id, document_id, version_id, limit, cursor
    )


@router.post(
    "/{document_id}/versions/{version_id}/review",
    response_model=ReviewResponse,
    responses={202: {"model": ReviewResponse, "description": "Approved and index scheduled"}},
)
def review(
    document_id: UUID,
    version_id: UUID,
    body: ReviewInput,
    request: Request,
    principal=Depends(writing),
    idempotency_key: str = Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"),
):
    status, data = request.app.state.document_service.review(
        principal.actor_id, document_id, version_id, body, idempotency_key
    )
    return JSONResponse(status_code=status, content=data)


@router.get(
    "/{document_id}/versions/{version_id}/content",
    response_class=Response,
    responses={
        200: {
            "description": "Immutable source; PDF attachment with X-Source-Page-Count when parsed",
            "content": {
                "text/plain": {"schema": {"type": "string"}},
                "application/pdf": {"schema": {"type": "string", "format": "binary"}},
            },
        }
    },
)
def content(
    document_id: UUID,
    version_id: UUID,
    request: Request,
    principal=Depends(authenticated),
    page: int | None = Query(None, ge=1),
):
    data, mime, pages = request.app.state.document_service.content(
        principal.actor_id, document_id, version_id, page
    )
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
    }
    if mime == "application/pdf":
        headers["Content-Disposition"] = 'attachment; filename="source.pdf"'
        if pages:
            headers["X-Source-Page-Count"] = str(pages)
    return Response(
        data,
        media_type="text/plain; charset=utf-8" if mime == "text/markdown" else mime,
        headers=headers,
    )
