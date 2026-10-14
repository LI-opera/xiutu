"""Additive migration and explicit import in the existing isolated local workspace."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from scripts.wp15_workbench import STATE, environment
from scripts.seed_area_references import seed
from app.infrastructure.db_target import validate_target
from sqlalchemy import create_engine, text
from alembic import command
from alembic.config import Config


def main():
    env = environment(json.loads(STATE.read_text(encoding="utf-8")))
    target = validate_target(env["DATABASE_URL"], "migration")
    os.environ["DATABASE_URL"] = env["DATABASE_URL"]
    engine = create_engine(target.sqlalchemy_url(), connect_args=target.connect_kwargs())
    with engine.connect() as conn:
        before = conn.execute(text("select version_num from alembic_version")).scalar_one()
    if before not in {"0019_case_area_rankings", "0020_area_analysis", "0021_area_input_identity", "0022_area_analysis_failed_retry"}:
        raise RuntimeError("Unexpected migration version; no changes made")
    command.upgrade(Config(str(ROOT / "alembic.ini")), "0022_area_analysis_failed_retry")
    with engine.begin() as conn:
        relations = seed(conn)
    print(json.dumps({"before": before, "after": "0022_area_analysis_failed_retry", "bindings": relations,
                      "model_calls": 0}, ensure_ascii=False, indent=2))
    engine.dispose()


if __name__ == "__main__":
    main()
