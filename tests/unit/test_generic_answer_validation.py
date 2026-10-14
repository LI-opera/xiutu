import pytest
from app.domain.policies import DomainError
from app.services.workbench_b01_service import TopicAnswer, TopicService
from app.services.workbench_topic_workflow import ObservationWorkflow, workflow_for


def inputs(value):
    # Deliberate ID collision: a new topic must not inherit the old 0.5 bar rule.
    q = {"id": "AIR-14", "answer_kind": "numeric_with_choice", "stage": "inspection",
         "options": [{"id": "within_limit", "outcome": "normal"}],
         "fields": [{"id": "pressureBar", "type": "number", "unit": "bar", "label": "读数",
                     "minimum": -2, "maximum": 5, "required_when_options": ["within_limit"]}]}
    topic = {"version": "unrelated-1", "questions": [q]}
    plan = {"capture_batches": {}, "rounds": []}
    answer = TopicAnswer(expected_revision=0, topic_version=topic["version"], question_id=q["id"],
                         option_ids=["within_limit"], fields={"pressureBar": {"value": value, "unit": "bar"}})
    return topic, plan, answer


@pytest.mark.parametrize("value", [0, -1, 1.2, 5])
def test_new_topic_uses_declared_numeric_range_not_legacy_threshold(value):
    topic, plan, answer = inputs(value)
    assert TopicService._validate_answer(topic, plan, [], answer)[1]["pressureBar"]["value"] == value


@pytest.mark.parametrize("value", [-3, 6, True, float("nan"), float("inf")])
def test_common_numeric_validation_rejects_invalid_values(value):
    topic, plan, answer = inputs(value)
    with pytest.raises(DomainError):
        TopicService._validate_answer(topic, plan, [], answer)


def test_required_fields_unit_batch_and_unknown_calculator_are_enforced():
    topic, plan, answer = inputs(1)
    empty = answer.model_copy(update={"fields": {}})
    with pytest.raises(DomainError, match="请填写"):
        TopicService._validate_answer(topic, plan, [], empty)
    wrong_unit = answer.model_copy(update={"fields": {"pressureBar": {"value": 1, "unit": "other"}}})
    with pytest.raises(DomainError, match="单位不符"):
        TopicService._validate_answer(topic, plan, [], wrong_unit)
    topic["questions"][0]["capture"] = {"batch_kind": "new_measurement", "batch_id_required": True}
    plan["capture_batches"]["new_measurement"] = "current-batch"
    with pytest.raises(DomainError, match="受控批次"):
        TopicService._validate_answer(topic, plan, [], answer)
    answer.batch_id = "current-batch"
    TopicService._validate_answer(topic, plan, [], answer)
    topic["calculation_catalog"] = {"version": "unknown"}
    with pytest.raises(DomainError, match="尚不支持"):
        TopicService._validate_answer(topic, plan, [], answer)


def test_independent_topic_cannot_inherit_legacy_rules_by_version_collision():
    topic, plan, answer = inputs(1.2)
    topic["version"] = "2.2.1-b02"
    answer.topic_version = topic["version"]
    assert TopicService._validate_answer(topic, plan, [], answer)[1]["pressureBar"]["value"] == 1.2
    assert type(workflow_for(topic)) is ObservationWorkflow
