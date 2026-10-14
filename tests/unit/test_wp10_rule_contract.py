"""Application mapping and model candidate are distinct schemas."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from app.agents.conclusion_rules import TrustedConclusionRule
from app.agents.state import ProposalEnvelope
from pydantic import ValidationError


def mapping():
    return dict(
        rule_id=uuid4(),
        owner_id=uuid4(),
        case_id=uuid4(),
        profile="synthetic",
        component_key="ANY-COMPONENT",
        kind="connector_detached_hypothesis",
        evidence_id=uuid4(),
        document_version_id=uuid4(),
        quote_sha256="a" * 64,
        authorization_epoch=1,
        reviewed_by=uuid4(),
        reviewed_at=datetime.now(timezone.utc),
        engine="off",
    )


def test_mapping_is_immutable_and_not_candidate_authority():
    rule = TrustedConclusionRule(**mapping())
    with pytest.raises(ValidationError):
        rule.component_key = "forged"
    body = dict(
        type="conclude_area",
        component_key="ANY-COMPONENT",
        finding=dict(text="synthetic"),
        assessment="hypothesis",
        support_rule_id=str(rule.rule_id),
        conclusion_scope="contact_fault",
    )
    assert ProposalEnvelope.model_validate(body)
    for extra in [
        {"reviewed": True},
        {"support_rule": rule.model_dump(mode="json")},
        {"premises_satisfied": True},
    ]:
        with pytest.raises(ValidationError):
            ProposalEnvelope.model_validate(dict(body, **extra))


@pytest.mark.parametrize(
    "change",
    [
        {"kind": "housing_intact_comparison_exclusion"},
        {"reviewed_at": "yesterday"},
        {"quote_sha256": "wrong"},
        {"spec_id": str(uuid4())},
    ],
)
def test_invalid_mapping_rejected(change):
    with pytest.raises(ValidationError):
        TrustedConclusionRule(**dict(mapping(), **change))
