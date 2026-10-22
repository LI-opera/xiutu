from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import authenticated, writing

router = APIRouter(prefix="/api/v2/area-references", tags=["area-references"])


class AreaTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_id: str = Field(min_length=1, max_length=100)
    template_version: str = Field(min_length=1, max_length=32)
    area_id: str = Field(min_length=1, max_length=80)


class ReferenceUpload(BaseModel):
    """A Markdown manual for one or more workbench areas. Same document_id adds a version."""
    model_config = ConfigDict(extra="forbid")
    document_id: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    filename: str = Field(default="", max_length=255)
    content: str = Field(min_length=1, max_length=2_000_000)
    areas: list[AreaTarget] = Field(min_length=1, max_length=50)
    always_include: list[str] = Field(default_factory=list, max_length=50)


@router.post("", status_code=202)
def upload_reference(body: ReferenceUpload, request: Request, principal=Depends(writing)):
    status, result = request.app.state.reference_ingest_service.upload(principal.actor_id, body)
    return JSONResponse(status_code=status, content=result)


@router.get("")
def list_references(request: Request, principal=Depends(authenticated)):
    return request.app.state.reference_ingest_service.list()


@router.get("/{document_id}/versions/{version}/chunks")
def reference_chunks(document_id: str, version: str, request: Request, principal=Depends(authenticated)):
    return request.app.state.reference_ingest_service.chunks(document_id, version)
