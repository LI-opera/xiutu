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


class ReferenceUploadResult(BaseModel):
    document_id: str
    version: str
    status: str
    reused: bool
    run_id: str | None


class ReferenceItem(BaseModel):
    document_id: str
    version: str
    title: str
    status: str
    error_code: str | None
    source_kind: str
    content_hash: str
    chars: int
    chunk_count: int | None
    chunker_version: str | None
    vector_fingerprint: str | None
    always_include: list[str]
    requested_areas: list[AreaTarget]
    bound_areas: list[AreaTarget]
    created_at: str
    updated_at: str


class ReferenceList(BaseModel):
    items: list[ReferenceItem]


class ReferenceChunk(BaseModel):
    ordinal: int
    section: str
    subsection: str | None
    text: str
    char_start: int
    char_end: int
    identifiers: list[str]
    searchable: bool
    has_vector: bool


class ReferenceChunkList(BaseModel):
    document_id: str
    version: str
    status: str
    vector_fingerprint: str | None
    items: list[ReferenceChunk]


class TargetArea(BaseModel):
    id: str
    title: str


class TargetTemplate(BaseModel):
    template_id: str
    version: str
    title: str
    areas: list[TargetArea]


class ReferenceTargets(BaseModel):
    templates: list[TargetTemplate]


@router.post("", status_code=202, response_model=ReferenceUploadResult,
             responses={200: {"model": ReferenceUploadResult, "description": "Same content: existing version"}})
def upload_reference(body: ReferenceUpload, request: Request, principal=Depends(writing)):
    status, result = request.app.state.reference_ingest_service.upload(principal.actor_id, body)
    return JSONResponse(status_code=status, content=result)


@router.get("", response_model=ReferenceList)
def list_references(request: Request, principal=Depends(authenticated)):
    return request.app.state.reference_ingest_service.list()


@router.get("/targets", response_model=ReferenceTargets)
def reference_targets(request: Request, principal=Depends(authenticated)):
    """Templates and their areas a manual can be bound to."""
    return request.app.state.reference_ingest_service.targets()


@router.get("/{document_id}/versions/{version}/chunks", response_model=ReferenceChunkList)
def reference_chunks(document_id: str, version: str, request: Request, principal=Depends(authenticated)):
    return request.app.state.reference_ingest_service.chunks(document_id, version)
