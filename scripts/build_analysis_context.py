"""Carry reviewed record roles to new template versions, or stop for manual review.

Record roles (backend/app/reading_config/record_roles_v1.json) say what kind of information a saved
record is: observation, inspection status, human judgment, disposition, ... They are bound
to exact question definitions by hash, so a new template version has no roles until it gets
its own entries. This script fills them in and never guesses. Which manual sections an
analysis sends is chosen by search, not configured here; a template without roles still gets
an analysis, with its records marked unclassified.

For every template version listed in the package's relations.json, each question takes:
  1. the entry this version already has, when its definition hash still matches;
  2. otherwise a person's review from --review (a JSON file, see below);
  3. otherwise the entry of the newest earlier reviewed version of the same template, but only
     when the option IDs are exactly the ones that entry was written for.
Anything else stops with REVIEW REQUIRED. In every case an option marked "not executed"
(not_executed_not_normal) must be classified as inspection_status.

Review file: {"questions": {"AIR-07": {"role": "observation",
                                        "option_roles": {"inserted": "observation", ...}}}}
It applies to every template version in the run that needs a review for that question ID;
an entry nobody needed is an error, so stale reviews do not linger.

Usage (from the repository root):
  python scripts/build_analysis_context.py                                  # report only
  python scripts/build_analysis_context.py --review reviewed.json --write   # update roles
  python scripts/build_analysis_context.py --relations resources/templates/<bundle>/relations.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from app.services.analysis_context import ROLES, ROLES_CONFIG, digest  # noqa: E402

BUNDLE = ROOT / "resources/templates/tayron-v2"
RELATIONS = BUNDLE / "relations.json"


class ReviewRequired(ValueError):
    """Something changed in a way only a person can classify."""


def version_key(version):
    """Same ordering as template matching: numeric parts compare as numbers."""
    return tuple((1, int(part)) if part.isdecimal() else (0, part.casefold())
                 for part in re.split(r"(\d+)", version) if part)


def _entry(config, template_id, version):
    found = [t for t in config["templates"] if t["template_id"] == template_id and t["version"] == version]
    return found[0]["questions"] if found else {}


def _previous(config, relation):
    earlier = [t for t in config["templates"] if t["template_id"] == relation["template_id"]
               and version_key(t["version"]) < version_key(relation["version"])]
    return max(earlier, key=lambda t: version_key(t["version"])) if earlier else None


def _check(where, question, spec):
    option_ids = {o["id"] for o in question.get("options", [])}
    option_roles = spec.get("option_roles", {})
    if option_roles and set(option_roles) != option_ids:
        raise ReviewRequired(f"{where}: options changed {sorted(set(option_roles) ^ option_ids)}")
    if spec.get("role") not in ROLES or not set(option_roles.values()) <= ROLES:
        raise ReviewRequired(f"{where}: unknown role")
    for o in question.get("options", []):
        role = option_roles.get(o["id"], spec["role"])
        if o.get("status_semantics") == "not_executed_not_normal" and role != "inspection_status":
            raise ReviewRequired(f"{where}/{o['id']}: not executed but classified as {role}")


def derive_template(config, relation, topic, reviews=None, used=None):
    reviews = reviews or {}
    current = _entry(config, relation["template_id"], relation["version"])
    previous = _previous(config, relation)
    questions = {}
    for q in topic["questions"]:
        where = f"{relation['template_id']} v{relation['version']} {q['id']}"
        definition = digest(q)
        kept = current.get(q["id"])
        if kept and kept["definition_hash"] == definition:
            spec = {k: v for k, v in kept.items() if k != "definition_hash"}
        elif q["id"] in reviews:
            spec = reviews[q["id"]]
            if used is not None:
                used.add(q["id"])
        elif previous is None:
            raise ReviewRequired(f"{relation['template_id']}: no earlier reviewed version to carry from")
        elif q["id"] not in previous["questions"]:
            raise ReviewRequired(f"{where}: new question, classify its role manually")
        else:
            spec = {k: v for k, v in previous["questions"][q["id"]].items() if k != "definition_hash"}
        _check(where, q, spec)
        questions[q["id"]] = {"definition_hash": definition, **spec}
    return {"template_id": relation["template_id"], "version": relation["version"],
            "content_hash": digest(topic), "questions": questions}


def build(config, relations_path=RELATIONS, reviews=None):
    relations_path = Path(relations_path)
    relations = json.loads(relations_path.read_text(encoding="utf-8"))["relations"]
    relations = sorted(relations, key=lambda r: (r["template_id"], version_key(r["version"])))
    working, templates, used = json.loads(json.dumps(config)), [], set()
    for relation in relations:
        topic = json.loads((relations_path.parent / relation["content_file"]).read_text(encoding="utf-8"))
        derived = derive_template(working, relation, topic, reviews, used)
        identity = (derived["template_id"], derived["version"])
        # Later versions in the same run carry from this one, so it replaces any older entry now.
        working["templates"] = [t for t in working["templates"]
                                if (t["template_id"], t["version"]) != identity] + [derived]
        templates.append(derived)
    unused = set(reviews or {}) - used
    if unused:
        raise ReviewRequired(f"review entries not needed by any template: {sorted(unused)}")
    # Replace entries of the same identity in place; keep every other reviewed entry unchanged.
    new = {(t["template_id"], t["version"]): t for t in templates}
    result = dict(config)
    result["templates"] = [new.pop((t["template_id"], t["version"]), t) for t in config["templates"]]
    result["templates"] += list(new.values())
    return result, templates


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--relations", type=Path, default=RELATIONS)
    parser.add_argument("--review", type=Path, help="JSON file with roles a person reviewed")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    config = json.loads(ROLES_CONFIG.read_text(encoding="utf-8"))
    reviews = json.loads(args.review.read_text(encoding="utf-8"))["questions"] if args.review else None
    try:
        result, templates = build(config, args.relations.resolve(), reviews)
    except ReviewRequired as error:
        print("REVIEW REQUIRED:", error)
        raise SystemExit(1)
    for t in templates:
        print(f"template {t['template_id']} v{t['version']}: {len(t['questions'])} questions")
    changed = result != config
    if args.write and changed:
        ROLES_CONFIG.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("written:", ROLES_CONFIG.relative_to(ROOT))
    else:
        print("up to date" if not changed else "dry run: pass --write to update")


if __name__ == "__main__":
    main()
