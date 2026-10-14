"""Trusted administrator setup; never exposed as an HTTP/model tool."""

import argparse
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from app.infrastructure.db_target import validate_target
from app.infrastructure.orm import cases
from app.infrastructure.uow import make_engine
from app.mcp_server.config import TOOLS
from provision_mcp_role import provision
from sqlalchemy import select


def configure(url, case_id, directory, profile, port, model_path, data_path, bge_path=None):
    validate_target(url, "test" if profile == "synthetic" else "migration")
    dest = Path(directory).absolute()
    if not dest.is_dir() or any(dest.iterdir()):
        raise ValueError("Empty protected configuration directory required")
    engine = make_engine(url)
    try:
        with engine.connect() as c:
            row = c.execute(select(cases).where(cases.c.id == case_id)).mappings().one()
            binding = dict(
                actor_id=str(row["owner_id"]),
                case_id=str(row["id"]),
                revision=row["revision"],
                manifest=row["corpus_manifest"],
                profile=profile,
                allowlist=list(TOOLS),
            )
    finally:
        engine.dispose()
    provision(url, dest / "db-secret.json")
    database = json.loads((dest / "db-secret.json").read_text(encoding="utf8"))
    grants = []
    for name in ("application", "cli"):
        token = secrets.token_urlsafe(40)
        grants.append(
            dict(
                binding,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                expires_at=(datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
            )
        )
        (dest / (name + "-secret.json")).write_text(
            json.dumps(
                dict(url=f"http://127.0.0.1:{port}/mcp", token=token, binding=binding), indent=2
            ),
            encoding="utf8",
        )
    cfg = dict(
        database=database,
        grants=grants,
        hosts=[f"127.0.0.1:{port}"],
        origins=[],
        embedding_path=str(model_path.absolute()),
        embedding_model_path=str(bge_path.absolute()) if bge_path else None,
        data_path=str(data_path.absolute()),
        retrieval_profile=profile,
    )
    (dest / "server-secret.json").write_text(json.dumps(cfg, indent=2), encoding="utf8")
    cfg["database"]["deployment"] = "compose"
    cfg["embedding_path"] = "/models/e5"
    cfg["embedding_model_path"] = "/models/bge-m3" if bge_path else None
    cfg["data_path"] = "/manuals"
    cfg["hosts"] = [f"127.0.0.1:{port}", "127.0.0.1:8031", "manual-mcp:8031"]
    (dest / "compose-server-secret.json").write_text(json.dumps(cfg, indent=2), encoding="utf8")
    if os.name != "nt":
        for f in dest.iterdir():
            f.chmod(0o600)
    print("Created two separate expiring credentials and readonly role; secret values not printed")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--case-id", required=True, type=UUID)
    p.add_argument("--directory", required=True)
    p.add_argument("--profile", choices=["formal", "synthetic"], default="formal")
    p.add_argument("--port", type=int, default=8031)
    p.add_argument("--model-path", required=True, type=Path)
    p.add_argument("--bge-path", type=Path)
    p.add_argument("--data-path", required=True, type=Path)
    a = p.parse_args()
    try:
        if not 1024 <= a.port <= 65535:
            raise ValueError("Invalid port")
        configure(
            os.environ["DATABASE_URL"],
            a.case_id,
            a.directory,
            a.profile,
            a.port,
            a.model_path,
            a.data_path,
            a.bge_path,
        )
    except Exception:
        print(
            "Setup rejected: verify isolated target, case and protected empty directory; no secrets logged"
        )
        raise SystemExit(1)
