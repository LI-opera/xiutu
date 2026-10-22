import re
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from app.domain.enums import CaseStatus


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


ShortCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9-]+$"
    ),
]


def reject_nul(value: str) -> str:
    if "\x00" in value:
        raise ValueError("NUL is not supported in persisted text")
    return value


PersistedText = Annotated[str, AfterValidator(reject_nul)]


class VehicleContext(InputModel):
    brand: PersistedText | None = Field(default=None, min_length=1, max_length=100)
    model: PersistedText = Field(min_length=1, max_length=100)
    year: int | None = Field(default=None, ge=1886, le=2100, strict=True)
    engine_code: PersistedText | None = Field(default=None, min_length=1, max_length=64)
    engine_family: PersistedText | None = Field(default=None, min_length=1, max_length=100)
    vin: str | None = Field(default=None, min_length=17, max_length=17)

    @field_validator("engine_code", mode="before")
    @classmethod
    def optional_engine_code(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("vin")
    @classmethod
    def normalize_vin(cls, value):
        if value is not None:
            value = value.upper()
            if not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", value):
                raise ValueError("Invalid VIN")
        return value


class CreateCase(InputModel):
    workbench_flow: Literal["template-match-v1"]
    vehicle: VehicleContext
    fault_description: PersistedText = Field(min_length=1, max_length=4000)
    fault_codes: list[ShortCode] = Field(default_factory=list, max_length=30)
    topic_intake: dict[str, str] | None = None

    @field_validator("fault_codes")
    @classmethod
    def normalize_codes(cls, codes):
        return sorted({c.upper() for c in codes})


class CaseExperience(InputModel):
    category: Literal["continue", "waiting", "completed", "reference"]
    label: str
    guidance: str
    priority: int


class CaseSnapshot(InputModel):
    id: UUID
    vehicle: VehicleContext
    fault_description: str
    fault_codes: list[str]
    intake_snapshot: dict = Field(default_factory=dict)
    revision: int
    status: CaseStatus
    created_at: datetime
    updated_at: datetime
    experience: CaseExperience
    template_progress: dict | None = None


class CaseList(InputModel):
    items: list[CaseSnapshot]
    next_cursor: str | None


class LoginInput(InputModel):
    token: str = Field(min_length=32, max_length=512, repr=False)


class AuthSession(InputModel):
    actor_id: UUID
    csrf_token: str
    expires_in: int


class LogoutResponse(InputModel):
    logged_out: Literal[True] = True


class ErrorBody(InputModel):
    code: str
    message: str
    retryable: bool
    trace_id: UUID
    details: dict | None = None


class ErrorEnvelope(InputModel):
    error: ErrorBody
