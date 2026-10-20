"""Carry reviewed reading-guide entries to a new template version, or stop for manual review.

The reading guide (backend/app/topics/analysis_context_v1.json) binds roles and source sections
to exact question definitions and document bodies by hash. A new template version therefore
matches nothing until it gets its own entries. This script derives them from the previously
reviewed version and never guesses: every carried value must pass the checks below.

Checks per question:
  - the previous version already classified this question ID;
  - the option IDs are exactly the ones the previous roles were written for;
  - an option marked "not executed" (not_executed_not_normal) is classified as inspection_status;
  - every referenced section exists in the new document entries.
Checks per document:
  - the new body is byte-identical to a configured version, so section offsets stay valid.
    A changed body stops the script: its sections must be located and reviewed again.

Usage (from the repository root):
  python scripts/build_analysis_context.py          # report only, writes nothing
  python scripts/build_analysis_context.py --write  # update the reading guide in place
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from app.services.analysis_context import CONFIG, ROLES, digest  # noqa: E402

from scripts.seed_area_references import DEFAULT_PACKAGE, build_documents  # noqa: E402

BUNDLE = ROOT / "resources/templates/tayron-v2"
RELATIONS = BUNDLE / "relations.json"
MANIFEST = BUNDLE / "area_reference_manifest_v2.json"
FROM_VERSION = "1"


class ReviewRequired(ValueError):
    """Something changed in a way only a person can classify."""


def derive_documents(config, manifest, package=DEFAULT_PACKAGE):
    entries = []
    for _, doc in build_documents(package, manifest):
        same_body = [d for d in config["documents"]
                     if d["id"] == doc["document_id"] and d["content_hash"] == doc["content_hash"]]
        if not same_body:
            raise ReviewRequired(f"{doc['document_id']} v{doc['version']}: body changed; "
                                 "locate and review its sections manually")
        source = same_body[-1]
        entries.append({**source, "version": doc["version"]})
    return entries


def derive_template(config, relation, topic, documents):
    sources = [t for t in config["templates"]
               if t["template_id"] == relation["template_id"] and t["version"] == FROM_VERSION]
    if len(sources) != 1:
        raise ReviewRequired(f"{relation['template_id']}: no reviewed v{FROM_VERSION} entry to carry")
    reviewed = sources[0]["questions"]
    sections = {d["id"]: set(d["sections"]) for d in documents}
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
        refs = [spec.get("references", {})] + list(spec.get("option_references", {}).values())
        for ref in refs:
            for doc_id, ids in ref.items():
                missing = set(ids) - sections.get(doc_id, set())
                if missing:
                    raise ReviewRequired(f"{where}: sections {sorted(missing)} not in {doc_id}")
        questions[q["id"]] = {**spec, "definition_hash": digest(q)}
    return {"template_id": relation["template_id"], "version": relation["version"],
            "content_hash": digest(topic), "questions": questions}


def build(config, relations_path=RELATIONS, manifest_path=MANIFEST, package=DEFAULT_PACKAGE):
    relations = json.loads(Path(relations_path).read_text(encoding="utf-8"))
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    documents = derive_documents(config, manifest, package)
    templates = []
    for relation in relations["relations"]:
        path = Path(relations_path).parent / relation["content_file"]
        topic = json.loads(path.read_text(encoding="utf-8"))
        templates.append(derive_template(config, relation, topic, documents))
    # Replace entries of the same identity; keep every other reviewed entry unchanged.
    new_templates = {(t["template_id"], t["version"]) for t in templates}
    new_documents = {(d["id"], d["version"]) for d in documents}
    result = dict(config)
    result["templates"] = [t for t in config["templates"]
                           if (t["template_id"], t["version"]) not in new_templates] + templates
    result["documents"] = [d for d in config["documents"]
                           if (d["id"], d["version"]) not in new_documents] + documents
    return result, templates, documents


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    try:
        result, templates, documents = build(config)
    except ReviewRequired as error:
        print("REVIEW REQUIRED:", error)
        raise SystemExit(1)
    for t in templates:
        print(f"template {t['template_id']} v{t['version']}: {len(t['questions'])} questions carried")
    for d in documents:
        print(f"document {d['id']} v{d['version']}: {len(d['sections'])} sections carried")
    changed = result != config
    if args.write and changed:
        CONFIG.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("written:", CONFIG.relative_to(ROOT))
    else:
        print("up to date" if not changed else "dry run: pass --write to update")


if __name__ == "__main__":
    main()
