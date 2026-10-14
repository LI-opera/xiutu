"""Protected operator configuration, never supplied by a model or HTTP body."""

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from app.domain.policies import DomainError

TOOLS = ("search_manuals", "get_evidence_context", "get_measurement_spec")
TABLES = (
    "cases",
    "documents",
    "document_versions",
    "chunks",
    "index_versions",
    "chunk_embeddings",
    "case_evidence",
    "measurement_specs",
    "alembic_version",
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Binding(Strict):
    actor_id: UUID
    case_id: UUID
    revision: int = Field(ge=0)
    manifest: list[dict] = Field(max_length=1000)
    profile: Literal["formal", "synthetic"]
    allowlist: list[str] = Field(default_factory=lambda: list(TOOLS))

    @model_validator(mode="after")
    def allowed(self):
        if not set(self.allowlist) <= set(TOOLS) or len(set(self.allowlist)) != len(self.allowlist):
            raise ValueError("Invalid readonly allowlist")
        return self

    def context(self):
        return self.model_dump()


class Grant(Binding):
    token_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    expires_at: datetime

    def binding(self):
        return Binding.model_validate(self.model_dump(exclude={"token_hash", "expires_at"}))


class Database(Strict):
    deployment: Literal["loopback", "compose"]
    name: str = Field(pattern=r"^(xiutu_dev|xiutu_test_[a-z0-9_]{1,40})$")
    user: str = Field(pattern=r"^xiutu_mcp_[a-z0-9_]{1,40}$")
    password: SecretStr

    def engine(self):
        if any(k.upper().startswith("PG") and v for k, v in os.environ.items()):
            raise ValueError("PG environment is not allowed for MCP")
        host, port = ("127.0.0.1", 5433) if self.deployment == "loopback" else ("postgres", 5432)
        kwargs = dict(
            host=host,
            port=port,
            dbname=self.name,
            user=self.user,
            password=self.password.get_secret_value(),
            connect_timeout=2,
            passfile=os.devnull,
            options="-c default_transaction_read_only=on",
        )
        if self.deployment == "loopback":
            kwargs["hostaddr"] = host
        return create_engine(
            URL.create("postgresql+psycopg"),
            connect_args=kwargs,
            hide_parameters=True,
            pool_size=3,
            max_overflow=2,
            pool_timeout=2,
        )


class ServerConfig(Strict):
    database: Database
    grants: list[Grant] = Field(min_length=1, max_length=100)
    hosts: list[str] = Field(min_length=1, max_length=20)
    origins: list[str] = Field(default_factory=list, max_length=20)
    embedding_path: Path
    embedding_model_path: Path | None = None
    embedding_provider: str = "local_e5"
    data_path: Path
    retrieval_profile: Literal["formal", "synthetic"] = "formal"

    @model_validator(mode="after")
    def isolated(self):
        if self.retrieval_profile == "synthetic" and not self.database.name.startswith(
            "xiutu_test_"
        ):
            raise ValueError("Synthetic MCP requires isolated test database")
        if any(g.profile != self.retrieval_profile for g in self.grants):
            raise ValueError("Grant profile differs from server profile")
        if len({g.token_hash for g in self.grants}) != len(self.grants):
            raise ValueError("Duplicate credential mapping")
        return self

    def authenticate(self, authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise DomainError("MCP_UNAUTHORIZED", "Credential required", 401)
        raw = authorization[7:]
        if not 32 <= len(raw) <= 512:
            raise DomainError("MCP_UNAUTHORIZED", "Credential invalid", 401)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        for grant in self.grants:
            if hmac.compare_digest(digest, grant.token_hash):
                if grant.expires_at.tzinfo is None or grant.expires_at <= datetime.now(
                    timezone.utc
                ):
                    break
                return grant.binding()
        raise DomainError("MCP_UNAUTHORIZED", "Credential invalid", 401)


def read_config(path, model):
    p = Path(path).absolute()
    for parent in (p, *p.parents):
        if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise ValueError("Reparse configuration path forbidden")
    if not p.is_file() or p.stat().st_size > 1048576:
        raise ValueError("Protected configuration missing or too large")
    return model.model_validate(json.loads(p.read_text(encoding="utf-8")))


def output_schema(name):
    from pydantic import create_model

    from app.tools.schemas import OUTPUTS, Envelope

    model = create_model(name + "_Result", __base__=Envelope, data=(OUTPUTS[name] | None, ...))
    return model.model_json_schema()
