"""Carry reviewed record roles to a new template version, or stop for manual review.

Record roles (backend/app/reading_config/record_roles_v1.json) say what kind of information a saved
record is: observation, inspection status, human judgment, disposition, ... They are bound
to exact question definitions by hash, so a new template version has no roles until it gets
its own entries. This script derives them from the previously reviewed version and never
guesses. Which manual sections an analysis sends is chosen by search, not configured here;
a template without roles still gets an analysis, with its records marked unclassified.

Checks per question:
  - the previous version already classified this question ID;
  - the option IDs are exactly the ones the previous roles were written for;
  - an option marked "not executed" (not_executed_not_normal) is classified as inspection_status.

Usage (from the repository root):
  python scripts/build_analysis_context.py          # report only, writes nothing
  python scripts/build_analysis_context.py --write  # update the record roles in place
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from app.services.analysis_context import ROLES, ROLES_CONFIG, digest  # noqa: E402

BUNDLE = ROOT / "resources/templates/tayron-v2"
RELATIONS = BUNDLE / "relations.json"
FROM_VERSION = "1"


class ReviewRequired(ValueError):
    """Something changed in a way only a person can classify."""


def derive_template(config, relation, topic):
    sources = [t for t in config["templates"]
               if t["template_id"] == relation["template_id"] and t["version"] == FROM_VERSION]
    if len(sources) != 1:
        raise ReviewRequired(f"{relation['template_id']}: no reviewed v{FROM_VERSION} entry to carry")
    reviewed = sources[0]["questions"]
    questions = {}
    for q in topic["questions"]:
        where = f"{relation['template_id']} v{relation['version']} {q['id']}"
        spec = reviewed.get(q["id"])
        if spec is None:
            raise ReviewRequired(f"{where}: new question, classify its role manually")
        option_ids = {o["id"] for o in q.get("options", [])}
        option_roles = spec.get("option_roles", {})
        if option_roles and set(option_roles) != option_ids:
            raise ReviewRequired(f"{where}: options changed {sorted(set(option_roles) ^ option_ids)}")
        if spec["role"] not in ROLES or not set(option_roles.values()) <= ROLES:
            raise ReviewRequired(f"{where}: unknown role")
        for o in q.get("options", []):
            role = option_roles.get(o["id"], spec["role"])
            if o.get("status_semantics") == "not_executed_not_normal" and role != "inspection_status":
                raise ReviewRequired(f"{where}/{o['id']}: not executed but classified as {role}")
        questions[q["id"]] = {**spec, "definition_hash": digest(q)}
    return {"template_id": relation["template_id"], "version": relation["version"],
            "content_hash": digest(topic), "questions": questions}


def build(config, relations_path=RELATIONS):
    relations = json.loads(Path(relations_path).read_text(encoding="utf-8"))
    templates = []
    for relation in relations["relations"]:
        topic = json.loads((Path(relations_path).parent / relation["content_file"]).read_text(encoding="utf-8"))
        templates.append(derive_template(config, relation, topic))
    # Replace entries of the same identity; keep every other reviewed entry unchanged.
    new = {(t["template_id"], t["version"]) for t in templates}
    result = dict(config)
    result["templates"] = [t for t in config["templates"]
                           if (t["template_id"], t["version"]) not in new] + templates
    return result, templates


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    config = json.loads(ROLES_CONFIG.read_text(encoding="utf-8"))
    try:
        result, templates = build(config)
    except ReviewRequired as error:
        print("REVIEW REQUIRED:", error)
        raise SystemExit(1)
    for t in templates:
        print(f"template {t['template_id']} v{t['version']}: {len(t['questions'])} questions carried")
    changed = result != config
    if args.write and changed:
        ROLES_CONFIG.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("written:", ROLES_CONFIG.relative_to(ROOT))
    else:
        print("up to date" if not changed else "dry run: pass --write to update")


if __name__ == "__main__":
    main()
