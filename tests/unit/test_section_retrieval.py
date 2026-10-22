"""Section search building blocks and the offline evaluation's fairness rules. No model needed."""
import json

from app.retrieval.section_search import BM25, exact_rank, identifiers, rrf, split

from scripts import section_retrieval_eval as ev

DOC = """# 标题

前言不参与检索。

## 1. 接头座合

导语：先识别结构。

### 1.1 快插接头

推至止挡并听到锁止声。G71 在节气门前。

### 1.2 卡箍

卡箍扭矩按资料。

## 2. 检漏
### 2.1 加压

用 V.A.G 1687 加压，不超过 0.5 bar。

## 3. 与现有 AIR 问题的对应关系

| AIR-07 | 第 1 节 |
"""


def test_identifiers_are_exact_codes_but_not_question_ids():
    assert identifiers("G71 与 G31 不同，故障码 p0299") == {"G71", "G31", "P0299"}
    assert identifiers("使用 V.A.G 1687 或 VAS 6150") == {"VAG1687", "VAS6150"}
    # Written straight after Chinese text, as in question titles.
    assert identifiers("是否具备V.A.G 1687或等效工具，VAS6150可用") == {"VAG1687", "VAS6150"}
    assert identifiers("XVAS 6150、V.A.G 168701") == set()
    assert identifiers("AIR-07 与 PRS-05—PRS-06") == set()


def test_split_keeps_heading_paths_and_skips_front_matter_empty_and_navigation():
    chunks = split("doc", DOC, skip_sections=["对应关系"])
    assert [c.path for c in chunks] == ["1. 接头座合", "1. 接头座合 > 1.1 快插接头",
                                        "1. 接头座合 > 1.2 卡箍", "2. 检漏 > 2.1 加压"]
    assert all("前言" not in c.text and "AIR-07" not in c.text for c in chunks)
    assert chunks[1].identifiers == {"G71"} and chunks[3].identifiers == {"VAG1687"}
    assert chunks[1].search_text.startswith("1. 接头座合 > 1.1 快插接头\n")
    assert len(split("doc", DOC)) == 5  # the navigation table is searchable only when not skipped


def test_exact_rank_only_returns_chunks_sharing_a_code():
    chunks = split("doc", DOC)
    assert exact_rank("G71 读数离群", chunks) == [1]
    assert exact_rank("没有编号的问题", chunks) == []


def test_bm25_prefers_rare_matching_terms_and_drops_zero_scores():
    index = BM25(["接头 检查 检查 检查", "止挡 锁止 接头", "完全无关的内容"])
    assert index.rank("止挡") == [1]
    assert index.rank("接头止挡")[0] == 1
    assert 2 not in index.rank("接头止挡")


def test_rrf_rewards_items_ranked_by_several_channels():
    assert rrf([["a", "b", "c"], ["b", "c"]])[0] == "b"
    assert rrf([[], ["x"]]) == ["x"]


def test_hits_and_scores_follow_gold_granularity():
    chunks = split("doc", DOC)
    section = {"id": "s1", "heading": "## 1. 接头座合"}
    sub = {"id": "s1.2", "heading": "### 1.2 卡箍"}
    assert ev.hits(chunks[1], [section, sub]) == {"s1"}       # any chunk inside a ## covers it
    assert ev.hits(chunks[2], [section, sub]) == {"s1", "s1.2"}
    result = ev.score([3, 1, 2], chunks, [section, sub], [1, 2, 3])
    assert result["recall@1"] == 0 and result["recall@2"] == 0.5 and result["recall@3"] == 1
    assert result["rr"] == 0.5 and result["first_hit"] == 2


def test_real_queries_hide_question_ids_and_exclude_always_sent_sections():
    config = json.loads(ev.CONFIG.read_text(encoding="utf-8"))
    documents = ev.load_documents()
    context = json.loads(ev.CONTEXT.read_text(encoding="utf-8"))
    always = {(d["id"], d["version"]): set(d["always_include"]) for d in context["documents"]}
    queries = ev.load_queries(config, documents)
    assert len(queries) > 200
    for query in queries:
        assert not ev.QUESTION_ID.match(query["text"])
        assert query["question_id"] not in query["text"]
        version = documents[query["document_id"]]["version"]
        assert query["gold"] and not {g["id"] for g in query["gold"]} & always[(query["document_id"], version)]
    with_ids = ev.load_queries(config, documents, with_ids=True)
    assert all(q["question_id"] in q["text"] for q in with_ids)


def test_every_gold_section_is_reachable_after_skipping_navigation():
    config = json.loads(ev.CONFIG.read_text(encoding="utf-8"))
    documents = ev.load_documents()
    rows, counts = ev.evaluate(config, documents, ev.load_queries(config, documents), skip_navigation=True)
    assert all(not row["unreachable"] for row in rows)
    assert all(count > 40 for count in counts.values())
    navigation = [c for doc_id, doc in documents.items()
                  for c in split(doc_id, doc["body"]) if "对应关系" in c.section]
    assert navigation  # the manuals really contain question-to-section tables, so skipping matters


def test_section_ranking_counts_each_section_once_and_parent_covers_subsection_gold():
    chunks = split("doc", DOC)  # 0: ## 1 lead, 1: 1.1, 2: 1.2, 3: 2.1
    assert ev.section_ranking([1, 2, 0, 3], chunks) == [("doc", "## 1. 接头座合"), ("doc", "## 2. 检漏")]
    gold = [{"id": "s1.2", "heading": "### 1.2 卡箍"}, {"id": "s2", "heading": "## 2. 检漏"}]
    result = ev.score_sections([1, 2, 0, 3], chunks, gold, [1, 2], "doc")
    # Section 1 fills one slot however many of its subsections rank first, and contains 1.2.
    assert result["recall@1"] == 0.5 and result["recall@2"] == 1
    assert result["first_hit"] == 1 and result["top"] == ["1. 接头座合", "2. 检漏"]
    chunk_level = ev.score([1, 2, 0, 3], chunks, gold, [2], "doc")
    assert chunk_level["recall@2"] == 0.5  # chunk ranking spends both slots inside section 1


def test_library_scope_only_counts_hits_in_the_questions_own_document():
    own, other = split("doc", DOC), split("other", DOC)  # same headings, different documents
    pooled = own + other
    gold = [{"id": "s2", "heading": "## 2. 检漏"}]
    ranking = [len(own) + 3, 3]  # the other document's "## 2" ranks first
    result = ev.score_sections(ranking, pooled, gold, [1, 2], "doc")
    assert result["recall@1"] == 0 and result["recall@2"] == 1
    assert result["top"] == ["[other] 2. 检漏", "2. 检漏"]
    assert result["other_documents_in_top"] == 1
    assert ev.hits(other[3], gold, "doc") == set() and ev.hits(own[3], gold, "doc") == {"s2"}


def test_library_scope_searches_one_pool_and_keeps_per_document_counts():
    config = json.loads(ev.CONFIG.read_text(encoding="utf-8"))
    documents = ev.load_documents()
    queries = ev.load_queries(config, documents)[:20]
    area, area_counts = ev.evaluate(config, documents, queries, skip_navigation=True)
    library, library_counts = ev.evaluate(config, documents, queries, skip_navigation=True, scope="library")
    assert area_counts == library_counts
    assert all(not row["unreachable"] for row in library)
    assert [r["question_id"] for r in area] == [r["question_id"] for r in library]


def test_routing_votes_for_documents_and_keeps_close_runners_up():
    from app.services.retrieval_reading import route_documents
    chunks = split("a", DOC) + split("b", DOC)
    a, b = list(range(len(chunks) // 2)), list(range(len(chunks) // 2, len(chunks)))
    # Every text ranks document a's chunks first: only a's chunks vote, only a is read.
    assert [d for d, _ in route_documents(["x", "y"], lambda _: a + b, chunks, depth=2)] == ["a"]
    # Votes split evenly: both are read, best first by name on a tie.
    split_votes = route_documents(["x", "y"], lambda t: a + b if t == "x" else b + a, chunks, depth=2)
    assert [d for d, _ in split_votes] == ["a", "b"]
    assert route_documents(["x"], lambda _: [], chunks) == []
    # A runner-up close to the best (all chunks voting, b just behind) is read as well.
    assert [d for d, _ in route_documents(["x"], lambda _: a + b, chunks)] == ["a", "b"]


def test_routed_scope_picks_each_areas_own_document_offline():
    config = json.loads(ev.CONFIG.read_text(encoding="utf-8"))
    documents = ev.load_documents()
    routing = {}
    rows, _ = ev.evaluate(config, documents, ev.load_queries(config, documents), skip_navigation=True,
                          scope="routed", routing=routing)
    assert routing and all(v["assigned"] in [d for d, _ in v["chosen"]] for v in routing.values())
    assert all(not row["unreachable"] for row in rows)
