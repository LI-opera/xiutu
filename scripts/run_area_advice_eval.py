"""Run the AI advice evaluation set.

Default is a dry run: build every case input and estimate cost, no model call.
Paid run (each call is one real DeepSeek request recorded in the usual budget ledger):

    uv run python -B scripts/run_area_advice_eval.py --paid --runs 1 --max-cny 1

Results go to .local-data/evals/area-advice/<time>/ (report.md, summary.json, raw results).
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from scripts import area_advice_eval as ev  # noqa: E402

# Same per-token prices the budget ledger uses for deepseek-flash (CNY per token).
INPUT_CNY, OUTPUT_CNY = Decimal(2) / 1000000, Decimal(8) / 1000000
OUT_DIR = ROOT / ".local-data/evals/area-advice"


def wire_chars(payload):
    from app.domain.case_analysis import AreaAdviceV3
    from app.infrastructure.model_gateway import structured_schema_instruction
    from app.services.area_analysis_service import messages_for
    return sum(len(m.content) for m in messages_for(payload)) + len(
        structured_schema_instruction(AreaAdviceV3.model_json_schema()))


def upper_estimate(payload):
    """Conservative: one token per character, plus the full output budget."""
    return wire_chars(payload) * INPUT_CNY + payload["max_output_tokens"] * OUTPUT_CNY


def cost(usage):
    return usage["input_tokens"] * INPUT_CNY + usage["output_tokens"] * OUTPUT_CNY


def ledger_rows(turn_id):
    """What the budget ledger recorded for this call: no row means nothing was sent."""
    from app.infrastructure.model_budget import LIVE_LEDGER, BudgetLedger
    calls = BudgetLedger(LIVE_LEDGER).read()["calls"]
    return [row for key, row in calls.items() if key.startswith(turn_id + ":")]


def call_model(settings, payload, turn_id):
    from app.domain.case_analysis import AreaAdviceV3
    from app.infrastructure.model_gateway import DeepSeekGateway, ModelError
    from app.services.area_analysis_service import messages_for
    meta = {}
    gateway = None
    started = time.monotonic()
    try:
        gateway = DeepSeekGateway(settings, paid=True, turn_id=turn_id,
            prompt_version=payload["prompt_version"], max_model_calls=1,
            max_output_tokens=payload["max_output_tokens"], input_profile="matched_areas")
        result = gateway.generate_structured_once(AreaAdviceV3, messages_for(payload),
            on_response=lambda raw, m: meta.update(m, raw_response=raw)).model_dump(mode="json")
        error = None
    except ModelError as exc:
        result, error = None, str(exc)[:200]
    finally:
        if gateway is not None:
            gateway.close()
    return result, error, meta, round(time.monotonic() - started, 1)


def steps_md(result):
    lines = []
    for i, s in enumerate(result.get("steps") or []):
        lines.append(f"  {i + 1}. [{s.get('kind')}] {s.get('title')}（{','.join(s.get('question_ids') or []) or '无题号'}）")
    for b, branch in enumerate(result.get("conditional_branches") or []):
        lines.append(f"  - 暂缓分支 {b + 1}：触发条件「{branch.get('trigger')}」")
        for s in branch.get("steps") or []:
            lines.append(f"    - [{s.get('kind')}] {s.get('title')}（{','.join(s.get('question_ids') or []) or '无题号'}）")
    return "\n".join(lines) or "  （没有步骤）"


def write_report(folder, meta, cases, runs):
    lines = [f"# AI 建议评测报告 {meta['started_at']}", "",
             f"- 模型：{meta['model']}；提示词版本：{meta['prompt_version']}；题集：{meta['cases_version']}",
             f"- 每题运行 {meta['runs']} 次；实际费用约 {meta['cost_cny']} 元；调用 {meta['calls']} 次",
             "- 程序检查只是信号：文字匹配可能误判，请结合下面每次运行的详情和人工核对项判断。", "",
             "## 程序检查通过率", "", "| 题 | 检查 | 通过 |", "| --- | --- | --- |"]
    for case in cases:
        rows = [r for r in runs if r["case"] == case["id"]]
        labels = {g["id"]: g["label"] for r in rows if r["graded"] for g in r["graded"]}
        for check_id, label in labels.items():
            passed = sum(1 for r in rows if r["graded"] and next(
                g for g in r["graded"] if g["id"] == check_id)["passed"])
            lines.append(f"| {case['id']} | {label} | {passed}/{len(rows)} |")
        failed = sum(1 for r in rows if r["error"])
        if failed:
            lines.append(f"| {case['id']} | 调用失败（次数） | {failed}/{len(rows)} |")
    for case in cases:
        lines += ["", f"## {case['id']}　{case['title']}", "", f"**考什么**：{case['purpose']}", "",
                  f"**标准答案**：{case['expected']}"]
        for r in (r for r in runs if r["case"] == case["id"]):
            lines += ["", f"### 第 {r['run']} 次（{r['seconds']} 秒，约 {r['cost_cny']} 元）", ""]
            if r["error"]:
                lines.append(f"调用失败：`{r['error']}`" + ("" if r.get("sent") else "（请求未发出，未计费）"))
                continue
            lines += [f"**summary**：{r['result'].get('summary', '')}", "", "**步骤**：", steps_md(r["result"]), "",
                      "**程序检查**："]
            lines += [f"- {'✅' if g['passed'] else '❌'} {g['label']}：{g['detail']}" for g in r["graded"]]
            lines += ["", "**人工核对**（请勾选）："]
            lines += [f"- [ ] 是　[ ] 否　{q}" for q in case["human"]]
    (folder / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--paid", action="store_true", help="really call the model (costs money)")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--cases", default="", help="comma separated case IDs; default all")
    parser.add_argument("--max-cny", type=Decimal, default=Decimal("1"))
    args = parser.parse_args()
    if not 1 <= args.runs <= 5:
        parser.error("--runs must be 1..5")

    spec = ev.load_cases()
    wanted = {c for c in args.cases.split(",") if c}
    cases = [c for c in spec["cases"] if not wanted or c["id"] in wanted]
    if wanted - {c["id"] for c in cases}:
        parser.error("unknown case: " + ",".join(sorted(wanted - {c["id"] for c in cases})))

    settings = None
    max_output = ev.DEFAULT_MAX_OUTPUT_TOKENS
    if args.paid:
        from app.config import load_settings
        settings = load_settings(project_env=True)
        if not settings.deepseek_api_key:
            sys.exit("没有配置模型连接（DEEPSEEK_API_KEY），未调用。")
        if settings.deepseek_model != "deepseek-flash":
            sys.exit(f"当前模型设置是 {settings.deepseek_model!r}，项目账本只核实过 deepseek-flash 的价格，"
                     "调用会被拒绝。请检查 .env 里的 DEEPSEEK_MODEL，以及是否设置了同名环境变量。未调用。")
        max_output = settings.area_analysis_max_output_tokens

    topic = ev.load_topic(spec["template"])
    references = ev.load_references(spec["template"])
    # Same section choice as the service: local vectors, loaded from the project settings.
    from app.config import load_settings
    from app.services.area_analysis_service import reading_embeddings
    embeddings = reading_embeddings(settings or load_settings(project_env=True))
    payloads = {c["id"]: ev.build_payload(spec, c, topic=topic, references=references, embeddings=embeddings,
                                          max_output_tokens=max_output) for c in cases}
    unavailable = [d for p in payloads.values() for g in p["reference_reading_guide"] for d in g["documents"]
                   if d["status"] != "selected"]
    if unavailable:
        sys.exit(f"资料章节没有按检索选出（{unavailable[0]['status']}），检查本地向量模型。未调用。")
    upper = {cid: upper_estimate(p) for cid, p in payloads.items()}
    planned = sum(upper.values()) * args.runs
    print(f"{len(cases)} 题 × {args.runs} 次 = {len(cases) * args.runs} 次调用")
    for cid, p in payloads.items():
        print(f"  {cid}: 输入约 {wire_chars(p)} 字，区域 {[a['id'] for a in p['areas']]}，"
              f"单次上限约 {upper[cid]:.3f} 元")
    print(f"按上限估算（每字 1 token、输出用满）：{planned:.2f} 元；实际通常明显更低。费用上限 {args.max_cny} 元。")
    if not args.paid:
        print("这是演习，没有调用模型。加 --paid 才会真正调用。")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = OUT_DIR / stamp
    (folder / "payloads").mkdir(parents=True)
    (folder / "results").mkdir()
    for cid, p in payloads.items():
        (folder / "payloads" / f"{cid}.json").write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

    spent, observed, runs = Decimal(0), [], []
    for n in range(1, args.runs + 1):
        for case in cases:
            payload = payloads[case["id"]]
            next_cost = max(observed) * Decimal("1.5") if observed else upper[case["id"]]
            if spent + next_cost > args.max_cny:
                print(f"已花约 {spent:.3f} 元，下一次预计约 {next_cost:.3f} 元，会超过上限 {args.max_cny} 元，停止。")
                break
            print(f"调用 {case['id']} 第 {n} 次…", flush=True)
            turn_id = f"area-eval-{stamp}-{case['id']}-{n}"
            result, error, meta, seconds = call_model(settings, payload, turn_id)
            recorded = ledger_rows(turn_id)
            sent = any(row.get("status") != "not_sent" for row in recorded)
            usage = meta.get("usage") or next((row["usage"] for row in recorded if row.get("usage")), None)
            # Not in the ledger = refused before sending: costs nothing. Sent without usage: assume the upper bound.
            spent_now = cost(usage) if usage else (upper[case["id"]] if sent else Decimal(0))
            spent += spent_now
            if usage:
                observed.append(spent_now)
            graded = ev.grade(case, payload, result) if result else None
            row = {"case": case["id"], "run": n, "seconds": seconds, "error": error, "sent": sent, "usage": usage,
                   "cost_cny": f"{spent_now:.4f}", "result": result, "graded": graded,
                   "raw_response": meta.get("raw_response")}
            runs.append(row)
            (folder / "results" / f"{case['id']}-{n}.json").write_text(
                json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
            status = error or "、".join(f"{g['id']}{'✓' if g['passed'] else '✗'}" for g in graded)
            print(f"  {seconds} 秒，约 {spent_now:.4f} 元：{status}")
            if error and not sent:
                print("请求在发出前被拒绝（配置或账本问题），后面的调用也会同样失败，停止。")
                break
        else:
            continue
        break

    meta = {"started_at": stamp, "model": settings.deepseek_model,
            "prompt_version": sorted({p["prompt_version"] for p in payloads.values()}),
            "cases_version": spec["version"], "runs": args.runs, "calls": len(runs),
            "cost_cny": f"{spent:.3f}"}
    summary = {**meta, "results": [{k: r[k] for k in ("case", "run", "error", "sent", "usage", "cost_cny", "graded")}
                                   for r in runs]}
    (folder / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(folder, meta, cases, runs)
    print(f"完成：{len(runs)} 次调用，约 {spent:.3f} 元。报告：{folder / 'report.md'}")


if __name__ == "__main__":
    main()
