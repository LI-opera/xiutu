"""Offline evaluation: can content search find the manual sections the reviewed table names?

No model API call. Queries are "question title (without its ID): option label"; the gold
answer is the reviewed question-to-section table, minus sections that are always sent.
Search runs inside the question's own area document, as the analysis does today; with
--scope library it runs over every document of the vehicle at once (no area-to-document
assignment), and a hit only counts in the question's own document.

    uv run python -B scripts/section_retrieval_eval.py            # all channels, needs local E5
    uv run python -B scripts/section_retrieval_eval.py --no-dense # keyword/exact only
    uv run python -B scripts/section_retrieval_eval.py --scope library
    uv run python -B scripts/section_retrieval_eval.py --scope routed

--scope routed is two-step retrieval: first the area's own texts (title, description, question
titles) vote which documents to read, then sections are searched inside those only.

Results: .local-data/evals/section-retrieval/<time>/report.md and results.json.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT, ROOT / "backend"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from app.retrieval.section_search import BM25, dense_rank, exact_rank, rrf, split  # noqa: E402
from app.services.retrieval_reading import route_documents  # noqa: E402

from scripts.build_analysis_context import RELATIONS  # noqa: E402
from scripts.seed_area_references import build_documents, load_manuals  # noqa: E402

CONFIG = ROOT / "evals/section-retrieval/config.json"
CONTEXT = ROOT / "evals/section-retrieval/reference_table_v1.json"
AREA_DOCUMENTS = ROOT / "evals/area_documents.json"
PACKAGE = ROOT / "resources/knowledge/tayron"
OUT_DIR = ROOT / ".local-data/evals/section-retrieval"
QUESTION_ID = re.compile(r"^[A-Z]{1,4}-[0-9]{2}\s*·\s*")


def load_documents():
    return {doc["document_id"]: doc for _, doc in build_documents(PACKAGE, load_manuals())}


def area_texts(config):
    """(template, area) -> texts describing the area, and the document it should read (gold)."""
    relations = json.loads(RELATIONS.read_text(encoding="utf-8"))["relations"]
    assigned = json.loads(AREA_DOCUMENTS.read_text(encoding="utf-8"))["areas"]
    result = {}
    for template in config["templates"]:
        relation = next(r for r in relations if r["template_id"] == template["template_id"]
                        and r["version"] == template["version"])
        topic = json.loads((RELATIONS.parent / relation["content_file"]).read_text(encoding="utf-8"))
        for area in topic["areas"]:
            texts = [f"{area['title']}：{area.get('description', '')}"]
            texts += [QUESTION_ID.sub("", q["title"]) for q in topic["questions"] if q["area_id"] == area["id"]]
            result[(template["template_id"], area["id"])] = {"texts": texts, "assigned": assigned.get(area["id"])}
    return result


def load_queries(config, documents, *, with_ids=False):
    """One query per (question, option); identical query+gold pairs across templates count once."""
    context = json.loads(CONTEXT.read_text(encoding="utf-8"))
    relations = json.loads(RELATIONS.read_text(encoding="utf-8"))["relations"]
    specs = {(d["id"], d["version"]): d for d in context["documents"]}
    seen, queries = set(), []
    for template in config["templates"]:
        relation = next(r for r in relations if r["template_id"] == template["template_id"]
                        and r["version"] == template["version"])
        topic = json.loads((RELATIONS.parent / relation["content_file"]).read_text(encoding="utf-8"))
        roles = next(t for t in context["templates"] if t["template_id"] == template["template_id"]
                     and t["version"] == template["version"])["questions"]
        for question in topic["questions"]:
            role = roles.get(question["id"], {})
            for option in question.get("options", []):
                gold = {}
                for source in (role.get("references", {}),
                               role.get("option_references", {}).get(option["id"], {})):
                    for doc_id, ids in source.items():
                        gold.setdefault(doc_id, set()).update(ids)
                for doc_id, ids in gold.items():
                    document = documents[doc_id]
                    spec = specs[(doc_id, document["version"])]
                    if spec["content_hash"] != document["content_hash"]:
                        raise ValueError(f"Reading config does not match document {doc_id}")
                    wanted = sorted(ids - set(spec["always_include"]))
                    if not wanted:
                        continue
                    title = question["title"] if with_ids else QUESTION_ID.sub("", question["title"])
                    text = f"{title}：{option['label']}"
                    key = (doc_id, text, tuple(wanted))
                    if key in seen:
                        continue
                    seen.add(key)
                    queries.append({"template_id": template["template_id"], "area_id": question["area_id"],
                        "question_id": question["id"],
                        "option_id": option["id"], "document_id": doc_id, "text": text,
                        "gold": [{"id": sid, "heading": spec["sections"][sid]["heading"]} for sid in wanted]})
    return queries


def hits(chunk, gold, doc_id=None):
    """Gold IDs a chunk covers: a ## gold by any chunk inside it, a ### gold only by itself.

    doc_id: the gold's document; a chunk of another document never covers it.
    """
    covered = set()
    if doc_id is not None and chunk.document_id != doc_id:
        return covered
    for item in gold:
        heading = item["heading"]
        if heading.startswith("### ") and chunk.subsection == heading:
            covered.add(item["id"])
        elif heading.startswith("## ") and not heading.startswith("### ") and chunk.section == heading:
            covered.add(item["id"])
    return covered


def section_ranking(ranking, chunks):
    """Whole ## sections (per document) in the order their best chunk ranks: what would be sent."""
    order = []
    for index in ranking:
        key = (chunks[index].document_id, chunks[index].section)
        if key not in order:
            order.append(key)
    return order


def section_hits(key, gold, parents, doc_id=None):
    """A ## gold is covered by its own section; a ### gold by the section that contains it."""
    document, section = key
    if doc_id is not None and document != doc_id:
        return set()
    return {g["id"] for g in gold if g["heading"] == section or parents.get(g["heading"]) == section}


def score_sections(ranking, chunks, gold, top_k, doc_id=None):
    parents = {c.subsection: c.section for c in chunks
               if c.subsection and (doc_id is None or c.document_id == doc_id)}
    order = section_ranking(ranking, chunks)
    result = {}
    for k in top_k:
        found = set()
        for key in order[:k]:
            found |= section_hits(key, gold, parents, doc_id)
        result[f"recall@{k}"] = len(found) / len(gold)
    first = next((pos for pos, key in enumerate(order, 1) if section_hits(key, gold, parents, doc_id)), None)
    result["rr"] = 1 / first if first else 0.0
    result["first_hit"] = first
    result["top"] = [(section.lstrip("# ") if doc_id is None or document == doc_id
                      else f"[{document}] {section.lstrip('# ')}")
                     for document, section in order[:5]]
    result["other_documents_in_top"] = sum(1 for document, _ in order[:5]
                                           if doc_id is not None and document != doc_id)
    return result


def score(ranking, chunks, gold, top_k, doc_id=None):
    result = {}
    for k in top_k:
        found = set()
        for index in ranking[:k]:
            found |= hits(chunks[index], gold, doc_id)
        result[f"recall@{k}"] = len(found) / len(gold)
    first = next((pos for pos, index in enumerate(ranking, 1) if hits(chunks[index], gold, doc_id)), None)
    result["rr"] = 1 / first if first else 0.0
    result["first_hit"] = first
    return result


def embedder():
    """The vector model the analysis itself uses, chosen by the project settings (E5 or BGE-M3)."""
    from app.config import load_settings
    from app.infrastructure.model_factory import embedding_factory, selected_config
    settings = load_settings(project_env=True)
    config = selected_config(settings)
    model = embedding_factory(settings, config)
    model.fingerprint = config["config_version"]
    return model


def cached_vectors(model, texts, cache_path):
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    keys = [hashlib.sha256(t.encode()).hexdigest() for t in texts]
    missing = [t for t, k in zip(texts, keys) if k not in cache]
    if missing:
        for text, vector in zip(missing, model.embed_documents(missing)):
            cache[hashlib.sha256(text.encode()).hexdigest()] = [float(x) for x in vector]
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
    return [cache[k] for k in keys]


def evaluate(config, documents, queries, *, skip_navigation, model=None, scope="area", routing=None):
    skip = config["navigation_sections"] if skip_navigation else []
    chunks_by_doc = {doc_id: split(doc_id, doc["body"], skip) for doc_id, doc in documents.items()}
    counts = {doc_id: len(chunks) for doc_id, chunks in chunks_by_doc.items()}
    own = dict(chunks_by_doc)
    if scope in ("library", "routed"):
        # One pool: every document of the vehicle, searched together.
        pooled = [c for doc_id in sorted(chunks_by_doc) for c in chunks_by_doc[doc_id]]
        shared = BM25([c.search_text for c in pooled])
        chunks_by_doc = {doc_id: pooled for doc_id in chunks_by_doc}
        indexes = {doc_id: shared for doc_id in chunks_by_doc}
    else:
        indexes = {doc_id: BM25([c.search_text for c in chunks]) for doc_id, chunks in chunks_by_doc.items()}
    vectors = {}
    if model is not None:
        for doc_id, chunks in chunks_by_doc.items():
            vectors[doc_id] = cached_vectors(model, [c.search_text for c in chunks],
                                             OUT_DIR / "cache" / f"{model.fingerprint}-chunk-vectors.json")
    routes = {}
    if scope == "routed":
        # Step one: each area's texts vote for documents over the whole pool (all channels).
        pool_vectors = cached_vectors(model, [c.search_text for c in pooled],
                                      OUT_DIR / "cache" / f"{model.fingerprint}-chunk-vectors.json") if model else None

        def rank(text):
            channels = [exact_rank(text, pooled), shared.rank(text)]
            if model is not None:
                channels.append(dense_rank(model.embed_query(text), pool_vectors))
            return rrf(channels)
        for key, area in area_texts(config).items():
            routes[key] = route_documents(area["texts"], rank, pooled)
            if routing is not None:
                routing[key] = {"chosen": routes[key], "assigned": area["assigned"],
                                "all": route_documents(area["texts"], rank, pooled, keep=0)[:3]}
        routed_chunks, routed_index, routed_vectors = {}, {}, {}
        for key, chosen in routes.items():
            subset = [c for doc_id, _ in chosen for c in own[doc_id]]
            routed_chunks[key], routed_index[key] = subset, BM25([c.search_text for c in subset])
            if model is not None:
                routed_vectors[key] = cached_vectors(model, [c.search_text for c in subset],
                                                     OUT_DIR / "cache" / f"{model.fingerprint}-chunk-vectors.json")
    rows = []
    for query in queries:
        doc_id = query["document_id"]
        chunks = chunks_by_doc[doc_id]
        if scope == "routed":
            key = (query["template_id"], query["area_id"])
            chunks = routed_chunks[key]
        reachable = [g for g in query["gold"] if any(hits(c, [g], doc_id) for c in chunks)]
        index = routed_index[key] if scope == "routed" else indexes[doc_id]
        rankings = {"exact": exact_rank(query["text"], chunks), "bm25": index.rank(query["text"])}
        if model is not None:
            chunk_vectors = routed_vectors[key] if scope == "routed" else vectors[doc_id]
            rankings["dense"] = dense_rank(model.embed_query(query["text"]), chunk_vectors)
            rankings["bm25+dense"] = rrf([rankings["bm25"], rankings["dense"]])
            rankings["exact+bm25+dense"] = rrf([rankings["exact"], rankings["bm25"], rankings["dense"]])
        rankings["exact+bm25"] = rrf([rankings["exact"], rankings["bm25"]])
        row = {**query, "unreachable": [g["id"] for g in query["gold"] if g not in reachable],
               "channels": {}, "chunk_channels": {}}
        for name, ranking in rankings.items():
            # Main unit (v2): whole ## sections. Chunk-level (v1) is kept for comparison.
            row["channels"][name] = score_sections(ranking, chunks, query["gold"], config["top_k"], doc_id)
            row["chunk_channels"][name] = score(ranking, chunks, query["gold"], config["top_k"], doc_id)
            row["chunk_channels"][name]["top"] = [chunks[i].path for i in ranking[:5]]
        rows.append(row)
    return rows, counts


def summarize(rows, channels, top_k, key="channels"):
    def mean(values):
        values = list(values)
        return round(sum(values) / len(values), 3) if values else None
    summary = {}
    for name in channels:
        summary[name] = {f"recall@{k}": mean(r[key][name][f"recall@{k}"] for r in rows) for k in top_k}
        summary[name]["mrr"] = mean(r[key][name]["rr"] for r in rows)
    return summary


def by_gold_size(rows, channel, k):
    sizes = {}
    for r in rows:
        sizes.setdefault(len(r["gold"]), []).append(r["channels"][channel][f"recall@{k}"])
    return {n: (round(sum(v) / len(v), 3), len(v)) for n, v in sorted(sizes.items())}


def by_document(rows, channel, k):
    result = {}
    for doc_id in sorted({r["document_id"] for r in rows}):
        values = [r["channels"][channel][f"recall@{k}"] for r in rows if r["document_id"] == doc_id]
        result[doc_id] = (round(sum(values) / len(values), 3), len(values))
    return result


def table(summary, top_k):
    head = "| 检索方式 | " + " | ".join(f"前 {k} 召回率" for k in top_k) + " | MRR |"
    lines = [head, "|" + " --- |" * (len(top_k) + 2)]
    for name, values in summary.items():
        lines.append(f"| {name} | " + " | ".join(str(values[f'recall@{k}']) for k in top_k) + f" | {values['mrr']} |")
    return lines


SCOPES = {
    "area": "每题只在本区域的资料里检索（现在的做法，区域对资料靠清单）",
    "library": "全部资料一起检索，不按区域分资料；命中必须在本题的资料里才算",
    "routed": "两步检索：先由区域的名称、说明和题目自动选资料（不用清单），再在选中的资料里检索章节",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-dense", action="store_true", help="skip the vector channel (no local model needed)")
    parser.add_argument("--scope", choices=["area", "library", "routed"], default="area",
                        help="area: the question's own document (today); library: all documents together; "
                             "routed: the area's texts choose documents first, then sections")
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    documents = load_documents()
    model = None if args.no_dense else embedder()
    queries = load_queries(config, documents)
    routing = {}
    rows, chunk_counts = evaluate(config, documents, queries, skip_navigation=True, model=model,
                                  scope=args.scope, routing=routing)
    channels = list(rows[0]["channels"])
    summary = summarize(rows, channels, config["top_k"])
    chunk_summary = summarize(rows, channels, config["top_k"], key="chunk_channels")
    # Comparison only: question IDs in the query and navigation tables searchable.
    leak_rows, _ = evaluate(config, documents, load_queries(config, documents, with_ids=True),
                            skip_navigation=False, model=model, scope=args.scope)
    leak_summary = summarize(leak_rows, channels, config["top_k"])

    main_channel = config["main_channel"] if config["main_channel"] in channels else "exact+bm25"
    k = config["pass"]["recall_at"]
    overall = summary[main_channel][f"recall@{k}"]
    per_doc = by_document(rows, main_channel, k)
    passed = overall >= config["pass"]["overall"] and all(v >= config["pass"]["each_document"] for v, _ in per_doc.values())

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = OUT_DIR / (stamp if args.scope == "area" else f"{stamp}-{args.scope}")
    folder.mkdir(parents=True, exist_ok=True)
    unreachable = [r for r in rows if r["unreachable"]]
    misses = sorted((r for r in rows if r["channels"][main_channel][f"recall@{k}"] < 1),
                    key=lambda r: (r["channels"][main_channel][f"recall@{k}"], r["document_id"], r["question_id"]))
    lines = [f"# 资料章节检索评测 {stamp}", "",
        f"- 题集：{config['version']}；查询 {len(rows)} 条（题目去掉题号 + 选项）；资料块 {sum(chunk_counts.values())} 个（{chunk_counts}）",
        "- 排名单位：整个 `##` 章节（同一章节的多个小节只占一个名额）；标准答案是 `###` 小节时，包含它的章节进前 k 即算命中",
        f"- 检索范围：{SCOPES[args.scope]}",
        f"- 前 5 里平均有几章来自别的资料：{round(sum(r['channels'][main_channel]['other_documents_in_top'] for r in rows) / len(rows), 2) if args.scope != 'area' else '—'}",
        f"- 向量模型：{'未使用（--no-dense）' if model is None else model.fingerprint + '（项目配置，与分析时相同）'}",
        f"- 及格线（事先写定）：{main_channel} 前 {k} 召回率 ≥ {config['pass']['overall']}，每份资料 ≥ {config['pass']['each_document']}",
        f"- **结果：{main_channel} 前 {k} 召回率 {overall}，{'达到' if passed else '未达到'}及格线**", "",
        "## 主分数（按章节排名；不用题号，导航章节不参与检索）", "", *table(summary, config["top_k"]), "",
        f"## 按标准章节个数（{main_channel}，前 {k}）", "", "| 标准章节个数 | 召回率 | 查询数 |", "| --- | --- | --- |",
        *[f"| {n} | {v} | {c} |" for n, (v, c) in by_gold_size(rows, main_channel, k).items()], "",
        "## 对照：按小节排名（v1 的算法）", "", *table(chunk_summary, config["top_k"]), "",
        f"## 按资料（{main_channel}，前 {k}）", "", "| 资料 | 召回率 | 查询数 |", "| --- | --- | --- |",
        *[f"| {d} | {v} | {n} |" for d, (v, n) in per_doc.items()], "",
        "## 对照：查询带题号、导航章节也参与检索（只作对照，不作为结论；导航章节会占用名额）", "", *table(leak_summary, config["top_k"]), "",
        f"## 标准答案找不到的（落在导航章节里，或第一步没选到它的资料）：{len(unreachable)} 条", ""]
    if routing:
        right = sum(1 for v in routing.values() if v["assigned"] in [d for d, _ in v["chosen"]])
        lines[lines.index("## 主分数（按章节排名；不用题号，导航章节不参与检索）"):
              lines.index("## 主分数（按章节排名；不用题号，导航章节不参与检索）")] = [
            f"## 第一步：区域自动选资料（{right}/{len(routing)} 个区域选中了清单里对应的资料）", "",
            "注意：现有 5 份资料与区域一一对应，这一步比资料多、一份资料讲多个区域时容易，分数偏乐观。", "",
            "| 模板 | 区域 | 选中的资料（得分） | 清单对应 | 落选的第二名（得分，占第一名比例） |",
            "| --- | --- | --- | --- | --- |",
            *[f"| {tid} | {aid} | {'；'.join(f'{d}（{s}）' for d, s in v['chosen'])} | {v['assigned']} | "
              + (f"{v['all'][len(v['chosen'])][0]}（{v['all'][len(v['chosen'])][1]}，"
                 f"{round(v['all'][len(v['chosen'])][1] / v['all'][0][1], 2)}）" if len(v['all']) > len(v['chosen']) else "—")
              + " |" for (tid, aid), v in routing.items()], ""]
    lines += [f"- {r['question_id']}/{r['option_id']}：{r['unreachable']}" for r in unreachable[:30]]
    lines += ["", f"## 没找全的查询（{main_channel} 前 {k}，最多列 40 条）", ""]
    for r in misses[:40]:
        c = r["channels"][main_channel]
        lines.append(f"- **{r['question_id']} {r['text']}**（召回 {c[f'recall@{k}']}，首个命中第 {c['first_hit']} 位）")
        lines.append(f"  - 标准答案：{'；'.join(g['heading'] for g in r['gold'])}")
        lines.append(f"  - 实际前 5：{'；'.join(c['top'])}")
    (folder / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (folder / "results.json").write_text(json.dumps({"config": config, "scope": args.scope, "summary": summary,
        "routing": {f"{tid}/{aid}": v for (tid, aid), v in routing.items()},
        "chunk_level_summary": chunk_summary,
        "reference_with_ids": leak_summary, "per_document": per_doc, "passed": passed, "rows": rows},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(table(summary, config["top_k"])))
    print(f"{main_channel} 前 {k} 召回率 {overall}：{'达到' if passed else '未达到'}及格线。报告：{folder / 'report.md'}")


if __name__ == "__main__":
    main()
