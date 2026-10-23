"""Install the repository's manuals (resources/knowledge/tayron/manuals.json) into the manual table.

Each manual is stored with the vehicle it applies to; nothing ties it to a template or area.
Runtime reads the stored bodies, never these source paths.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from sqlalchemy import select, update
from app.infrastructure.orm import area_reference_documents as documents

DEFAULT_PACKAGE = ROOT / "resources/knowledge/tayron"
MANUALS = DEFAULT_PACKAGE / "manuals.json"


def extract_sections(body, headings=None):
    if not headings:
        return body
    sections = re.split(r"(?=^## )", body, flags=re.MULTILINE)
    by_heading = {section.splitlines()[0].strip(): section.rstrip() for section in sections if section.strip()}
    missing = set(headings) - set(by_heading)
    if missing:
        raise ValueError(f"Missing source headings: {sorted(missing)}")
    return "\n\n".join(by_heading[heading] for heading in headings)


def load_manuals(path=MANUALS):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_documents(package, manuals):
    """(list entry, document row) for every manual; source files must match their recorded hashes."""
    package = package.resolve()
    for entry in manuals["documents"]:
        pieces = []
        sources = []
        for source in entry["sources"]:
            path = (package / source["file"]).resolve()
            if not path.is_relative_to(package):
                raise ValueError("Source outside package")
            expected_hash = (entry.get("source_hashes") or {}).get(source["file"])
            if entry.get("source_hashes") is not None and expected_hash is None:
                raise ValueError("Missing source hash: " + source["file"])
            if expected_hash and hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                raise ValueError("Source changed: " + source["file"])
            raw = path.read_text(encoding="utf-8-sig")
            pieces.append(extract_sections(raw, source.get("headings")))
            sources.append({**source, "source_hash": hashlib.sha256(raw.encode()).hexdigest()})
        body = "\n\n---\n\n".join(pieces)
        yield entry, {"document_id": entry["document_id"], "version": entry["version"],
            "title": entry["title"], "body": body,
            "content_hash": hashlib.sha256(body.encode()).hexdigest(),
            "provenance": {"sources": sources, "coverage": entry["coverage"], "images_sent": False}}


READING = ROOT / "backend/app/reading_config/reading_documents_v1.json"


def always_include(doc):
    """Reviewed always-sent sections for this exact body, carried into the document row."""
    config = json.loads(READING.read_text(encoding="utf-8"))
    for entry in config["documents"]:
        if (entry["id"], entry["version"], entry["content_hash"]) == (
                doc["document_id"], doc["version"], doc["content_hash"]):
            return entry["always_include"]
    return []


def backfill_always_include(conn):
    """Every stored version whose exact body has reviewed always-sent sections gets them once."""
    config = json.loads(READING.read_text(encoding="utf-8"))
    filled = []
    for entry in config["documents"]:
        result = conn.execute(update(documents).where(
            documents.c.document_id == entry["id"], documents.c.version == entry["version"],
            documents.c.content_hash == entry["content_hash"], documents.c.always_include == [])
            .values(always_include=entry["always_include"]))
        if result.rowcount:
            filled.append(f"{entry['id']} v{entry['version']}")
    return filled


def latest_versions(conn):
    """The version of every manual analyses read: its latest one."""
    latest = {}
    for row in conn.execute(select(documents.c.document_id, documents.c.version, documents.c.created_at)):
        rank = (int(row.version) if row.version.isdigit() else -1, row.created_at)
        if row.document_id not in latest or rank > latest[row.document_id][0]:
            latest[row.document_id] = (rank, row.version)
    return {(document_id, version) for document_id, (_, version) in latest.items()}


def index(engine, documents_seeded, embedder):
    """Chunk (and embed, when a model is given) every seeded version that has no chunks yet."""
    from app.services.reference_ingest import process
    done = []
    for document_id, version in sorted(documents_seeded):
        with engine.connect() as conn:
            row = conn.execute(select(documents.c.chunk_count, documents.c.vector_fingerprint).where(
                documents.c.document_id == document_id, documents.c.version == version)).one()
        fingerprint = embedder[1] if embedder else None
        if row.chunk_count is not None and row.vector_fingerprint == fingerprint:
            continue
        done.append(process(engine, document_id, version, embedder))
    return done


def seed(conn, package=DEFAULT_PACKAGE, manuals_path=MANUALS):
    """Insert every listed manual version that is not stored yet; never change a stored one."""
    manuals = load_manuals(manuals_path)
    vehicle = manuals["vehicle"]
    values = {"vehicle_brand": vehicle["brand"], "vehicle_model": vehicle["model"],
              "vehicle_year": vehicle.get("year"), "vehicle_engine_code": vehicle.get("engine_code")}
    result = []
    for _, doc in build_documents(package, manuals):
        prior = conn.execute(select(documents).where(documents.c.document_id == doc["document_id"],
            documents.c.version == doc["version"])).mappings().first()
        if prior and any(prior[key] != doc[key] for key in doc):
            raise ValueError("Existing document changed: publish a new version")
        if not prior:
            conn.execute(documents.insert().values(**doc, always_include=always_include(doc), **values))
        elif not prior["always_include"] and always_include(doc):
            conn.execute(update(documents).where(documents.c.document_id == doc["document_id"],
                documents.c.version == doc["version"]).values(always_include=always_include(doc)))
        result.append({"document_id": doc["document_id"], "version": doc["version"],
                       "title": doc["title"], "chars": len(doc["body"]), "new": prior is None})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--manuals", type=Path, default=MANUALS)
    parser.add_argument("--no-vectors", action="store_true",
                        help="store chunks only (no local embedding model on this machine)")
    args = parser.parse_args()
    from scripts.workbench import STATE, environment
    from app.infrastructure.db_target import validate_target
    from sqlalchemy import create_engine
    env = environment(json.loads(STATE.read_text(encoding="utf-8")), ranking_local_testing=False)
    # Same settings as the launched API and worker, so vectors use the model they will query with.
    import os
    os.environ.update(env)
    target = validate_target(env["DATABASE_URL"], "migration")
    engine = create_engine(target.sqlalchemy_url(), connect_args=target.connect_kwargs())
    with engine.begin() as conn:
        installed = seed(conn, args.package, args.manuals)
    print(json.dumps(installed, ensure_ascii=False, indent=2))
    embedder = None
    if not args.no_vectors:
        from app.services.reference_ingest import load_embedder
        embedder = load_embedder()
    print(json.dumps(index(engine, {(r["document_id"], r["version"]) for r in installed}, embedder),
                     ensure_ascii=False, indent=2))
    engine.dispose()
