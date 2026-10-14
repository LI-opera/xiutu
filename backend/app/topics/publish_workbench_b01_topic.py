"""Publish immutable B01 execution topic from the reviewed A01 candidate."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
source = ROOT / "candidates" / "tanyue-dkvb-p0299-a01-candidate.json"
target = ROOT / "tanyue_dkvb_p0299_b01.json"
topic = json.loads(source.read_text(encoding="utf-8"))
topic.update(version="2.2.0-b01", candidate_status="IMPLEMENTED_NOT_ACCEPTED",
             publishable=True, runtime_enabled=True,
             authority="A01 reviewed catalog plus B01 execution rules; synthetic DEMO only.")
questions = {q["id"]: q for q in topic["questions"]}
rules = {r["question_id"]: r for r in topic["derived_rules"]}

# The load-frame trend is not itself trustworthy diagnostic evidence.
rules["PRS-11"]["rationale"] += " 该项只表达读数趋势，不单独表示可信诊断证据。"
topic["derived_rules"].append({
    "rule_id": "D-PRESSURE-EVIDENCE", "question_id": None,
    "depends_on": ["PRS-01", "PRS-02", "PRS-03", "PRS-04", "PRS-05", "PRS-06",
                   "PRS-07", "PRS-08", "PRS-09", "PRS-10", "PRS-11"],
    "rationale": "仅同批次有效静态读数、必要信号复核与可比负荷帧均已保存时，趋势才可作为诊断线索。",
    "decision_table": [
        {"predicate_id": "saved_static_consistent_and_same_batch_comparable_load_frames", "output_option_id": "credible"},
        {"predicate_id": "otherwise", "output_option_id": "insufficient"}],
    "source_refs": ["EDITORIAL_DEMO"]})
rules["TUR-09"]["depends_on"] += ["PRS-04", "PRS-05", "PRS-06", "PRS-07"]
rules["TUR-09"]["rationale"] += " 压力类别仅引用 D-PRESSURE-EVIDENCE=credible，不直接引用 PRS-11 趋势。"
questions["TUR-09"]["dependency_question_ids"] += ["PRS-04", "PRS-05", "PRS-06", "PRS-07"]
questions["TUR-09"]["prerequisites"]["refs"] += ["PRS-04", "PRS-05", "PRS-06", "PRS-07"]
rules["X-13"]["rationale"] += " 各方向分别判定后汇总；同时支持两类以上输出 multiple 并保留全部方向。缺失证据不等于无异常。"
rules["X-13"]["decision_table"][-1]["predicate_id"] = "all_applicable_directions_checked_and_no_supported_direction"
rules["PRS-11"]["decision_table"][-1]["boundary"] += "; G71专项复核资料不足时保持待补充"
topic["plan_policy"]["first_round_scope"]["S2"] = [
    q for q in topic["plan_policy"]["first_round_scope"]["S2"] if q != "PRS-11"]
topic["plan_policy"]["ai_first_advice_ready"] += " ACT-10 and RET-01..08 never block first advice solely because an area is browsed."

rendered = json.dumps(topic, ensure_ascii=False, indent=2) + "\n"
if target.exists():
    if target.read_text(encoding="utf-8") != rendered:
        raise SystemExit("B01 publication exists with different bytes; never overwrite")
else:
    target.write_text(rendered, encoding="utf-8")
print(target)
