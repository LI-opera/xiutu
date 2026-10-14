from typing import Literal

from pydantic import Field

from app.domain.documents import Output
from app.domain.schemas import InputModel, PersistedText


class VehicleScope(InputModel):
    model: PersistedText | None = Field(None, min_length=1, max_length=100)
    year: int | None = Field(None, ge=1886, le=2100, strict=True)
    engine_family: PersistedText | None = Field(None, min_length=1, max_length=100)
    engine_code: PersistedText | None = Field(None, min_length=1, max_length=64)


class SearchInput(InputModel):
    query: PersistedText = Field(min_length=1, max_length=2000)
    vehicle_scope: VehicleScope = Field(default_factory=VehicleScope)
    top_k: int = Field(5, ge=1, le=10, strict=True)


class ReindexInput(InputModel):
    config_version: Literal["e5-small-onnx-v1", "bge-m3-onnx-v1"] | None = None


class ReindexResponse(Output):
    index_id: str
    run_id: str
    status: Literal["building"]


class SearchResponse(Output):
    chunks: list[dict]
    excluded: list[dict]
    trace: dict
