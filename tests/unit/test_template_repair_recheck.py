"""Post-repair re-checks are written through the ordinary record path, never as free text."""
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.domain.policies import DomainError
from app.services.template_repair_service import TemplateRepairService

from scripts.build_analysis_context import RELATIONS


def topic():
    relation = json.loads(RELATIONS.read_text(encoding="utf-8"))["relations"][0]
    return json.loads((RELATIONS.parent / relation["content_file"]).read_text(encoding="utf-8"))


class FakeTopicService:
    def __init__(self, existing=None):
        self.module = SimpleNamespace(TOPIC_VERSION="tpl", catalog=lambda: (topic(), "hash"))
        self.existing = existing or []
        self.writes = []

    def _topic(self, case):
        return self.module

    def _rows(self, conn, case_id, version):
        return self.existing

    def _write(self, conn, actor, case, module, answer, original_id=None, extra_payload=None):
        self.writes.append((answer, original_id, extra_payload))
        return uuid4(), case["revision"] + 1


def fake_conn(case):
    return SimpleNamespace(execute=lambda _: SimpleNamespace(
        mappings=lambda: SimpleNamespace(one=lambda: {**case, "revision": case["revision"] + 1})))


def item(question_id, option_id, **extra):
    return SimpleNamespace(question_id=question_id, option_ids=[option_id], fields={}, note="",
                           unavailable_reason="", **extra)


def test_recheck_supersedes_the_current_record_and_links_the_round():
    content = topic()
    question = next(q for q in content["questions"] if q["id"] == "AIR-02")
    current = {"id": uuid4(), "supersedes_id": None, "created_revision": 3,
               "payload": {"question_id": "AIR-02", "option_ids": [question["options"][0]["id"]]}}
    topics = FakeTopicService([current])
    service = TemplateRepairService(engine=None, topic_service=topics)
    case = {"id": uuid4(), "revision": 9}
    record = {"id": uuid4(), "area_id": "boost-air"}
    fresh = service._write_recheck(fake_conn(case), "actor", case, record,
                                   item("AIR-02", question["options"][1]["id"]))
    answer, original_id, extra = topics.writes[0]
    assert original_id == current["id"]
    assert answer.question_id == "AIR-02" and answer.expected_revision == 9
    assert answer.option_ids == [question["options"][1]["id"]]
    assert answer.correction_reason == "处理后复检"
    assert extra == {"repair_round_id": str(record["id"]), "operation_type": "post_repair_recheck"}
    assert fresh["revision"] == 10


@pytest.mark.parametrize("question_id,code", [
    ("PRS-05", "RETEST_QUESTION_INVALID"),   # another area
    ("NOPE-1", "RETEST_QUESTION_INVALID"),   # unknown question
    ("PRS-01", "RETEST_BATCH_UNSUPPORTED"),  # batch-captured reading
])
def test_recheck_rejects_items_outside_the_round_or_batch_readings(question_id, code):
    topics = FakeTopicService()
    service = TemplateRepairService(engine=None, topic_service=topics)
    area = "pressure" if question_id == "PRS-01" else "boost-air"
    with pytest.raises(DomainError) as error:
        service._write_recheck(fake_conn({"id": uuid4(), "revision": 1}), "actor",
                               {"id": uuid4(), "revision": 1}, {"id": uuid4(), "area_id": area},
                               item(question_id, "recorded"))
    assert error.value.code == code
    assert topics.writes == []
