"""AI advice evaluation set: synthetic cases -> real model input -> program checks.

Cases live in evals/area-advice/cases.json. Each case lists saved records and repair
rounds; this module turns them into the same frozen input the area analysis service
sends (real plan, rule calculation, reading guide and documents), then grades a
model result with deterministic checks. Nothing here calls a model.

The checks only test whether advice follows the facts and rules in its input. They do
not judge whether a diagnosis is correct for a real vehicle.
"""
import json
import re
import sys
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from functools import partial
from pathlib import Path
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT, ROOT / "backend"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from app.retrieval.section_search import identifiers  # noqa: E402
from app.services import analysis_context, area_analysis_service  # noqa: E402
from app.services.analysis_context import model_payload  # noqa: E402
from app.services.area_analysis_service import MATCHED_SYSTEM_PROMPT, build_matched_input  # noqa: E402
from app.services.template_projection import build_plan, project_template  # noqa: E402
from app.services.workbench_templates import content_hash  # noqa: E402

from scripts.build_analysis_context import RELATIONS  # noqa: E402
from scripts.seed_area_references import build_documents  # noqa: E402

CASES = ROOT / "evals/area-advice/cases.json"
MANIFEST = RELATIONS.parent / "area_reference_manifest_v2.json"
PACKAGE = ROOT / "resources/knowledge/tayron"
DEFAULT_MAX_OUTPUT_TOKENS = 8192


def load_cases(path=CASES):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_topic(template):
    relations = json.loads(RELATIONS.read_text(encoding="utf-8"))["relations"]
    match = [r for r in relations
             if r["template_id"] == template["template_id"] and r["version"] == template["version"]]
    if len(match) != 1:
        raise ValueError("Template not found in relations: " + json.dumps(template))
    return json.loads((RELATIONS.parent / match[0]["content_file"]).read_text(encoding="utf-8"))


def load_references(template):
    """Documents per area, in the same shape load_documents() returns from the database."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if template["template_id"] not in manifest["template_ids"] or manifest["template_version"] != template["version"]:
        raise ValueError("Reference manifest does not cover the case template")
    by_area = {}
    for entry, doc in build_documents(PACKAGE, manifest):
        by_area.setdefault(entry["area_id"], []).append({
            "id": doc["document_id"], "version": doc["version"], "title": doc["title"],
            "body": doc["body"], "content_hash": doc["content_hash"], "provenance": doc["provenance"]})
    for docs in by_area.values():
        docs.sort(key=lambda d: d["id"])
    return by_area


def _id(case_id, *parts):
    """Stable IDs keep the model input identical between runs of the same case."""
    return str(uuid5(NAMESPACE_URL, "xiutu-area-advice-eval:" + ":".join([case_id, *map(str, parts)])))


def _fields(question, raw):
    """[value, unit] -> numeric field, string -> text field; units must match the template."""
    definitions = {f["id"]: f for f in question.get("fields", [])}
    fields = {}
    for name, value in (raw or {}).items():
        definition = definitions[name]
        if isinstance(value, list):
            number, unit = value
            if unit != definition.get("unit"):
                raise ValueError(f"{question['id']}.{name}: unit {unit!r} != {definition.get('unit')!r}")
            fields[name] = {"value": number, "unit": unit}
        else:
            fields[name] = {"value": value, "unit": definition.get("unit")}
    return fields


def build_view(spec, case, topic=None):
    """Saved records, repair rounds and the page projection for one case."""
    topic = topic or load_topic(spec["template"])
    questions = {q["id"]: q for q in topic["questions"]}
    plan = build_plan(topic, {})
    batches = plan["capture_batches"]
    groups = {**spec["shared"], **spec.get("extra_records", {})}
    records = []

    def add(item, supersede=False):
        q = questions[item["q"]]
        if item["option"] not in {o["id"] for o in q["options"]}:
            raise ValueError(f"{item['q']}: unknown option {item['option']}")
        payload = {"question_id": item["q"], "option_ids": [item["option"]],
                   "fields": _fields(q, item.get("fields")), "note": item.get("note", ""),
                   "unavailable_reason": item.get("unavailable_reason", "")}
        if item.get("batch"):
            payload["batch_id"] = batches[item["batch"]]
        previous = None
        if supersede:
            previous = next(r for r in reversed(records) if r["payload"]["question_id"] == item["q"])
        revision = len(records) + 1
        records.append({"id": _id(case["id"], "record", revision), "created_revision": revision,
                        "supersedes_id": previous["id"] if previous else None,
                        "correction_reason": "维修后复检" if previous else None, "payload": payload})

    for group in case["records"]:
        for item in groups[group]:
            add(item)
    rounds = []
    for number, use in enumerate(case.get("repairs", []), start=1):
        repair = spec["repairs"][use["use"]]
        retest = use.get("retest")
        round_id = _id(case["id"], "round", number)
        rounds.append({"id": round_id, "area_id": repair["area"],
            "repair_action": repair["action"], "repair_note": repair.get("note", ""),
            "pre_repair_revision": len(records),
            "retest_status": "retested" if retest else "pending",
            "retest_condition": retest["condition"] if retest else None,
            "retest_outcome": retest["outcome"] if retest else None,
            "retest_evidence": retest["evidence"] if retest else None, "next_area_id": None,
            "created_at": f"2026-10-01T0{number}:00:00+00:00",
            "retested_at": f"2026-10-01T0{number}:30:00+00:00" if retest else None})
        for item in use.get("rechecks", []):
            add(item, supersede=True)

    binding = {"template_id": spec["template"]["template_id"], "version": spec["template"]["version"],
               "content_hash": content_hash(topic)}
    intake = {"topic_plan": plan, "template_binding": binding}
    projection = project_template({"intake_snapshot": intake}, records, {}, topic)
    superseded = {r["supersedes_id"] for r in records if r["supersedes_id"]}
    return {"topic": topic, "plan": plan, "view": projection,
        "case": {"id": _id(case["id"], "case"), "revision": len(records) + 1,
                 "vehicle": spec["vehicle"], "fault_description": spec["complaint"],
                 "fault_codes": spec["fault_codes"], "intake_snapshot": intake},
        "observations": [{"id": r["id"], "question_id": r["payload"]["question_id"],
                          "payload": r["payload"], "round_id": None,
                          "created_revision": r["created_revision"], "supersedes_id": r["supersedes_id"],
                          "correction_reason": r["correction_reason"],
                          "effective": r["id"] not in superseded} for r in records],
        "repair_rounds": rounds}


# How much manual text an analysis sends. Only "current" is what the product does; the
# others exist to compare advice quality against the amount of text (experiment only).
READING_MODES = {
    "current": "现在的方式：已填题和未填题都检索，每题前 3 个章节，加必带章节",
    "full": "整份资料全发",
    "answered": "只按已填题检索，每题前 3 个章节，加必带章节",
    "answered-top1": "只按已填题检索，每题只取第 1 个章节，不带必带章节",
}


@contextmanager
def reading_mode(mode):
    """Run the product's own section selection with one setting changed for the experiment."""
    if mode not in READING_MODES:
        raise ValueError("Unknown reading mode: " + mode)
    with ExitStack() as stack:
        if mode in ("answered", "answered-top1"):
            original = analysis_context.queries_for
            stack.enter_context(patch.object(analysis_context, "queries_for", lambda payload: [
                q for q in original(payload) if q["reason"] == "recorded_question"]))
        if mode == "answered-top1":
            stack.enter_context(patch.object(analysis_context, "_always_include", lambda *_: []))
            stack.enter_context(patch.object(area_analysis_service, "enrich",
                                             partial(analysis_context.enrich, top_k=1)))
        yield


def send_full_documents(payload):
    """The "full" mode: every document goes whole, recorded in the guide like the fallback."""
    for document in payload["documents"]:
        document.pop("analysis_extracts", None)
    for guide in payload["reference_reading_guide"]:
        guide["mode"] = "full_documents_experiment"
        for entry in guide["documents"]:
            entry.update(status="full_body_retained", sections=[], result_methods=[])
    return payload


def build_payload(spec, case, *, topic=None, references=None, embeddings=None,
                  max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS, reading="current"):
    """Mirror AreaAnalysisService._payload for the combined (matched areas) analysis.

    Pass the local vector model as embeddings to choose sections exactly as the service
    does; without it sections are chosen by exact codes and keywords only. reading picks
    an experiment mode from READING_MODES; "current" is the product behaviour.
    """
    topic = topic or load_topic(spec["template"])
    references = deepcopy(references if references is not None else load_references(spec["template"]))
    view = build_view(spec, case, topic)
    area_of = {q["id"]: q["area_id"] for q in topic["questions"]}
    recorded = {area_of[o["question_id"]] for o in view["observations"] if o["effective"]}
    recorded |= {r["area_id"] for r in view["repair_rounds"]}
    with reading_mode(reading):
        payload = build_matched_input(view, {area: references.get(area, []) for area in recorded}, embeddings)
    if reading == "full":
        send_full_documents(payload)
    payload["max_output_tokens"] = max_output_tokens
    return payload


def sent_text(payload):
    """Everything the model actually received: system prompt and the sent JSON."""
    sent = {k: v for k, v in model_payload(payload).items() if k != "max_output_tokens"}
    return MATCHED_SYSTEM_PROMPT + json.dumps(sent, ensure_ascii=False)


# ---------------------------------------------------------------- grading

def _steps(result, where):
    current = [("steps", i, s) for i, s in enumerate(result.get("steps") or [])]
    deferred = [(f"conditional_branches[{b}]", i, s)
                for b, branch in enumerate(result.get("conditional_branches") or [])
                for i, s in enumerate(branch.get("steps") or [])]
    return {"steps": current, "branches": deferred, "all": current + deferred}[where]


def _hits(step, check):
    """Why a step matches a check: shared question IDs and/or a text match in title/action."""
    reasons = []
    shared = sorted(set(step.get("question_ids") or []) & set(check.get("question_ids", [])))
    if shared:
        reasons.append("题号 " + ",".join(shared))
    if check.get("text"):
        text = f"{step.get('title') or ''} {step.get('action') or ''}"
        found = re.search(check["text"], text)
        if found:
            reasons.append(f"文字“{found.group(0)}”")
    return reasons


def _label(location, index, step):
    return f"{location}[{index}]「{(step.get('title') or step.get('action') or '')[:40]}」"


def check_result(check, result):
    kind = check["type"]
    if kind == "first_step_kind":
        steps = result.get("steps") or []
        actual = steps[0].get("kind") if steps else None
        return actual in check["kinds"], f"第一步类型：{actual or '没有步骤'}"
    if kind == "any_step_targets":
        for location, index, step in _steps(result, check["where"]):
            if check.get("kinds") and step.get("kind") not in check["kinds"]:
                continue
            reasons = _hits(step, check)
            if reasons:
                return True, f"{_label(location, index, step)}：{'；'.join(reasons)}"
        return False, "没有找到符合的步骤"
    if kind == "no_step_targets":
        offending = []
        for location, index, step in _steps(result, check["where"]):
            if step.get("kind") not in check["kinds"]:
                continue
            reasons = _hits(step, check)
            if reasons:
                offending.append(f"{_label(location, index, step)}：{'；'.join(reasons)}")
        return not offending, "；".join(offending) or "没有"
    raise ValueError("Unknown check type: " + kind)


# A number with a unit, as written in specifications: 0.5 bar, 150 kPa, 8 Nm, 5 V, 80 °C.
# A slash series shares the unit: "1450/1500/1580 hPa" is three values.
NUMBER = r"[0-9]+(?:[.,][0-9]+)?"
UNITS = ("mbar", "bar", "kPa", "hPa", "psi", "N·m", "Nm", "mm", "cm", "mV", "V", "kΩ", "Ω", "°C", "℃",
         "ms", "rpm", "r/min", "mA", "A", "g/s", "kg/h", "%")
VALUE = re.compile(rf"(?<![0-9.,/])({NUMBER}(?:\s*/\s*{NUMBER})*)\s*({'|'.join(map(re.escape, UNITS))})(?![A-Za-z])")


def _number(number):
    number = str(number).replace(",", ".")
    return number.rstrip("0").rstrip(".") if "." in number else number


def _unit(unit):
    unit = (unit or "").split(" ")[0]  # "hPa absolute" -> "hPa"
    return {"℃": "°C", "N·m": "Nm", "r/min": "rpm"}.get(unit, unit)


def _values(text):
    return {(_number(n), _unit(unit)) for series, unit in VALUE.findall(text) for n in series.split("/")}


def _numbers(value):
    """Every number the model was given as data: recorded fields, targets, rule results."""
    if isinstance(value, bool):
        return set()
    if isinstance(value, (int, float)):
        return {_number(value)}
    items = value.values() if isinstance(value, dict) else value if isinstance(value, list) else []
    return set().union(*(_numbers(item) for item in items)) if items else set()


def _advice_text(value, key=""):
    """Readable text of the advice: IDs and enum fields are left out."""
    if isinstance(value, dict):
        return " ".join(_advice_text(v, k) for k, v in value.items())
    if isinstance(value, list):
        return " ".join(_advice_text(v, key) for v in value)
    if isinstance(value, str) and not (key.endswith("id") or key.endswith("ids") or key == "kind"):
        return value
    return ""


def grounding_checks(payload, result):
    """Codes and specified values in the advice must appear in what the model was given.

    Catches invented part/tool/fault codes and specification numbers. A value counts as
    given when the same number and unit are in the sent text, or the number is in the sent
    data (recorded fields and rule results carry units separately). A value the model
    computed itself (a difference, a converted unit) still shows up here: read the detail.
    """
    sent, advice = sent_text(payload), _advice_text(result)
    codes = sorted(identifiers(advice) - identifiers(sent))
    given, numbers = _values(sent), _numbers(model_payload(payload))
    values = sorted(f"{n} {u}" for n, u in _values(advice) if (n, u) not in given and n not in numbers)
    return [
        {"id": "codes_grounded", "label": "建议里的零件/工具/故障码都能在输入里找到",
         "passed": not codes, "detail": "、".join(codes) or "全部能找到"},
        {"id": "values_grounded", "label": "建议里带单位的数值都能在输入里找到（信号，可能是自行换算）",
         "passed": not values, "detail": "、".join(values) or "全部能找到"},
    ]


HUMAN_GROUNDING = "建议里有没有在资料和记录中找不到依据的具体说法（数值、零件、操作方法）？如有，请写出来。"


def generic_checks(payload, result):
    """Checks every case gets: no invented references, retired fields left empty."""
    known = {
        "question_ids": {q["id"] for q in payload["questions"]},
        "basis_observation_ids": {str(o["id"]) for o in payload["observations"]},
        "source_ids": {d["id"] for d in payload["documents"]},
    }
    unknown = []
    for location, index, step in _steps(result, "all"):
        for field, allowed in known.items():
            for value in step.get(field) or []:
                if str(value) not in allowed:
                    unknown.append(f"{location}[{index}].{field}={value}")
    for d, direction in enumerate(result.get("directions") or []):
        for field, allowed in (("basis_observation_ids", known["basis_observation_ids"]),
                               ("counter_observation_ids", known["basis_observation_ids"]),
                               ("source_ids", known["source_ids"])):
            for value in direction.get(field) or []:
                if str(value) not in allowed:
                    unknown.append(f"directions[{d}].{field}={value}")
    for m, item in enumerate(result.get("missing") or []):
        if item.get("question_id") not in known["question_ids"]:
            unknown.append(f"missing[{m}].question_id={item.get('question_id')}")
    filled = [name for name in ("verification", "if_unresolved") if (result.get(name) or "").strip()]
    return [
        {"id": "refs_exist", "label": "引用的题号/记录/资料都存在（没有编造）",
         "passed": not unknown, "detail": "；".join(unknown[:10]) or "全部存在"},
        {"id": "retired_fields_empty", "label": "\"整体复检\"和\"仍未解决\"两栏留空",
         "passed": not filled, "detail": "、".join(filled) or "均为空"},
    ]


def grade(case, payload, result):
    graded = generic_checks(payload, result) + grounding_checks(payload, result)
    for check in case["checks"]:
        passed, detail = check_result(check, result)
        graded.append({"id": check["id"], "label": check["label"], "passed": passed, "detail": detail})
    return graded
