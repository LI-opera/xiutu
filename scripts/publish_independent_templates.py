"""Validate and atomically add template versions (resources/templates/<bundle>/relations.json).

Dry-run is the default. --apply uses only the owned local workbench database target.
Existing template versions and case snapshots are never updated. Manuals are installed
separately (install_area_references.py); they are not tied to templates.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.seed_workbench_templates import build_templates  # noqa: E402
from scripts.seed_workbench_templates import seed as seed_templates  # noqa: E402


def preflight(config_path):
    candidates = list(build_templates(config_path))
    return {"templates": [{"template_id": relation["template_id"], "version": relation["version"],
                            "areas": len(topic["areas"]), "questions": len(topic["questions"])}
                           for relation, topic in candidates],
            "database_writes": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = preflight(args.config.resolve())
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
        print(json.dumps({"database": target.database, "templates": installed},
                         ensure_ascii=False, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
