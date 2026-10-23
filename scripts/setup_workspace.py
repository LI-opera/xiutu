"""Validate bundled resources; initialize only an empty local workspace on --apply."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--enable-ai-budget", action="store_true")
    args = parser.parse_args()
    from scripts.publish_independent_templates import preflight
    from scripts.seed_area_references import DEFAULT_PACKAGE as package
    from scripts.seed_area_references import build_documents, load_manuals

    relations = ROOT / "resources/templates/tayron-v2/relations.json"
    report = preflight(relations)
    report["manuals"] = len(list(build_documents(package, load_manuals())))
    if args.apply:
        from alembic import command
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from app.config import load_settings
        from app.infrastructure.uow import make_engine
        from sqlalchemy import inspect, text

        from scripts.seed_area_references import seed as seed_references
        from scripts.seed_workbench_templates import seed as seed_templates

        settings = load_settings(project_env=True)
        engine = make_engine(settings.database_url.get_secret_value() if settings.database_url else None)
        if engine is None:
            raise RuntimeError("Set DATABASE_URL locally before applying")
        config = Config(str(ROOT / "alembic.ini"))
        head = ScriptDirectory.from_config(config).get_current_head()
        try:
            with engine.connect() as conn:
                tables = set(inspect(conn).get_table_names())
                if "cases" in tables and conn.execute(text("SELECT count(*) FROM cases")).scalar_one():
                    raise RuntimeError("Workspace contains cases; use the existing runtime, not initialization")
                if tables:
                    if "alembic_version" not in tables:
                        raise RuntimeError("Existing unversioned schema; no changes made")
                    version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                    if version != head:
                        raise RuntimeError("Existing older schema requires an explicit migration plan")
            if not tables:
                # Settings for migration are explicit; never switch to another database.
                previous = os.environ.get("DATABASE_URL")
                os.environ["DATABASE_URL"] = settings.database_url.get_secret_value()
                try:
                    command.upgrade(config, "head")
                finally:
                    if previous is None:
                        os.environ.pop("DATABASE_URL", None)
                    else:
                        os.environ["DATABASE_URL"] = previous
            with engine.begin() as conn:
                templates = seed_templates(conn, relations)
                manuals = seed_references(conn, package)
            report.update(database_writes=True, installed_templates=len(templates),
                          installed_manuals=len(manuals))
        finally:
            engine.dispose()
    if args.enable_ai_budget:
        from app.infrastructure.model_budget import LIVE_LEDGER, BudgetLedger

        ledger = BudgetLedger(LIVE_LEDGER)
        if LIVE_LEDGER.exists():
            ledger.read()
            report["ai_budget"] = "existing_preserved"
        else:
            ledger.initialize("Explicit local user authorization via setup_workspace --enable-ai-budget")
            report["ai_budget"] = "initialized_no_model_call"
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
