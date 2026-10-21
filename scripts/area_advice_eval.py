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
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT, ROOT / "backend"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from app.services.area_analysis_service import build_matched_input  # noqa: E402
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


def build_payload(spec, case, *, topic=None, references=None,
                  max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS):
    """Mirror AreaAnalysisService._payload for the combined (matched areas) analysis."""
    topic = topic or load_topic(spec["template"])
    references = references if references is not None else load_references(spec["template"])
    view = build_view(spec, case, topic)
    area_of = {q["id"]: q["area_id"] for q in topic["questions"]}
    recorded = {area_of[o["question_id"]] for o in view["observations"] if o["effective"]}
    recorded |= {r["area_id"] for r in view["repair_rounds"]}
    payload = build_matched_input(view, {area: references.get(area, []) for area in recorded})
    payload["max_output_tokens"] = max_output_tokens
    return payload


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
        return actual == check["kind"], f"第一步类型：{actual or '没有步骤'}"
    if kind == "any_step_targets":
        for location, index, step in _steps(result, check["where"]):
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
    graded = generic_checks(payload, result)
    for check in case["checks"]:
        passed, detail = check_result(check, result)
        graded.append({"id": check["id"], "label": check["label"], "passed": passed, "detail": detail})
    return graded
