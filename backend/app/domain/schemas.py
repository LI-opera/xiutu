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
    workbench_flow: Literal["template-match-v1"] | None = None
    vehicle: VehicleContext
    fault_description: PersistedText = Field(min_length=1, max_length=4000)
    fault_codes: list[ShortCode] = Field(default_factory=list, max_length=30)
    diagnosis_mode: Literal["conservative"] | None = None
    policy_version: PersistedText | None = Field(default=None, min_length=1, max_length=64)
    topic_version: Literal["2.2.0-b01", "2.2.1-b02"] | None = None
    topic_intake: dict[str, str] | None = None

    @field_validator("fault_codes")
    @classmethod
    def normalize_codes(cls, codes):
        return sorted({c.upper() for c in codes})


class StartDiagnosis(InputModel):
    expected_revision: int = Field(ge=0, strict=True)


class ResumeDiagnosis(InputModel):
    expected_revision: int = Field(ge=0, strict=True)
    observation_id: UUID


class RequestReport(InputModel):
    kind: str = Field(pattern="^(progress|final)$")
    expected_revision: int = Field(ge=0, strict=True)


class ReportGate(InputModel):
    available: bool = False
    reason: str | None = "NOT_IMPLEMENTED"
    blocking_items: list[dict] = Field(default_factory=list)


class ActiveRun(InputModel):
    id: UUID
    kind: str
    status: str


class CurrentCheck(InputModel):
    id: UUID
    area_id: UUID
    run_id: UUID
    status: str
    candidate: dict
    validation: dict


class CaseExperience(InputModel):
    category: Literal["continue", "waiting", "completed", "restart", "reference"]
    label: str
    guidance: str
    priority: int


class CaseSnapshot(InputModel):
    id: UUID
    vehicle: VehicleContext
    fault_description: str
    fault_codes: list[str]
    diagnosis_mode: Literal["conservative"] | None = None
    policy_version: str | None = None
    intake_snapshot: dict = Field(default_factory=dict)
    revision: int
    graph_epoch: int
    status: CaseStatus
    corpus_manifest: list = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    active_run: ActiveRun | None = None
    current_check: CurrentCheck | None = None
    experience: CaseExperience
    template_progress: dict | None = None
    report_gate: ReportGate = Field(default_factory=ReportGate)


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


class ClientConfig(InputModel):
    upload_max_bytes: int
    retrieval_profile: Literal["formal", "synthetic"]


class ErrorBody(InputModel):
    code: str
    message: str
    retryable: bool
    trace_id: UUID
    details: dict | None = None


class ErrorEnvelope(InputModel):
    error: ErrorBody


# WP-15 exposes the response shapes already returned by the accepted
# diagnosis/report services.  These models are documentation and output
# validation only; they do not move any authorization or workflow decision
# into the browser.
class EnqueuedAction(InputModel):
    run_id: UUID
    status: str
    parent_run_id: UUID | None = None
    observation_id: UUID | None = None
    supersedes_id: UUID | None = None
    report_id: UUID | None = None
    area_id: UUID | None = None
    current_step_id: UUID | None = None
    case_revision: int | None = None
    graph_epoch: int | None = None
    input_revision: int | None = None
    kind: str | None = None
    mode: str | None = None


class DiagnosisRunSummary(InputModel):
    id: UUID
    status: str
    phase: str
    error_code: str | None = None


class DiagnosisStepView(InputModel):
    id: UUID
    area_id: UUID
    run_id: UUID
    candidate: dict
    validation: dict
    status: str
    required_conditions: dict[str, str] | None = None


class DiagnosisView(InputModel):
    case_id: UUID
    revision: int
    graph_epoch: int
    status: str
    recent_runs: list[DiagnosisRunSummary]
    current_step: DiagnosisStepView | None = None


class AreaConclusionView(InputModel):
    id: UUID
    assessment: str
    content: dict
    created_revision: int
    needs_review: bool


class AreaConclusionResult(InputModel):
    id: UUID
    area_id: UUID
    assessment: str
    content: dict
    created_revision: int


class AreaActivationResult(InputModel):
    area_id: UUID
    mode: Literal["read_only", "generating"]
    revision: int | None = None
    current_step_id: UUID | None = None
    run_id: UUID | None = None
    status: str | None = None
    parent_run_id: UUID | None = None


class DiagnosisAreaView(InputModel):
    id: UUID
    component_key: str
    title: str
    status: str
    current_step_id: UUID | None = None
    conclusion: AreaConclusionView | None = None


class DiagnosisAreaList(InputModel):
    case_id: UUID
    revision: int
    graph_epoch: int
    areas: list[DiagnosisAreaView]


class ObservationView(InputModel):
    id: UUID
    area_id: UUID | None = None
    step_id: UUID | None = None
    kind: str
    payload: dict
    input_schema: dict | None = None
    protocol: dict | None = None
    required_conditions: dict[str, str] | None = None
    created_revision: int
    supersedes_id: UUID | None = None
    correction_reason: str | None = None
    effective: bool


class ObservationList(InputModel):
    case_id: UUID
    revision: int
    items: list[ObservationView]


class WorkbenchActionView(InputModel):
    check_id: str
    title: str
    status: Literal["locked", "not_started", "current", "completed", "needs_review", "not_applicable"]
    available: bool


class WorkbenchComponentView(InputModel):
    component_id: str
    title: str
    status: Literal["locked", "not_started", "current", "completed", "needs_review", "not_applicable"]
    actions: list[WorkbenchActionView]


class WorkbenchAreaView(InputModel):
    area_id: str
    title: str
    priority: int
    priority_reason: str
    status: Literal["locked", "available", "current", "waiting", "abnormal", "completed", "handed_off"]
    completed_checks: int
    required_checks: int
    has_abnormality: bool
    available: bool
    locked_reason: str | None = None
    components: list[WorkbenchComponentView]


class WorkbenchSynthesisView(InputModel):
    status: Literal["in_progress", "handoff", "demo_complete"]
    confirmed_facts: list[str]
    handled_issues: list[str]
    remaining_abnormalities: list[str]
    unchecked_items: list[str]
    next_recommendations: list[str]
    can_generate_demo_summary: bool


class WorkbenchCaseSummary(InputModel):
    id: UUID
    title: str
    mode: str
    status_label: str
    vehicle: dict
    fault_description: str
    fault_codes: list[str]
    symptom_context: dict
    synthetic: bool
    formal_usable: bool


class WorkbenchView(InputModel):
    case_summary: WorkbenchCaseSummary
    areas: list[WorkbenchAreaView]
    selected_area_id: str
    current_component: WorkbenchComponentView | None = None
    current_action: dict | None = None
    saved_facts: list[dict]
    synthesis: WorkbenchSynthesisView


class FinalReportGate(InputModel):
    allowed: bool
    blocking_items: list[dict] = Field(default_factory=list)
    case_revision: int
    graph_epoch: int


class ReportValidity(InputModel):
    valid: bool
    reasons: list[str] = Field(default_factory=list)


class ReportView(InputModel):
    id: UUID
    case_id: UUID
    run_id: UUID
    kind: str
    status: str
    input_revision: int
    graph_epoch: int
    content: dict
    current_validity: ReportValidity
    stale_reason: str | None = None


class ReportList(InputModel):
    case_id: UUID
    items: list[ReportView]
