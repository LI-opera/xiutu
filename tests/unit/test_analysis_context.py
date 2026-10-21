"""Reading guide: reviewed roles when present, retrieved sections always, full body only if search fails."""
import hashlib
from copy import deepcopy

from app.services.analysis_context import digest, enrich, model_payload
from app.services.retrieval_reading import Embeddings

BODY = """# 资料

## 1. 准备工作

记录故障背景与作业条件。

## 2. 接头座合与锁止

### 2.1 快插接头

确认接头推至止挡并听到锁止声，手拉不脱出。

## 3. 天气示例

雨天路面湿滑的一般说明。

## 4. 与现有问题的对应关系

| random-a | 第 2 节 |
"""


def fixture():
    questions = [{"id": "random-a", "title": "Q-01 · 接头是否推至止挡并锁止"},
                 {"id": "random-b", "title": "下一步安排"}]
    binding = {"template_id": "unrelated-template", "version": "9", "content_hash": "frozen"}
    document = {"id": "unrelated-document", "version": "7", "body": BODY,
                "content_hash": hashlib.sha256(BODY.encode()).hexdigest()}
    roles = {"version": "1", "templates": [{**binding, "questions": {
        "random-a": {"definition_hash": digest(questions[0]), "role": "observation",
                     "option_roles": {"missing": "inspection_status"}},
        "random-b": {"definition_hash": digest(questions[1]), "role": "disposition"}}}]}
    reading = {"version": "1", "documents": [{"id": document["id"], "version": "7",
               "content_hash": document["content_hash"], "always_include": ["## 1. 准备工作"]}]}
    payload = {"template_binding": binding, "questions": deepcopy(questions), "documents": [document],
               "observations": [{"id": "record", "question_id": "random-a", "option_ids": ["missing"],
                                 "option_labels": ["未座合"], "note": "备注提到天气", "fields": {"n": 7}}],
               "unknown_question_ids": ["random-b"]}
    return payload, {"questions": questions}, roles, reading


def run(payload, topic, roles, reading, embeddings=None):
    return enrich(payload, topic, embeddings, roles_config=roles, reading_config=reading, top_k=1)


def sent_body(result):
    return model_payload(result)["documents"][0]["body"]


def test_reviewed_roles_are_applied_and_originals_preserved():
    payload, topic, roles, reading = fixture()
    before = deepcopy(payload)
    result = run(payload, topic, roles, reading)
    assert all(result["documents"][0][k] == v for k, v in before["documents"][0].items())
    for key, value in before["observations"][0].items():
        assert result["observations"][0][key] == value
    assert result["observations"][0]["selected_option_roles"][0]["role"] == "inspection_status"
    assert result["observations"][0]["free_text_role"] == "unclassified"
    assert result["unknown_question_ids"] == []
    assert result["unrecorded_decision_question_ids"] == ["random-b"]
    assert result["reference_reading_guide"]["roles"] == "reviewed"


def test_sections_are_retrieved_plus_always_included_and_nothing_else():
    payload, topic, roles, reading = fixture()
    result = run(payload, topic, roles, reading)
    guide = result["reference_reading_guide"]["documents"][0]
    assert guide["status"] == "selected"
    assert [s["heading"] for s in guide["sections"]] == ["## 1. 准备工作", "## 2. 接头座合与锁止"]
    assert guide["sections"][1]["question_ids"] == ["random-a"]
    body = sent_body(result)
    assert "推至止挡" in body and "作业条件" in body
    # Unrelated content and the manual's own question table are not sent; the free-text note
    # mentioning the weather does not pull the weather section in.
    assert "雨天" not in body and "对应关系" not in body


def test_template_without_roles_still_gets_retrieved_sections():
    payload, topic, roles, reading = fixture()
    payload["template_binding"] = {**payload["template_binding"], "content_hash": "new-template"}
    result = run(payload, topic, roles, reading)
    assert result["reference_reading_guide"]["roles"] == "unreviewed"
    assert all(q["record_role"] == "unclassified" for q in result["questions"])
    assert result["unknown_question_ids"] == ["random-b"]
    sent = model_payload(result)["documents"][0]
    assert sent["body_scope"] == "retrieved_sections_with_context"
    assert "推至止挡" in sent["body"] and "对应关系" not in sent["body"]
    # Without roles, "下一步安排" is an ordinary unanswered question and gets its own best
    # (here weak) match: every question contributes its top sections, however weak.
    reasons = {s["heading"]: s["reason"] for s in result["reference_reading_guide"]["documents"][0]["sections"]}
    assert reasons["## 3. 天气示例"] == "unknown_fact_method"


def test_changed_question_definition_drops_its_role_but_not_the_search():
    payload, topic, roles, reading = fixture()
    topic["questions"][0] = {**topic["questions"][0], "title": "不同含义"}
    result = run(payload, topic, roles, reading)
    assert result["observations"][0]["record_role"] == "unclassified"
    assert result["reference_reading_guide"]["documents"][0]["status"] == "selected"


def test_always_included_sections_apply_only_to_the_reviewed_body():
    payload, topic, roles, reading = fixture()
    body = BODY + "\n## 5. 新增章节\n\n新内容。\n"
    payload["documents"][0].update(body=body, content_hash=hashlib.sha256(body.encode()).hexdigest())
    guide = run(payload, topic, roles, reading)["reference_reading_guide"]["documents"][0]
    assert "## 1. 准备工作" not in [s["heading"] for s in guide["sections"]]
    assert guide["status"] == "selected"


def test_document_without_sections_is_sent_whole():
    payload, topic, roles, reading = fixture()
    payload["documents"][0].update(body="没有标题的一段说明。", content_hash="x")
    result = run(payload, topic, roles, reading)
    assert result["reference_reading_guide"]["documents"][0]["status"] == "full_body_retained"
    sent = model_payload(result)["documents"][0]
    assert sent["body_scope"] == "full_document_fallback" and sent["body"] == "没有标题的一段说明。"


def test_unavailable_vector_model_sends_the_full_body():
    payload, topic, roles, reading = fixture()

    def missing_model():
        raise RuntimeError("MODEL_PATH_UNAVAILABLE")
    result = run(payload, topic, roles, reading, Embeddings(missing_model, fingerprint="e5"))
    guide = result["reference_reading_guide"]
    assert guide["documents"][0]["status"] == "retrieval_unavailable_full_body_retained"
    assert guide["channels"] == ["exact", "bm25", "dense"] and guide["embedding"] == "e5"
    assert sent_body(result) == BODY


def test_vectors_take_part_when_available():
    class CharVectors:
        """Deterministic stand-in: a vector of character counts over a fixed alphabet."""
        alphabet = "接头止挡锁天气准备"

        def embed_documents(self, texts):
            return [self.embed_query(t) for t in texts]

        def embed_query(self, text):
            return [float(text.count(c)) + 0.01 for c in self.alphabet]
    payload, topic, roles, reading = fixture()
    result = run(payload, topic, roles, reading, Embeddings(CharVectors(), fingerprint="chars"))
    guide = result["reference_reading_guide"]
    assert guide["channels"][-1] == "dense" and guide["documents"][0]["status"] == "selected"
    assert "推至止挡" in sent_body(result)


def test_unknown_facts_get_their_method_sections():
    payload, topic, roles, reading = fixture()
    payload["observations"] = []
    payload["unknown_question_ids"] = ["random-a", "random-b"]
    result = run(payload, topic, roles, reading)
    sections = result["reference_reading_guide"]["documents"][0]["sections"]
    method = next(s for s in sections if s["heading"].startswith("## 2."))
    assert method["reason"] == "unknown_fact_method" and method["question_ids"] == ["random-a"]
    assert result["unrecorded_decision_question_ids"] == ["random-b"]


def test_selected_result_is_bound_to_record_and_transport_is_nonmutating():
    payload, topic, roles, reading = fixture()
    result = run(payload, topic, roles, reading)
    before = deepcopy(result)
    sent = model_payload(result)
    focus = sent["reference_reading_guide"]["documents"][0]["result_methods"]
    assert focus == [{"heading": "## 2. 接头座合与锁止",
                      "selected_by": [{"observation_id": "record", "option_ids": ["missing"]}]}]
    assert sent["documents"][0]["body"].count("推至止挡") == 1
    assert result == before
    assert "analysis_extracts" not in sent["documents"][0]
    assert sent["documents"][0]["full_content_hash"] == result["documents"][0]["content_hash"]
    assert sent["documents"][0]["content_hash"] == hashlib.sha256(sent["documents"][0]["body"].encode()).hexdigest()


def test_extracts_from_an_earlier_call_are_never_reused():
    payload, topic, roles, reading = fixture()
    payload["documents"][0]["analysis_extracts"] = ["旧的摘录"]
    payload["documents"][0].update(body="没有标题。", content_hash="x")
    assert sent_body(run(payload, topic, roles, reading)) == "没有标题。"


def test_queries_hide_question_ids():
    from app.services.retrieval_reading import queries_for
    payload, _, _, _ = fixture()
    texts = [q["text"] for q in queries_for(payload)]
    assert texts == ["接头是否推至止挡并锁止：未座合", "下一步安排"]
