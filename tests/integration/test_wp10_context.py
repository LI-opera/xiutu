"""Extra synthetic regression: a real quote may still lose its negation context."""

from test_document_ingest import docrig as docrig
from test_evidence_measurement import indexed_rig as indexed_rig
from test_wp10_proposals import prepare


def test_quote_cannot_drop_negation(indexed_rig):
    _, _, context, service, cite = prepare(
        indexed_rig, "SYNTHETIC ONLY\n不能认定P01正常。\n".encode()
    )
    quoted = cite("P01正常。")
    result = service.validate(
        context,
        dict(
            type="propose_areas", areas=[dict(component_key="P01", title="P01", rationale=quoted)]
        ),
    )
    assert not result["accepted"], result
