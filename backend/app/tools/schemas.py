from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.measurements import DecimalText, validate_conditions
from app.domain.retrieval import SearchInput, VehicleScope
from app.domain.schemas import InputModel, PersistedText


class ContextInput(InputModel):
    chunk_id: UUID
    document_version_id: UUID
    neighbors: int = Field(default=0, ge=0, le=2, strict=True)


class SpecQuery(InputModel):
    component_key: PersistedText = Field(min_length=1, max_length=100)
    quantity: Literal["temperature", "pressure", "voltage", "resistance"]
    vehicle_scope: VehicleScope = Field(default_factory=VehicleScope)


class MeasurementInput(InputModel):
    spec_id: UUID
    value: DecimalText | None = None
    unit: Literal["C", "F", "Pa", "kPa", "bar", "V", "mV", "ohm", "kohm"]
    conditions: dict[PersistedText, PersistedText] = Field(default_factory=dict, max_length=20)

    @model_validator(mode="after")
    def valid_conditions(self):
        validate_conditions(self.conditions)
        return self


class ObservationInput(InputModel):
    area_id: UUID | None = None
    at_revision: int = Field(ge=0, strict=True)


class StrictOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChunkResult(StrictOutput):
    chunk_id: UUID
    document_version_id: UUID
    index_id: UUID
    text: str = Field(max_length=20000)
    content_hash: str = Field(pattern="^[0-9a-f]{64}$")
    locator: dict
    applicability: dict


class SearchData(StrictOutput):
    empty: bool
    chunks: list[ChunkResult] = Field(max_length=10)


class ContextData(StrictOutput):
    empty: bool
    chunks: list[ChunkResult] = Field(max_length=5)


class SpecResult(StrictOutput):
    spec_id: UUID
    evidence_id: UUID
    version: int
    definition: dict


class SpecData(StrictOutput):
    empty: bool
    candidates: list[SpecResult] = Field(max_length=20)


class CompareData(StrictOutput):
    comparison_id: UUID
    spec_id: UUID
    spec_version: int
    outcome: str
    input: dict
    converted: str | None
    converted_exact: bool | None
    synthetic: bool
    diagnosis: Literal[False] = False


class ObservationResult(StrictOutput):
    id: UUID
    area_id: UUID | None
    step_id: UUID | None
    kind: str
    payload: dict
    created_revision: int
    supersedes_id: UUID | None


class ObservationData(StrictOutput):
    empty: bool
    observations: list[ObservationResult] = Field(max_length=50)


class ToolError(StrictOutput):
    code: str
    message: str
    retryable: bool = False


class Envelope(StrictOutput):
    ok: bool
    data: dict | None
    error: ToolError | None
    provenance: list[dict] = Field(default_factory=list, max_length=50)
    duration_ms: int = Field(ge=0)


INPUTS = dict(
    search_manuals=SearchInput,
    get_evidence_context=ContextInput,
    get_measurement_spec=SpecQuery,
    compare_measurement=MeasurementInput,
    get_case_observations=ObservationInput,
)
OUTPUTS = dict(
    search_manuals=SearchData,
    get_evidence_context=ContextData,
    get_measurement_spec=SpecData,
    compare_measurement=CompareData,
    get_case_observations=ObservationData,
)
