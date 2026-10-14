from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.schemas import InputModel, PersistedText


class DocumentScope(InputModel):
    model: PersistedText | None = Field(default=None, min_length=1, max_length=100)
    year_from: int | None = Field(default=None, ge=1886, le=2100, strict=True)
    year_to: int | None = Field(default=None, ge=1886, le=2100, strict=True)
    engine_family: PersistedText | None = Field(default=None, min_length=1, max_length=100)
    engine_code: PersistedText | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def years(self):
        if self.year_from and self.year_to and self.year_from > self.year_to:
            raise ValueError("Invalid year range")
        return self


class DocumentInput(InputModel):
    document_id: UUID | None = None
    title: PersistedText = Field(min_length=1, max_length=300)
    source_kind: PersistedText = Field(min_length=1, max_length=32)
    source_reference: PersistedText = Field(min_length=1, max_length=2000)
    source_status: Literal["unknown", "verified"] = "unknown"
    license_status: Literal["unknown", "private_use", "permitted"] = "unknown"
    scope: DocumentScope = Field(default_factory=DocumentScope)
    synthetic: bool = Field(strict=True)


class ReviewInput(InputModel):
    decision: Literal["approved", "rejected", "revoked"]
    scope: DocumentScope
    source_status: Literal["unknown", "verified"]
    license_status: Literal["unknown", "private_use", "permitted"]
    review_note: PersistedText = Field(min_length=1, max_length=4000)


class IngestError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


# Output models do not strip whitespace from source text.


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UploadResponse(Output):
    document_id: UUID
    version_id: UUID
    run_id: UUID
    reused: bool


class DocumentSummary(Output):
    id: UUID
    title: str
    source_kind: str
    created_at: str
    latest_version_id: UUID | None


class DocumentList(Output):
    items: list[DocumentSummary]
    next_cursor: str | None


class ReviewResponse(Output):
    document_id: UUID
    version_id: UUID
    review_status: str
    index_status: Literal["index_pending", "building", "ready", "failed", "blocked"]
    index_implemented: Literal[True]
    formal_usable: bool
    active_index_id: str | None
    index_run_id: str | None
    index_exclusion: str | None
    last_index_status: Literal["building", "ready", "failed"] | None
    index_error: dict


class VersionResponse(ReviewResponse):
    sha256: str
    mime: str
    metadata: dict
    parse_status: Literal[
        "pending", "parsing", "review_pending", "needs_ocr", "failed", "cancelled"
    ]
    run_id: UUID
    parser_version: str | None
    chunker_version: str | None
    tokenizer: str | None
    page_count: int | None
    page_issues: list[dict]
    parse_error: dict
    review_history: list[dict]


class ChunkResponse(Output):
    ordinal: int
    heading_path: list[str]
    page_start: int | None
    page_end: int | None
    char_start: int | None
    char_end: int | None
    text: str
    text_hash: str
    kind: str
    locator_json: dict
    token_count: int


class ChunkList(Output):
    items: list[ChunkResponse]
    next_cursor: int | None
