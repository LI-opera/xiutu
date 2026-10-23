from pydantic import Field

from app.domain.schemas import InputModel

ACTIVE = {"queued", "running", "cancel_requested"}
TERMINAL = {"succeeded", "failed", "cancelled", "superseded", "waiting_input"}


class NoOpInput(InputModel):
    seconds: float = Field(default=0, ge=0, le=300, allow_inf_nan=False)
