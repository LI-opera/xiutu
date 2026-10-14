"""Validate and atomically add independent template versions with references.

Dry-run is the default. --apply uses only the owned WP-15 local database target.
Existing template versions, bindings and case snapshots are never updated.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.seed_area_references import build_documents  # noqa: E402
from scripts.seed_area_references import seed as seed_references  # noqa: E402
from scripts.seed_workbench_templates import build_templates  # noqa: E402
from scripts.seed_workbench_templates import seed as seed_templates  # noqa: E402


def preflight(config_path, manifest_path, package):
    candidates = list(build_templates(config_path))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (set(manifest["template_ids"]) != {relation["template_id"] for relation, _ in candidates} or
            {manifest["template_version"]} != {relation["version"] for relation, _ in candidates}):
        raise ValueError("Reference manifest and template versions differ")
    documents = list(build_documents(package, manifest))
    areas = {area["id"] for _, topic in candidates for area in topic["areas"]}
    if {entry["area_id"] for entry, _ in documents} != areas:
        raise ValueError("Reference coverage differs from template areas")
    return {"templates": [{"template_id": relation["template_id"], "version": relation["version"],
                            "areas": len(topic["areas"]), "questions": len(topic["questions"])}
                           for relation, topic in candidates],
            "documents": len(documents), "database_writes": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = preflight(args.config.resolve(), args.manifest.resolve(), args.package.resolve())
    if not args.apply:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    from app.infrastructure.db_target import validate_target
    from sqlalchemy import create_engine

    from scripts.wp15_workbench import STATE, environment

    state = json.loads(STATE.read_text(encoding="utf-8"))
    env = environment(state, ranking_local_testing=False)
    target = validate_target(env["DATABASE_URL"], "migration")
    engine = create_engine(target.sqlalchemy_url(), connect_args=target.connect_kwargs())
    try:
        with engine.begin() as conn:
            installed = seed_templates(conn, args.config.resolve())
            references = seed_references(conn, args.package.resolve(), args.manifest.resolve())
        print(json.dumps({"database": target.database, "templates": installed,
                          "reference_bindings": len(references)}, ensure_ascii=False, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
