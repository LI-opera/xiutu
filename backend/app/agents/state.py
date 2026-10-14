"""WP10 candidate-only schema. No model-owned identity or business status."""

from dataclasses import dataclass
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import Field, RootModel, model_validator

from app.domain.measurements import SpecInput
from app.domain.schemas import InputModel, PersistedText

Text = Annotated[PersistedText, Field(min_length=1, max_length=2000)]
Key = Annotated[PersistedText, Field(min_length=1, max_length=100)]


class Reference(InputModel):
    evidence_id: UUID
    document_version_id: UUID


class Claim(InputModel):
    text: Text
    references: list[Reference] = Field(default_factory=list, max_length=12)


class AreaCandidate(InputModel):
    component_key: Key
    title: Key
    rationale: Claim
    children: list["AreaLeaf"] = Field(default_factory=list, max_length=8)


class AreaLeaf(InputModel):
    component_key: Key
    title: Key
    rationale: Claim


class ProposeAreas(InputModel):
    type: Literal["propose_areas"]
    areas: list[AreaCandidate] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def bounded(self):
        if len(self.areas) + sum(len(a.children) for a in self.areas) > 8:
            raise ValueError("At most eight physical candidates across two levels")
        return self


class SpecAssertion(SpecInput):
    spec_id: UUID


class InputSpec(InputModel):
    kind: Literal["choice", "measurement", "composite"]
    choices: list[Claim] = Field(default_factory=list, max_length=8)
    measurements: list[SpecAssertion] = Field(default_factory=list, max_length=8)


class Action(Claim):
    operation: Literal["inspect", "measure", "read", "actuate"]


class Retest(InputModel):
    reason: Claim
    observation_ids: list[UUID] = Field(min_length=1, max_length=10)


class ProposeStep(InputModel):
    type: Literal["propose_step"]
    component_key: Key
    title: Key
    purpose: Claim
    location: Claim | None = None
    prerequisites: list[Claim] = Field(default_factory=list, max_length=12)
    actions: list[Action] = Field(default_factory=list, max_length=12)
    input: InputSpec
    interpretation: list[Claim] = Field(default_factory=list, max_length=12)
    retest: Retest | None = None


class ConcludeArea(InputModel):
    type: Literal["conclude_area"]
    component_key: Key
    finding: Claim
    support_rule_id: UUID | None = None
    conclusion_scope: Literal["contact_fault", "housing_damage"] | None = None
    assessment: Literal[
        "hypothesis", "temporarily_excluded", "unknown", "not_checked", "insufficient_data"
    ]
    observation_ids: list[UUID] = Field(default_factory=list, max_length=20)


class NeedInput(InputModel):
    type: Literal["need_input"]
    missing: list[Text] = Field(min_length=1, max_length=20)


class ToolRequest(InputModel):
    name: Key
    arguments: dict = Field(default_factory=dict, max_length=20)


class RequestTools(InputModel):
    type: Literal["request_tools"]
    calls: list[ToolRequest] = Field(min_length=1, max_length=6)


Proposal = Annotated[
    Union[RequestTools, ProposeAreas, ProposeStep, ConcludeArea, NeedInput],
    Field(discriminator="type"),
]


class ProposalEnvelope(RootModel[Proposal]):
    pass


@dataclass(frozen=True)
class PriorCheck:
    fingerprint: str
    component_key: str
    retest_count: int = 0


@dataclass(frozen=True)
class ProposalContext:
    # Application-only parameter, never deserialized from model payload.
    actor: UUID
    case_id: UUID
    revision: int
    allowed_tools: frozenset[str] = frozenset()
    history: tuple[PriorCheck, ...] = ()


@dataclass
class ProposalTurn:
    # Same object for all validation/repair attempts; persistence belongs to WP11.
    repair_used: bool = False
    attempts: int = 0
