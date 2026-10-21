"""Offline evaluation: can content search find the manual sections the reviewed table names?

No model API call. Queries are "question title (without its ID): option label"; the gold
answer is the reviewed question-to-section table, minus sections that are always sent.
Search runs inside the question's own area document, as the analysis would.

    uv run python -B scripts/section_retrieval_eval.py            # all channels, needs local E5
    uv run python -B scripts/section_retrieval_eval.py --no-dense # keyword/exact only

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

from scripts.build_analysis_context import RELATIONS  # noqa: E402
from scripts.seed_area_references import build_documents  # noqa: E402

CONFIG = ROOT / "evals/section-retrieval/config.json"
CONTEXT = ROOT / "evals/section-retrieval/reference_table_v1.json"
MANIFEST = RELATIONS.parent / "area_reference_manifest_v2.json"
PACKAGE = ROOT / "resources/knowledge/tayron"
OUT_DIR = ROOT / ".local-data/evals/section-retrieval"
QUESTION_ID = re.compile(r"^[A-Z]{1,4}-[0-9]{2}\s*·\s*")


def load_documents():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {doc["document_id"]: doc for _, doc in build_documents(PACKAGE, manifest)}


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
                    queries.append({"template_id": template["template_id"], "question_id": question["id"],
                        "option_id": option["id"], "document_id": doc_id, "text": text,
                        "gold": [{"id": sid, "heading": spec["sections"][sid]["heading"]} for sid in wanted]})
    return queries


def hits(chunk, gold):
    """Gold IDs a chunk covers: a ## gold by any chunk inside it, a ### gold only by itself."""
    covered = set()
    for item in gold:
        heading = item["heading"]
        if heading.startswith("### ") and chunk.subsection == heading:
            covered.add(item["id"])
        elif heading.startswith("## ") and not heading.startswith("### ") and chunk.section == heading:
            covered.add(item["id"])
    return covered


def section_ranking(ranking, chunks):
    """Whole ## sections in the order their best chunk ranks: what the analysis would send."""
    order = []
    for index in ranking:
        if chunks[index].section not in order:
            order.append(chunks[index].section)
    return order


def section_hits(section, gold, parents):
    """A ## gold is covered by its own section; a ### gold by the section that contains it."""
    return {g["id"] for g in gold if g["heading"] == section or parents.get(g["heading"]) == section}


def score_sections(ranking, chunks, gold, top_k):
    parents = {c.subsection: c.section for c in chunks if c.subsection}
    order = section_ranking(ranking, chunks)
    result = {}
    for k in top_k:
        found = set()
        for section in order[:k]:
            found |= section_hits(section, gold, parents)
        result[f"recall@{k}"] = len(found) / len(gold)
    first = next((pos for pos, section in enumerate(order, 1) if section_hits(section, gold, parents)), None)
    result["rr"] = 1 / first if first else 0.0
    result["first_hit"] = first
    result["top"] = [section.lstrip("# ") for section in order[:5]]
    return result


def score(ranking, chunks, gold, top_k):
    result = {}
    for k in top_k:
        found = set()
        for index in ranking[:k]:
            found |= hits(chunks[index], gold)
        result[f"recall@{k}"] = len(found) / len(gold)
    first = next((pos for pos, index in enumerate(ranking, 1) if hits(chunks[index], gold)), None)
    result["rr"] = 1 / first if first else 0.0
    result["first_hit"] = first
    return result


def embedder():
    from app.config import load_settings
    from app.infrastructure.embedding_gateway import gateway
    settings = load_settings(project_env=True)
    path = settings.embedding_path if settings.embedding_path.is_absolute() else ROOT / settings.embedding_path
    return gateway(path)


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


def evaluate(config, documents, queries, *, skip_navigation, model=None):
    skip = config["navigation_sections"] if skip_navigation else []
    chunks_by_doc = {doc_id: split(doc_id, doc["body"], skip) for doc_id, doc in documents.items()}
    indexes = {doc_id: BM25([c.search_text for c in chunks]) for doc_id, chunks in chunks_by_doc.items()}
    vectors = {}
    if model is not None:
        for doc_id, chunks in chunks_by_doc.items():
            vectors[doc_id] = cached_vectors(model, [c.search_text for c in chunks],
                                             OUT_DIR / "cache" / "e5-chunk-vectors.json")
    rows = []
    for query in queries:
        doc_id = query["document_id"]
        chunks = chunks_by_doc[doc_id]
        reachable = [g for g in query["gold"] if any(hits(c, [g]) for c in chunks)]
        rankings = {"exact": exact_rank(query["text"], chunks), "bm25": indexes[doc_id].rank(query["text"])}
        if model is not None:
            rankings["dense"] = dense_rank(model.embed_query(query["text"]), vectors[doc_id])
            rankings["bm25+dense"] = rrf([rankings["bm25"], rankings["dense"]])
            rankings["exact+bm25+dense"] = rrf([rankings["exact"], rankings["bm25"], rankings["dense"]])
        rankings["exact+bm25"] = rrf([rankings["exact"], rankings["bm25"]])
        row = {**query, "unreachable": [g["id"] for g in query["gold"] if g not in reachable],
               "channels": {}, "chunk_channels": {}}
        for name, ranking in rankings.items():
            # Main unit (v2): whole ## sections. Chunk-level (v1) is kept for comparison.
            row["channels"][name] = score_sections(ranking, chunks, query["gold"], config["top_k"])
            row["chunk_channels"][name] = score(ranking, chunks, query["gold"], config["top_k"])
            row["chunk_channels"][name]["top"] = [chunks[i].path for i in ranking[:5]]
        rows.append(row)
    return rows, {doc_id: len(chunks) for doc_id, chunks in chunks_by_doc.items()}


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-dense", action="store_true", help="skip the vector channel (no local model needed)")
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    documents = load_documents()
    model = None if args.no_dense else embedder()
    queries = load_queries(config, documents)
    rows, chunk_counts = evaluate(config, documents, queries, skip_navigation=True, model=model)
    channels = list(rows[0]["channels"])
    summary = summarize(rows, channels, config["top_k"])
    chunk_summary = summarize(rows, channels, config["top_k"], key="chunk_channels")
    # Comparison only: question IDs in the query and navigation tables searchable.
    leak_rows, _ = evaluate(config, documents, load_queries(config, documents, with_ids=True),
                            skip_navigation=False, model=model)
    leak_summary = summarize(leak_rows, channels, config["top_k"])

    main_channel = config["main_channel"] if config["main_channel"] in channels else "exact+bm25"
    k = config["pass"]["recall_at"]
    overall = summary[main_channel][f"recall@{k}"]
    per_doc = by_document(rows, main_channel, k)
    passed = overall >= config["pass"]["overall"] and all(v >= config["pass"]["each_document"] for v, _ in per_doc.values())

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = OUT_DIR / stamp
    folder.mkdir(parents=True, exist_ok=True)
    unreachable = [r for r in rows if r["unreachable"]]
    misses = sorted((r for r in rows if r["channels"][main_channel][f"recall@{k}"] < 1),
                    key=lambda r: (r["channels"][main_channel][f"recall@{k}"], r["document_id"], r["question_id"]))
    lines = [f"# 资料章节检索评测 {stamp}", "",
        f"- 题集：{config['version']}；查询 {len(rows)} 条（题目去掉题号 + 选项）；资料块 {sum(chunk_counts.values())} 个（{chunk_counts}）",
        "- 排名单位：整个 `##` 章节（同一章节的多个小节只占一个名额）；标准答案是 `###` 小节时，包含它的章节进前 k 即算命中",
        f"- 向量模型：{'未使用（--no-dense）' if model is None else 'multilingual-e5-small（本地）'}",
        f"- 及格线（事先写定）：{main_channel} 前 {k} 召回率 ≥ {config['pass']['overall']}，每份资料 ≥ {config['pass']['each_document']}",
        f"- **结果：{main_channel} 前 {k} 召回率 {overall}，{'达到' if passed else '未达到'}及格线**", "",
        "## 主分数（按章节排名；不用题号，导航章节不参与检索）", "", *table(summary, config["top_k"]), "",
        f"## 按标准章节个数（{main_channel}，前 {k}）", "", "| 标准章节个数 | 召回率 | 查询数 |", "| --- | --- | --- |",
        *[f"| {n} | {v} | {c} |" for n, (v, c) in by_gold_size(rows, main_channel, k).items()], "",
        "## 对照：按小节排名（v1 的算法）", "", *table(chunk_summary, config["top_k"]), "",
        f"## 按资料（{main_channel}，前 {k}）", "", "| 资料 | 召回率 | 查询数 |", "| --- | --- | --- |",
        *[f"| {d} | {v} | {n} |" for d, (v, n) in per_doc.items()], "",
        "## 对照：查询带题号、导航章节也参与检索（只作对照，不作为结论；导航章节会占用名额）", "", *table(leak_summary, config["top_k"]), "",
        f"## 标准答案落在导航章节里、内容检索不可能找到的：{len(unreachable)} 条", ""]
    lines += [f"- {r['question_id']}/{r['option_id']}：{r['unreachable']}" for r in unreachable[:30]]
    lines += ["", f"## 没找全的查询（{main_channel} 前 {k}，最多列 40 条）", ""]
    for r in misses[:40]:
        c = r["channels"][main_channel]
        lines.append(f"- **{r['question_id']} {r['text']}**（召回 {c[f'recall@{k}']}，首个命中第 {c['first_hit']} 位）")
        lines.append(f"  - 标准答案：{'；'.join(g['heading'] for g in r['gold'])}")
        lines.append(f"  - 实际前 5：{'；'.join(c['top'])}")
    (folder / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (folder / "results.json").write_text(json.dumps({"config": config, "summary": summary,
        "chunk_level_summary": chunk_summary,
        "reference_with_ids": leak_summary, "per_document": per_doc, "passed": passed, "rows": rows},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(table(summary, config["top_k"])))
    print(f"{main_channel} 前 {k} 召回率 {overall}：{'达到' if passed else '未达到'}及格线。报告：{folder / 'report.md'}")


if __name__ == "__main__":
    main()
