"""Application-only reviewed mappings. Never deserialize these from model messages."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from app.domain.schemas import InputModel, PersistedText

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class TrustedConclusionRule(InputModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    format_version: Literal[1] = 1
    rule_id: UUID
    owner_id: UUID
    case_id: UUID
    profile: Literal["formal", "synthetic"]
    component_key: Annotated[PersistedText, Field(min_length=1, max_length=100)]
    kind: Literal["connector_detached_hypothesis", "housing_intact_comparison_exclusion"]
    evidence_id: UUID
    document_version_id: UUID
    quote_sha256: Digest
    authorization_epoch: int = Field(ge=0)
    reviewed_by: UUID
    reviewed_at: AwareDatetime
    engine: Literal["off", "on"]
    spec_id: UUID | None = None
    spec_definition_sha256: Digest | None = None

    @model_validator(mode="after")
    def bounded_mapping(self):
        exclusion = self.kind == "housing_intact_comparison_exclusion"
        if exclusion != (self.spec_id is not None and self.spec_definition_sha256 is not None):
            raise ValueError("Exclusion requires one exact reviewed specification")
        if not exclusion and (self.spec_id is not None or self.spec_definition_sha256 is not None):
            raise ValueError("Hypothesis template has no numerical inference")
        if self.reviewed_at > datetime.now(self.reviewed_at.tzinfo):
            raise ValueError("Review timestamp cannot be in the future")
        return self
