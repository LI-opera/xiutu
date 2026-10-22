from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import authenticated, writing

router = APIRouter(prefix="/api/v2/area-references", tags=["area-references"])


class ReferenceVehicle(BaseModel):
    """The vehicle a manual applies to; analyses only read manuals of the case's vehicle."""
    model_config = ConfigDict(extra="forbid")
    brand: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=1950, le=2100)
    engine_code: str = Field(min_length=1, max_length=64)


class StoredVehicle(BaseModel):
    brand: str | None
    model: str | None
    year: int | None
    engine_code: str | None


class ReferenceUpload(BaseModel):
    """A new Markdown manual. Nothing ties it to a template or an area."""
    model_config = ConfigDict(extra="forbid")
    document_id: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    filename: str = Field(default="", max_length=255)
    content: str = Field(min_length=1, max_length=2_000_000)
    vehicle: ReferenceVehicle
    always_include: list[str] = Field(default_factory=list, max_length=50)


class ReferenceVersionUpload(BaseModel):
    """A new version of an existing manual; title, vehicle and always-sent sections carry over."""
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(default="", max_length=255)
    content: str = Field(min_length=1, max_length=2_000_000)


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
    vehicle: StoredVehicle
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


class KnownVehicles(BaseModel):
    vehicles: list[StoredVehicle]


@router.post("", status_code=202, response_model=ReferenceUploadResult,
             responses={200: {"model": ReferenceUploadResult, "description": "Same content: existing version"}})
def upload_reference(body: ReferenceUpload, request: Request, principal=Depends(writing)):
    status, result = request.app.state.reference_ingest_service.upload(principal.actor_id, body)
    return JSONResponse(status_code=status, content=result)


@router.get("", response_model=ReferenceList)
def list_references(request: Request, principal=Depends(authenticated)):
    return request.app.state.reference_ingest_service.list()


@router.get("/vehicles", response_model=KnownVehicles)
def known_vehicles(request: Request, principal=Depends(authenticated)):
    """Vehicles already known from templates and manuals, suggested while typing."""
    return request.app.state.reference_ingest_service.vehicles()


@router.post("/{document_id}/versions", status_code=202, response_model=ReferenceUploadResult,
             responses={200: {"model": ReferenceUploadResult, "description": "Same content: existing version"}})
def upload_reference_version(document_id: str, body: ReferenceVersionUpload, request: Request,
                             principal=Depends(writing)):
    status, result = request.app.state.reference_ingest_service.add_version(principal.actor_id, document_id, body)
    return JSONResponse(status_code=status, content=result)


@router.get("/{document_id}/versions/{version}/chunks", response_model=ReferenceChunkList)
def reference_chunks(document_id: str, version: str, request: Request, principal=Depends(authenticated)):
    return request.app.state.reference_ingest_service.chunks(document_id, version)
