"""Structured output of an area analysis (the JSON the model must return).

Class names and docstrings are part of the JSON schema sent to the model; keep them stable.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    # Kept optional so earlier saved results still validate; new advice leaves them empty.
    verification: str | None = Field(default=None, max_length=6000,
        description="留空。各行动的复检写在其 retest；处理后的实际复检由用户另行记录。")
    if_unresolved: str | None = Field(default=None, max_length=4000,
        description="留空。当前行动完成后仍未解决的去向写入 conditional_branches 或 directions。")
