import numpy as np
import pytest
from app.config import Settings
from app.domain.retrieval import SearchInput
from app.infrastructure.embedding_gateway import EmbeddingError, validate_vectors
from app.retrieval.eligibility import applicability
from app.retrieval.sparse import rank, tokens
from pydantic import ValidationError


@pytest.mark.parametrize(
    "value",
    [[[0] * 383], [[float("nan")] * 384], [[float("inf")] * 384], [[0] * 384], [[1] * 384] * 2],
)
def test_bad_vectors(value):
    with pytest.raises(EmbeddingError):
        validate_vectors(value, 1)


def test_vectors_normalized():
    assert np.isclose(np.linalg.norm(validate_vectors([[1] * 384], 1)[0]), 1)


def test_dtc_and_scope():
    assert "p00b700" in tokens("P00B700 冷却液")
    assert rank("P0301", ["P0300", "第一缸 P0301"])[0][0] == 1
    assert (
        applicability({"engine_family": "EA888"}, {"engine_code": "EA888"})["status"] == "unknown"
    )
    assert applicability({"engine_code": "AAA"}, {"engine_code": "BBB"})["status"] == "mismatch"
    assert applicability({"year_from": 2020}, {"year": 2019})["status"] == "mismatch"


def test_profile_cannot_be_request_option():
    with pytest.raises(ValidationError):
        SearchInput(query="test", profile="synthetic")
    with pytest.raises(ValidationError):
        Settings(retrieval_profile="synthetic", app_mode="development", database_url=None)
