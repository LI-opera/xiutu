"""A case advice draft is not a final repair report or a saved observation."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.schemas import InputModel


class RequestCaseAnalysis(InputModel):
    expected_revision: int = Field(ge=0, strict=True)
    paid_call_acknowledged: bool = False


class AdviceDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=2, max_length=240)
    basis_observation_ids: list[str] = Field(default_factory=list, max_length=12)
    source_ids: list[str] = Field(default_factory=list, max_length=8)
    limit: str = Field(min_length=2, max_length=300)


class AdviceStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["check", "conditional_action", "handoff", "record"]
    action_id: str | None = Field(default=None, max_length=96)
    action: str = Field(min_length=2, max_length=500)
    reason: str | None = Field(default=None, min_length=2, max_length=400)
    recheck_reason: str | None = Field(default=None, min_length=2, max_length=300)
    prerequisites: str | None = Field(default=None, min_length=2, max_length=300)
    basis_observation_ids: list[str] = Field(default_factory=list, max_length=12)
    missing_question_ids: list[str] = Field(default_factory=list, max_length=12)
    question_ids: list[str] = Field(default_factory=list, max_length=12)
    source_ids: list[str] = Field(default_factory=list, max_length=8)
    retest: str | None = Field(default=None, min_length=2, max_length=400)
    stop_condition: str | None = Field(default=None, min_length=2, max_length=300)


class CaseAdviceDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=2, max_length=1200)
    supported_directions: list[AdviceDirection] = Field(default_factory=list, max_length=8)
    unconfirmed_directions: list[str] = Field(default_factory=list, max_length=12)
    steps: list[AdviceStep] = Field(min_length=1, max_length=6)
    retest_plan: str = Field(min_length=2, max_length=700)
    uncertainty: str = Field(min_length=2, max_length=700)
    safety_notice: str = Field(min_length=2, max_length=500)


class ProposedStep(BaseModel):
    """Model proposal. Controlled operation prose is supplied by the server."""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["check", "conditional_action", "handoff"]
    action_id: str | None = Field(default=None, max_length=96)
    action: str | None = Field(default=None, max_length=500)
    prerequisites: str | None = Field(default=None, max_length=300)
    basis_observation_ids: list[str] = Field(default_factory=list, max_length=12)
    source_ids: list[str] = Field(default_factory=list, max_length=8)
    retest: str | None = Field(default=None, max_length=400)
    stop_condition: str | None = Field(default=None, max_length=300)


class CaseAdviceProposal(BaseModel):
    """C04 output contract; old published CaseAdviceDraft remains readable."""
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=2, max_length=1200)
    supported_directions: list[AdviceDirection] = Field(default_factory=list, max_length=8)
    unconfirmed_directions: list[str] = Field(default_factory=list, max_length=12)
    steps: list[ProposedStep] = Field(min_length=1, max_length=6)
    retest_plan: str = Field(min_length=2, max_length=700)
    uncertainty: str = Field(min_length=2, max_length=700)
    safety_notice: str = Field(min_length=2, max_length=500)


class ControlledStepProposal(BaseModel):
    """Only the frozen action ID and effective facts are proposed by the model."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["controlled"]
    action_id: str = Field(min_length=1, max_length=96)
    basis_observation_ids: list[str] = Field(min_length=1, max_length=12)


class FreeStepProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["free"]
    kind: Literal["check", "handoff"]
    action: str = Field(min_length=2, max_length=500)
    prerequisites: str = Field(min_length=2, max_length=300)
    basis_observation_ids: list[str] = Field(default_factory=list, max_length=12)
    source_ids: list[str] = Field(default_factory=list, max_length=8)
    retest: str = Field(min_length=2, max_length=400)
    stop_condition: str = Field(min_length=2, max_length=300)


class CaseAdviceProposalV2(BaseModel):
    """C06 discriminated proposal; published CaseAdviceDraft remains unchanged."""
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=2, max_length=1200)
    supported_directions: list[AdviceDirection] = Field(default_factory=list, max_length=8)
    unconfirmed_directions: list[str] = Field(default_factory=list, max_length=12)
    steps: list[Annotated[ControlledStepProposal | FreeStepProposal,
                          Field(discriminator="type")]] = Field(min_length=1, max_length=6)
    retest_plan: str = Field(min_length=2, max_length=700)
    uncertainty: str = Field(min_length=2, max_length=700)
    safety_notice: str = Field(min_length=2, max_length=500)


class FreeStepProposalV3(BaseModel):
    """A useful check/handoff needs a request, a reason, and actual case context."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["free"]
    kind: Literal["check", "handoff"]
    action: str = Field(min_length=2, max_length=500)
    reason: str = Field(min_length=2, max_length=400)
    basis_observation_ids: list[str] = Field(default_factory=list, max_length=12)
    missing_question_ids: list[str] = Field(default_factory=list, max_length=12)
    source_ids: list[str] = Field(default_factory=list, max_length=8)
    prerequisites: str | None = Field(default=None, min_length=2, max_length=300)
    retest: str | None = Field(default=None, min_length=2, max_length=400)
    stop_condition: str | None = Field(default=None, min_length=2, max_length=300)


class CaseAdviceProposalV3(BaseModel):
    """C07 output contract; older proposals and published advice remain readable."""
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=2, max_length=1200)
    supported_directions: list[AdviceDirection] = Field(default_factory=list, max_length=8)
    unconfirmed_directions: list[str] = Field(default_factory=list, max_length=12)
    steps: list[Annotated[ControlledStepProposal | FreeStepProposalV3,
                          Field(discriminator="type")]] = Field(min_length=1, max_length=6)
    retest_plan: str = Field(min_length=2, max_length=700)
    uncertainty: str = Field(min_length=2, max_length=700)
    safety_notice: str = Field(min_length=2, max_length=500)


class AdviceDirectionV4(AdviceDirection):
    """An observed pattern is not a causal diagnosis or permission to repair."""
    type: Literal["observed_pattern", "technical_cause"]


class RecordStepProposalV4(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["record"]
    question_ids: list[str] = Field(min_length=1, max_length=12)
    request: str = Field(min_length=2, max_length=300)
    reason: str = Field(min_length=2, max_length=400)
    basis_observation_ids: list[str] = Field(default_factory=list, max_length=12)
    missing_question_ids: list[str] = Field(default_factory=list, max_length=12)


class HandoffStepProposalV4(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["handoff"]
    action: str = Field(min_length=2, max_length=500)
    reason: str = Field(min_length=2, max_length=400)
    basis_observation_ids: list[str] = Field(default_factory=list, max_length=12)
    missing_question_ids: list[str] = Field(default_factory=list, max_length=12)
    source_ids: list[str] = Field(default_factory=list, max_length=8)


class CaseAdviceProposalV4(BaseModel):
    """C09 separates interpretation, recording, handoff and frozen operations."""
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=2, max_length=1200)
    supported_directions: list[AdviceDirectionV4] = Field(default_factory=list, max_length=8)
    unconfirmed_directions: list[str] = Field(default_factory=list, max_length=12)
    steps: list[Annotated[ControlledStepProposal | RecordStepProposalV4 | HandoffStepProposalV4,
                          Field(discriminator="type")]] = Field(min_length=1, max_length=6)
    retest_plan: str = Field(min_length=2, max_length=700)
    uncertainty: str = Field(min_length=2, max_length=700)
    safety_notice: str = Field(min_length=2, max_length=500)
    safety_source_ids: list[str] = Field(default_factory=list, max_length=4)


class PublishedAdviceV4(CaseAdviceDraft):
    """A partial result is explicit; rejected sections never become advice."""
    # The proposal still requires a retest plan. A rejected, independent plan
    # is omitted from published content rather than rewritten as model prose.
    retest_plan: str | None = Field(default=None, min_length=2, max_length=700)
    steps: list[AdviceStep] = Field(default_factory=list, max_length=6)
    supported_directions: list[AdviceDirectionV4] = Field(default_factory=list, max_length=8)
    publication: dict = Field(default_factory=dict)


class AdviceDirectionV5(AdviceDirectionV4):
    """Optional frozen editorial references; numbers are rendered by the server."""
    editorial_rule_ids: list[str] = Field(default_factory=list, max_length=8)


class CaseAdviceProposalV5(CaseAdviceProposalV4):
    """C14: interpretation is separate from optional post-treatment planning."""
    supported_directions: list[AdviceDirectionV5] = Field(default_factory=list, max_length=8)
    steps: list[Annotated[ControlledStepProposal | RecordStepProposalV4 | HandoffStepProposalV4,
                          Field(discriminator="type")]] = Field(default_factory=list, max_length=6)
    retest_plan: str | None = Field(default=None, min_length=2, max_length=700)
    safety_notice: str | None = Field(default=None, min_length=2, max_length=500)


class PublishedAdviceV5(PublishedAdviceV4):
    supported_directions: list[AdviceDirectionV5] = Field(default_factory=list, max_length=8)
    safety_notice: str | None = Field(default=None, min_length=2, max_length=500)


class CaseAdviceProposalV6(BaseModel):
    """C16: the model does not author controlled safety or post-treatment text."""
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=2, max_length=1200)
    supported_directions: list[AdviceDirectionV5] = Field(default_factory=list, max_length=8)
    unconfirmed_directions: list[str] = Field(default_factory=list, max_length=12)
    steps: list[Annotated[ControlledStepProposal | RecordStepProposalV4 | HandoffStepProposalV4,
                          Field(discriminator="type")]] = Field(default_factory=list, max_length=6)
    uncertainty: str = Field(min_length=2, max_length=700)


class AdviceDirectionV7(AdviceDirectionV5):
    """Current judgment may identify effective counter-evidence explicitly."""
    counter_observation_ids: list[str] = Field(default_factory=list, max_length=12)


class RecordStepProposalV7(RecordStepProposalV4):
    """An already answered question needs a specific reason to recheck it."""
    recheck_reason: str | None = Field(default=None, min_length=2, max_length=300)


class CaseAdviceProposalV7(CaseAdviceProposalV6):
    """C17: concise judgment, relevant checks, and ordered supported actions."""
    summary: str = Field(min_length=2, max_length=550)
    supported_directions: list[AdviceDirectionV7] = Field(default_factory=list, max_length=8)
    steps: list[Annotated[ControlledStepProposal | RecordStepProposalV7 | HandoffStepProposalV4,
                          Field(discriminator="type")]] = Field(default_factory=list, max_length=6)


class PublishedAdviceV7(PublishedAdviceV5):
    supported_directions: list[AdviceDirectionV7] = Field(default_factory=list, max_length=8)


class OpenAdviceDirection(BaseModel):
    """Model-authored interpretation; references are navigational, not approval gates."""
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=1000)
    explanation: str | None = Field(default=None, max_length=4000)
    basis_observation_ids: list[str] = Field(default_factory=list, max_length=40)
    counter_observation_ids: list[str] = Field(default_factory=list, max_length=40)
    source_ids: list[str] = Field(default_factory=list, max_length=30)


class OpenAdviceMissing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: str = Field(min_length=1, max_length=96)
    missing: str = Field(min_length=1, max_length=1500)
    reason: str | None = Field(default=None, max_length=2000)
    suggestion: str | None = Field(default=None, max_length=2000)


class OpenAdviceStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["check", "repair", "record", "handoff"]
    action: str = Field(min_length=1, max_length=4000)
    reason: str | None = Field(default=None, max_length=3000)
    prerequisites: str | None = Field(default=None, max_length=3000)
    retest: str | None = Field(default=None, max_length=3000)
    stop_condition: str | None = Field(default=None, max_length=3000)
    question_ids: list[str] = Field(default_factory=list, max_length=30)
    basis_observation_ids: list[str] = Field(default_factory=list, max_length=40)
    source_ids: list[str] = Field(default_factory=list, max_length=30)


class CaseAdviceOpenV1(BaseModel):
    """C19 output: bounded JSON shape only; no technical-content approval."""
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=6000)
    directions: list[OpenAdviceDirection] = Field(default_factory=list, max_length=20)
    missing: list[OpenAdviceMissing] = Field(default_factory=list, max_length=40)
    steps: list[OpenAdviceStep] = Field(default_factory=list, max_length=30)
    precautions: list[str] = Field(default_factory=list, max_length=30)
    verification: str | None = Field(default=None, max_length=6000)
    if_unresolved: str | None = Field(default=None, max_length=4000)
    uncertainty: str | None = Field(default=None, max_length=4000)


class OpenAdviceConditionalBranch(BaseModel):
    """A model-authored option shown only after its stated finding is confirmed."""
    model_config = ConfigDict(extra="forbid")
    trigger: str = Field(min_length=1, max_length=1500)
    reason: str | None = Field(default=None, max_length=2000)
    steps: list[OpenAdviceStep] = Field(default_factory=list, max_length=12)


class CaseAdviceOpenV2(CaseAdviceOpenV1):
    """Current steps, conditional branches and unresolved path remain distinct."""
    conditional_branches: list[OpenAdviceConditionalBranch] = Field(default_factory=list, max_length=12)


class AreaAdviceAction(OpenAdviceStep):
    """A readable action heading, independent of vehicle or diagnostic area."""
    title: str = Field(min_length=1, max_length=120,
        description="简短的对象加动作标题，不列异常清单、题号、参数或完整操作过程。")
    action: str = Field(min_length=1, max_length=4000,
        description="具体怎样操作；一个独立目标及其直接关联操作，不用逐个方向处理等空话。")
    prerequisites: str | None = Field(default=None, max_length=3000,
        description="执行前必须满足的实际条件。不能用无关维修仍失败作为已知异常的处理前提。")


class AreaAdviceBranch(OpenAdviceConditionalBranch):
    steps: list[AreaAdviceAction] = Field(default_factory=list, max_length=12)


class AreaAdviceV3(CaseAdviceOpenV2):
    """Used only by area advice; historical snapshots retain their original shape."""
    steps: list[AreaAdviceAction] = Field(default_factory=list, max_length=30)
    conditional_branches: list[AreaAdviceBranch] = Field(default_factory=list, max_length=12)
