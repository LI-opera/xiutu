import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BeforeValidator, ConfigDict, Field, model_validator

from app.domain.documents import Output
from app.domain.schemas import InputModel, PersistedText

UNITS = {
    "temperature": {"C", "F"},
    "pressure": {"Pa", "kPa", "bar"},
    "voltage": {"V", "mV"},
    "resistance": {"ohm", "kohm"},
}


def decimal_text(value):
    if (
        not isinstance(value, str)
        or len(value) > 80
        or not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]{1,2})?", value)
    ):
        raise ValueError("Decimal string required")
    d = Decimal(value)
    if (
        not d.is_finite()
        or len(d.as_tuple().digits) > 30
        or abs(d.as_tuple().exponent) > 30
        or abs(d.adjusted()) > 30
    ):
        raise ValueError("Decimal outside supported precision")
    return value


DecimalText = Annotated[str, BeforeValidator(decimal_text)]


class BindEvidence(InputModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    chunk_id: UUID
    document_version_id: UUID
    index_id: UUID
    start: int = Field(ge=0, strict=True)
    end: int = Field(gt=0, strict=True)
    quote: PersistedText = Field(min_length=1, max_length=20000)

    @model_validator(mode="after")
    def interval(self):
        if self.end <= self.start or len(self.quote) != self.end - self.start:
            raise ValueError("Quote offsets do not match")
        return self


class SpecInput(InputModel):
    evidence_id: UUID
    supersedes_id: UUID | None = None
    component_key: PersistedText = Field(min_length=1, max_length=100)
    quantity: Literal["temperature", "pressure", "voltage", "resistance"]
    unit: Literal["C", "F", "Pa", "kPa", "bar", "V", "mV", "ohm", "kohm"]
    lower: DecimalText | None = None
    upper: DecimalText | None = None
    lower_inclusive: bool = Field(default=False, strict=True)
    upper_inclusive: bool = Field(default=False, strict=True)
    conditions: dict[PersistedText, PersistedText] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def range(self):
        if self.unit not in UNITS[self.quantity]:
            raise ValueError("Quantity/unit mismatch")
        if self.lower is None and self.upper is None:
            raise ValueError("A bound is required")
        if (self.lower is None and self.lower_inclusive) or (
            self.upper is None and self.upper_inclusive
        ):
            raise ValueError("Infinite bound cannot be inclusive")
        if self.lower is not None and self.upper is not None:
            a, b = Decimal(self.lower), Decimal(self.upper)
            if a > b or (a == b and not (self.lower_inclusive and self.upper_inclusive)):
                raise ValueError("Empty or reversed range")
        validate_conditions(self.conditions)
        return self


class CompareInput(InputModel):
    value: DecimalText | None = None
    quantity: Literal["temperature", "pressure", "voltage", "resistance"]
    unit: Literal["C", "F", "Pa", "kPa", "bar", "V", "mV", "ohm", "kohm"]
    conditions: dict[PersistedText, PersistedText] = Field(default_factory=dict, max_length=20)

    @model_validator(mode="after")
    def conditions_valid(self):
        validate_conditions(self.conditions)
        return self


def validate_conditions(values):
    if any(
        not k.strip() or not v.strip() or len(k) > 100 or len(v) > 300 for k, v in values.items()
    ):
        raise ValueError("Invalid condition")


class SpecReview(InputModel):
    decision: Literal["approved", "rejected", "revoked"]
    note: PersistedText = Field(min_length=1, max_length=4000)


class CaseSearch(InputModel):
    query: PersistedText = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10, strict=True)


# Public output envelopes keep immutable snapshot and current validity distinct.



class EvidenceView(Output):
    evidence_id: UUID
    snapshot: dict
    current_validity: dict
    synthetic: bool
    source_content_url: str | None
    source_access: "EvidenceSourceAccess"


class EvidenceSourceAccess(Output):
    kind: Literal["text", "pdf"]
    status: Literal["available", "needs_ocr", "page_missing", "mapping_missing"]
    page: int | None = None
    page_count: int | None = None
    needs_ocr: bool = False
    content_url: str | None = None
    page_image_url: str | None = None
    page_image_status: Literal["available", "unavailable", "not_applicable"]


class SpecView(Output):
    spec: dict
    source: EvidenceView
    review_history: list[dict]


class ComparisonRecord(Output):
    id: UUID
    spec_id: UUID
    case_id: UUID
    result: dict
    needs_review: bool
    review_reasons: list[str]
    created_at: datetime


class ComparisonView(Output):
    comparison: ComparisonRecord
    current_validity: dict
