"""Explicit versioned import. Runtime reads DB bodies, never these source paths."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from sqlalchemy import select, update
from app.infrastructure.orm import area_reference_documents as documents, area_reference_bindings as bindings
from app.infrastructure.orm import workbench_templates

MANIFEST = ROOT / "backend/app/topics/area_reference_manifest_v1.json"
DEFAULT_PACKAGE = ROOT / "resources/knowledge/tayron"


def extract_sections(body, headings=None):
    if not headings:
        return body
    sections = re.split(r"(?=^## )", body, flags=re.MULTILINE)
    by_heading = {section.splitlines()[0].strip(): section.rstrip() for section in sections if section.strip()}
    missing = set(headings) - set(by_heading)
    if missing:
        raise ValueError(f"Missing source headings: {sorted(missing)}")
    return "\n\n".join(by_heading[heading] for heading in headings)


def build_documents(package, manifest):
    package = package.resolve()
    for entry in manifest["documents"]:
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


READING = ROOT / "backend/app/topics/reading_documents_v1.json"


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


def bound_versions(conn):
    """Every document version an area currently reads, across all template versions."""
    return {(row.document_id, row.document_version) for row in conn.execute(
        select(bindings.c.document_id, bindings.c.document_version).distinct())}


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


def seed(conn, package=DEFAULT_PACKAGE, manifest_path=MANIFEST):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    templates = list(conn.execute(select(workbench_templates).where(
        workbench_templates.c.template_id.in_(manifest["template_ids"]),
        workbench_templates.c.version == manifest["template_version"])).mappings())
    if len(templates) != len(manifest["template_ids"]):
        raise ValueError("Install the matching templates first")
    result = []
    for entry, doc in build_documents(package, manifest):
        prior = conn.execute(select(documents).where(documents.c.document_id == doc["document_id"],
            documents.c.version == doc["version"])).mappings().first()
        if prior and any(prior[key] != doc[key] for key in doc):
            raise ValueError("Existing document changed: publish a new version")
        if not prior:
            conn.execute(documents.insert().values(**doc, always_include=always_include(doc)))
        elif not prior["always_include"] and always_include(doc):
            # Rows imported before 0024 get their reviewed always-sent sections once.
            conn.execute(update(documents).where(documents.c.document_id == doc["document_id"],
                documents.c.version == doc["version"]).values(always_include=always_include(doc)))
        for template in templates:
            if entry["area_id"] not in {a["id"] for a in template["content_json"]["areas"]}:
                continue
            relation = {"template_id": template["template_id"], "template_version": template["version"],
                "area_id": entry["area_id"], "document_id": doc["document_id"], "document_version": doc["version"]}
            prior_binding = conn.execute(select(bindings).where(*[
                bindings.c[key] == relation[key] for key in ("template_id", "template_version", "area_id", "document_id")
            ])).mappings().first()
            if prior_binding and dict(prior_binding) != relation:
                raise ValueError("Binding changed: explicit version update required")
            if not prior_binding:
                conn.execute(bindings.insert().values(**relation))
            result.append({**relation, "title": doc["title"], "chars": len(doc["body"]),
                           "coverage": entry["coverage"]})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--no-vectors", action="store_true",
                        help="store chunks only (no local embedding model on this machine)")
    args = parser.parse_args()
    from scripts.wp15_workbench import STATE, environment
    from app.infrastructure.db_target import validate_target
    from sqlalchemy import create_engine
    env = environment(json.loads(STATE.read_text(encoding="utf-8")))
    # Same settings as the launched API and worker, so vectors use the model they will query with.
    import os
    os.environ.update(env)
    target = validate_target(env["DATABASE_URL"], "migration")
    engine = create_engine(target.sqlalchemy_url(), connect_args=target.connect_kwargs())
    with engine.begin() as conn:
        relations = seed(conn, args.package, args.manifest)
    print(json.dumps(relations, ensure_ascii=False, indent=2))
    embedder = None
    if not args.no_vectors:
        from app.services.reference_ingest import load_embedder
        embedder = load_embedder()
    print(json.dumps(index(engine, {(r["document_id"], r["document_version"]) for r in relations}, embedder),
                     ensure_ascii=False, indent=2))
    engine.dispose()
