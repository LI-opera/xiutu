"""Migrate the local workspace to the current schema, install the repository's manuals, chunk and embed them.

Stop the owned services first (wp15_workbench stop). Uses the same environment as the launched
API and worker, so the stored vectors come from the model analyses will query with.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.infrastructure.db_target import validate_target  # noqa: E402
from app.infrastructure.schema_version import EXPECTED_REVISION  # noqa: E402
from scripts.seed_area_references import backfill_always_include, index, latest_versions, seed  # noqa: E402
from scripts.wp15_workbench import STATE, environment  # noqa: E402

KNOWN = {"0019_case_area_rankings", "0020_area_analysis", "0021_area_input_identity",
         "0022_area_analysis_failed_retry", "0023_template_repair_retest", "0024_reference_ingest",
         "0025_reference_vehicle", EXPECTED_REVISION}


def main():
    no_vectors = "--no-vectors" in sys.argv[1:]
    env = environment(json.loads(STATE.read_text(encoding="utf-8")), ranking_local_testing=False)
    os.environ.update(env)
    target = validate_target(env["DATABASE_URL"], "migration")
    engine = create_engine(target.sqlalchemy_url(), connect_args=target.connect_kwargs())
    with engine.connect() as conn:
        before = conn.execute(text("select version_num from alembic_version")).scalar_one()
    if before not in KNOWN:
        raise RuntimeError("Unexpected migration version; no changes made")
    command.upgrade(Config(str(ROOT / "alembic.ini")), EXPECTED_REVISION)
    with engine.begin() as conn:
        installed = seed(conn)
        filled = backfill_always_include(conn)
        targets = latest_versions(conn)
    embedder = None
    if not no_vectors:
        from app.services.reference_ingest import load_embedder
        embedder = load_embedder()
    # Index what analyses read: the latest version of every manual.
    indexed = index(engine, targets, embedder)
    print(json.dumps({"before": before, "after": EXPECTED_REVISION, "manuals_listed": len(installed),
                      "always_include_filled": filled, "latest_versions": len(targets),
                      "indexed": indexed, "model_calls": 0}, ensure_ascii=False, indent=2))
    engine.dispose()


if __name__ == "__main__":
    main()
