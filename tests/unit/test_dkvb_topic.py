import pytest
from app.legacy_preview.dkvb import references, safe_file, TopicQuery
from pydantic import ValidationError

def test_multi_pages():
    raw="## 原节\n引用S02-P5、S02-P6。\n"
    result=references(raw,{"text":raw,"locator_json":{"char_start":0}})
    assert [(x["source_id"],x["page"]) for x in result["pages"]]==[("S02",5),("S02",6)]
    assert result["mapping_scope"]=="direct_chunk"

def test_simulation_context_not_lost():
    raw="## DS-02 模拟\n性质DEMO，非厂家标准。\n值150。\n## 后节\nS03-P2\n"
    result=references(raw,{"text":"值150。","locator_json":{"char_start":raw.index("值")}})
    assert result["simulation_specs"]==["DS-02"] and result["pages"]==[]
    assert 'DEMO' in result['section_context']

def test_section_reference_is_labeled():
    raw="## 节\n来源S02-P4\n内容\n"
    result=references(raw,{"text":"内容","locator_json":{"char_start":raw.index("内容")}})
    assert result['pages'][0]['relation']=='section_reference'

def test_no_fabricated_mapping():
    assert references('正文',{'text':'正文','locator_json':{}})['pages']==[]

def test_path_escape(tmp_path):
    with pytest.raises(ValueError):safe_file(tmp_path,'../secret')

def test_no_client_scope():
    from uuid import uuid4
    with pytest.raises(ValidationError):TopicQuery(case_id=uuid4(),query='G31',profile='formal')


def test_shorthand_and_subsection():
    raw="## FACT\n### FS04\n来源S03-P8/P9。\n### DS-02\n模拟150\n"
    hit={"text":"来源S03-P8/P9。","locator_json":{"char_start":raw.index("来源")}}
    result=references(raw,hit)
    assert [x['page'] for x in result['pages']]==[8,9]
    assert result['simulation_specs']==[]
    ds=references(raw,{'text':'模拟150','locator_json':{'char_start':raw.index('模拟')}})
    assert ds['pages']==[] and ds['simulation_specs']==['DS-02']


@pytest.mark.parametrize("selector", ["title", "intro"])
def test_real_manual_preamble_has_no_later_references(selector):
    import threading
    from pathlib import Path
    from app.retrieval.parsers.markdown import parse
    from app.retrieval.chunker import chunks

    # Reuse the actual source/locator from the retained review response, not its IDs.
    evidence = Path(__file__).resolve().parents[2] / "tests/fixtures/topic_intro_counterexample.json"
    import json
    original = json.loads(evidence.read_text(encoding="utf8"))
    raw = original["raw"]
    items = chunks(parse(raw.encode("utf8"), threading.Event()), threading.Event())["chunks"]
    hit = next(x for x in items if x["text"] == original["text"]) if selector == "title" else next(x for x in items if "本手册组合" in x["text"])
    result = references(raw, hit)
    assert result["pages"] == []
    assert result["simulation_specs"] == []
    assert result["section_context"] == raw[:raw.index("## 1. 入口与范围")]
    if selector == "title":
        assert hit["locator_json"] == original["locator"]


@pytest.mark.parametrize("heading", ["##", "###", "######"])
def test_preamble_direct_reference_is_preserved(heading):
    raw = f"# 总标题\n简介直接引用S01-P1。\n{heading} 后节\nS02-P6、DS-02模拟值\n"
    text = "简介直接引用S01-P1。"
    result = references(raw, {"text": text, "locator_json": {"char_start": raw.index(text)}})
    assert result["pages"] == [{"source_id": "S01", "page": 1, "relation": "chunk"}]
    assert result["mapping_scope"] == "direct_chunk"
    assert result["simulation_specs"] == []
    assert "后节" not in result["section_context"]


def test_document_without_section_headings_keeps_own_context():
    raw = "# 简短资料\n引用S02-P6。DS-01为模拟。\n"
    result = references(raw, {"text": raw, "locator_json": {"char_start": 0}})
    assert result["pages"] == [{"source_id": "S02", "page": 6, "relation": "chunk"}]
    assert result["simulation_specs"] == ["DS-01"]
