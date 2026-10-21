"""Before switching: how much text would retrieval send, and does it cover today's choice?

For each AI evaluation case, compares the sections chosen by the reviewed table (today)
with sections chosen by search at several "sections per question" settings. No model API
call; the vector channel uses the local E5 model unless --no-dense is given.

    uv run python -B scripts/retrieval_reading_measure.py
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT, ROOT / "backend"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from app.services.retrieval_reading import (  # noqa: E402
    Embeddings,
    queries_for,
    section_ranges,
    select_sections,
)

from scripts import area_advice_eval as ev  # noqa: E402

READING = ROOT / "backend/app/topics/reading_documents_v1.json"
OUT_DIR = ROOT / ".local-data/evals/retrieval-reading"
TOP_K = (1, 2, 3, 5)


def merged_chars(body, spans):
    total, last_end = 0, -1
    for start, end in sorted(spans):
        start = max(start, last_end)
        if end > start:
            total += end - start
        last_end = max(last_end, end)
    return total


def area_payload(payload, area):
    """The records and unanswered questions of one area, for building its queries."""
    ids = set(area["observation_ids"])
    return {"questions": payload["questions"],
            "observations": [o for o in payload["observations"] if o["id"] in ids],
            "unknown_question_ids": area["unknown_question_ids"]}


def today_sections(payload, document):
    """Headings the reviewed table selects today, ### mapped to their ## section."""
    guides = payload["reference_reading_guide"]
    guides = guides if isinstance(guides, list) else [guides]  # combined analysis: one guide per area
    guide = next(d for g in guides for d in g["documents"] if d["document_id"] == document["id"])
    ranges = section_ranges(document["body"])
    result = set()
    for section in guide["sections"]:
        heading = section["heading"]
        if heading in ranges:
            result.add(heading)
        else:
            start = document["body"].find(heading)
            result.add(next(h for h, (a, b) in ranges.items() if a <= start < b))
    return result, guide


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-dense", action="store_true")
    args = parser.parse_args()
    embeddings = None
    if not args.no_dense:
        from scripts.section_retrieval_eval import embedder
        embeddings = Embeddings(embedder(), OUT_DIR / "cache")
    always = {(d["id"], d["version"]): d["always_include"]
              for d in json.loads(READING.read_text(encoding="utf-8"))["documents"]}
    spec = ev.load_cases()
    topic = ev.load_topic(spec["template"])
    references = ev.load_references(spec["template"])
    lines = ["# 检索选章节：切换前测量", "",
             f"向量：{'未使用' if embeddings is None else 'multilingual-e5-small'}。字数为发给 AI 的资料正文字数（多个章节重叠部分只算一次）。",
             "覆盖率 = 今天对照表选中的章节里，检索也选中的比例（必带章节两边都有）。", ""]
    totals = {"today": 0, **{k: 0 for k in TOP_K}}
    covered = {k: [0, 0] for k in TOP_K}
    for case in spec["cases"]:
        payload = ev.build_payload(spec, case, topic=topic, references=references)
        lines += [f"## {case['id']}", "", "| 资料 | 今天 字数/章节 | " + " | ".join(f"前 {k} 字数/章节/覆盖" for k in TOP_K) + " |",
                  "|" + " --- |" * (len(TOP_K) + 2)]
        for area in payload["areas"]:
            for doc_id in area["document_ids"]:
                document = next(d for d in payload["documents"] if d["id"] == doc_id)
                wanted, guide = today_sections(payload, document)
                ranges = section_ranges(document["body"])
                today_chars = merged_chars(document["body"], [ranges[h] for h in wanted])
                totals["today"] += today_chars
                cells = [f"{today_chars}/{len(wanted)}"]
                queries = queries_for(area_payload(payload, area))
                for k in TOP_K:
                    chosen = select_sections(document, queries, top_k=k, embeddings=embeddings,
                                             always_include=always.get((document["id"], document["version"]), []))
                    headings = {s["heading"] for s in chosen}
                    chars = merged_chars(document["body"], [(s["start"], s["end"]) for s in chosen])
                    totals[k] += chars
                    hit = len(wanted & headings)
                    covered[k][0] += hit
                    covered[k][1] += len(wanted)
                    cells.append(f"{chars}/{len(headings)}/{hit}/{len(wanted)}")
                lines.append(f"| {doc_id} | " + " | ".join(cells) + " |")
        lines.append("")
    lines += ["## 合计（6 道题）", "", "| 方式 | 资料字数 | 相对今天 | 覆盖今天选中的章节 |", "| --- | --- | --- | --- |",
              f"| 今天（对照表） | {totals['today']} | 1.00 | — |"]
    for k in TOP_K:
        hit, total = covered[k]
        lines.append(f"| 检索 前 {k} | {totals[k]} | {totals[k] / totals['today']:.2f} | {hit}/{total} = {hit / total:.2f} |")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = OUT_DIR / stamp
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[-(len(TOP_K) + 4):]))
    print(f"报告：{folder / 'report.md'}")


if __name__ == "__main__":
    main()
