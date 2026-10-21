"""Write requests reject unknown fields; the local-only embedding flag accepts its documented text."""
import pytest
from app.api.area_analyses import AreaAnalysisRequest
from app.api.template_repairs import RecheckInput, RetestInput
from app.config import Settings
from app.services.workbench_observation_service import TopicAnswer
from pydantic import ValidationError

RETEST = {"expected_revision": 4, "retest_condition": "same", "retest_outcome": "persists",
          "retest_evidence": "仍增压不足"}


@pytest.mark.parametrize("model,body", [
    (RetestInput, RETEST),
    (RecheckInput, {"question_id": "AIR-01", "option_ids": ["normal"]}),
    (TopicAnswer, {"expected_revision": 1, "topic_version": "v", "question_id": "AIR-01"}),
    (AreaAnalysisRequest, {"expected_revision": 1}),
])
def test_unknown_fields_fail_instead_of_being_dropped(model, body):
    model.model_validate(body)
    with pytest.raises(ValidationError):
        model.model_validate({**body, "unexpected": True})


def test_local_only_embedding_flag_accepts_true_text_and_nothing_else():
    assert Settings(_env_file=None, embedding_local_files_only="true").embedding_local_files_only is True
    assert Settings(_env_file=None, embedding_local_files_only=" TRUE ").embedding_local_files_only is True
    with pytest.raises(ValidationError):
        Settings(_env_file=None, embedding_local_files_only="false")
