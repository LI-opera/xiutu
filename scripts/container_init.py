"""Prepare the Docker database before the API starts: migrate, install the bundled templates and
manuals, and chunk them (with vectors when a BGE-M3 model is mounted). Safe to run on every start.

Only for the Compose deployment in deploy/docker; the local workbench uses setup_workspace.py.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]


def main():
    if not os.environ.get("CONTAINER_DB_HOST"):
        raise SystemExit("container_init.py is only for the Docker deployment (deploy/docker)")
    from alembic import command
    from alembic.config import Config
    from app.infrastructure.embedding_gateway import EmbeddingError
    from app.infrastructure.uow import make_engine

    from scripts.seed_area_references import index, latest_versions
    from scripts.seed_area_references import seed as seed_references
    from scripts.seed_workbench_templates import seed as seed_templates

    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    engine = make_engine(os.environ["DATABASE_URL"])
    try:
        # Both seeds only insert what is missing and refuse to change a stored version.
        with engine.begin() as conn:
            templates = seed_templates(conn)
            manuals = seed_references(conn)
            targets = latest_versions(conn)
        try:
            from app.services.reference_ingest import load_embedder
            embedder = load_embedder()
        except EmbeddingError:
            embedder = None  # no model mounted: chunks only; analyses send whole manuals
        indexed = index(engine, targets, embedder)
    finally:
        engine.dispose()
    print(json.dumps({"templates": len(templates), "manuals": len(manuals), "indexed": len(indexed),
                      "vectors": embedder is not None}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
