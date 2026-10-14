from uuid import UUID

from pydantic import Field

from app.domain.enums import RunStatus
from app.domain.schemas import InputModel

ACTIVE = {"queued", "running", "cancel_requested"}
TERMINAL = {"succeeded", "failed", "cancelled", "superseded", "waiting_input"}


class RetryInput(InputModel):
    expected_revision: int | None = Field(default=None, ge=0, strict=True)


class RunSnapshot(InputModel):
    id: UUID
    case_id: UUID | None
    kind: str
    status: RunStatus
    attempt: int
    max_attempts: int
    parent_run_id: UUID | None
    error: dict
    usage: dict


class RunAction(InputModel):
    run_id: UUID
    status: RunStatus
    parent_run_id: UUID | None = None


class NoOpInput(InputModel):
    seconds: float = Field(default=0, ge=0, le=300, allow_inf_nan=False)
