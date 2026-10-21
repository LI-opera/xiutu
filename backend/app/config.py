import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.infrastructure.model_budget import MAX_MODEL_OUTPUT_TOKENS


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", hide_input_in_errors=True)
    app_mode: Literal["development", "test", "production"] = "development"
    database_url: SecretStr | None = Field(default=None, repr=False)
    data_path: Path = Path(".local-data")
    upload_max_bytes: int = Field(default=25 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    chunk_target_tokens: int = Field(default=600, ge=100, le=900)
    chunk_max_tokens: int = Field(default=900, ge=100, le=900)
    chunk_overlap_tokens: int = Field(default=80, ge=0, le=200)
    embedding_path: Path = Path(
        ".local-data/models/multilingual-e5-small/614241f622f53c4eeff9890bdc4f31cfecc418b3"
    )
    embedding_provider: Literal["local_e5", "local_bge_m3"] = "local_e5"
    embedding_model_path: Path | None = None
    embedding_model: str | None = None
    embedding_revision: str | None = None
    embedding_dimension: int | None = None
    embedding_local_files_only: Literal[True] = True

    @field_validator("embedding_local_files_only", mode="before")
    @classmethod
    def accept_true_text(cls, value):
        # .env values arrive as text; "true" from .env.example must mean True. Anything else
        # (including "false") still fails: embeddings are never downloaded at run time.
        if isinstance(value, str) and value.strip().lower() in {"true", "1", "yes"}:
            return True
        return value

    llm_provider: Literal["deepseek"] = "deepseek"
    deepseek_model: str = "deepseek-flash"
    deepseek_base_url: str = "https://api.deepseek.com"
    # Trusted server configuration for the longer WP-11 step envelope. This
    # value is never accepted from a case request or a model tool argument.
    diagnosis_max_output_tokens: int = Field(default=1536, ge=768, le=1536)
    case_analysis_max_output_tokens: int = Field(
        default=1536, ge=256, le=MAX_MODEL_OUTPUT_TOKENS, strict=True)
    area_analysis_max_output_tokens: int = Field(default=8192, ge=256, le=MAX_MODEL_OUTPUT_TOKENS)
    area_analysis_max_input_chars: int = Field(default=100000, ge=1000, le=500000)
    retrieval_profile: Literal["formal", "synthetic"] = "formal"

    @field_validator("case_analysis_max_output_tokens", mode="before")
    @classmethod
    def parse_case_analysis_output_tokens(cls, value):
        # Environment variables are strings; keep strict validation for all
        # other values instead of letting Pydantic coerce bools/floats.
        if isinstance(value, str) and value.isascii() and value.isdecimal():
            return int(value)
        return value

    @model_validator(mode="after")
    def profile_boundary(self):
        if self.retrieval_profile == "synthetic":
            from app.infrastructure.db_target import validate_target

            if self.app_mode != "test" or self.database_url is None:
                raise ValueError("Synthetic retrieval requires test mode and isolated database")
            validate_target(self.database_url.get_secret_value(), "test")
        return self

    tool_mode: Literal["local", "remote_mcp"] = "remote_mcp"
    mcp_client_config: Path | None = None

    deepseek_api_key: SecretStr | None = Field(default=None, repr=False)

    operator_token: SecretStr | None = Field(default=None, repr=False)
    operator_id: UUID = UUID("44b9f80c-7067-45e0-bbc1-7aae10dd3e2f")
    app_origin: str = "http://127.0.0.1:8020"
    auth_session_seconds: int = Field(default=3600, ge=1, le=86400)
    local_dev_auto_identity: bool = False

    @model_validator(mode="after")
    def local_identity_boundary(self):
        if self.local_dev_auto_identity:
            origin = urlsplit(self.app_origin)
            if (self.app_mode == "production" or origin.scheme != "http"
                    or origin.hostname not in {"localhost", "127.0.0.1"}):
                raise ValueError("Local auto identity requires non-production loopback HTTP")
        return self

    @field_validator("operator_token")
    @classmethod
    def validate_operator_token(cls, value):
        if value is not None and not 32 <= len(value.get_secret_value()) <= 512:
            raise ValueError("Operator token must contain 32..512 characters")
        return value

    @field_validator("app_origin")
    @classmethod
    def validate_origin(cls, value):
        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.path
            or parts.query
            or parts.fragment
            or (parts.scheme == "http" and parts.hostname not in {"localhost", "127.0.0.1"})
        ):
            raise ValueError("Origin requires HTTPS or local loopback HTTP, without path")
        _ = parts.port
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database(cls, value):
        if value is not None:
            try:
                raw = value.get_secret_value()
                if not raw.startswith(("postgresql://", "postgres://")):
                    raise ValueError()
                conninfo_to_dict(raw)
            except (ValueError, ProgrammingError):
                raise ValueError("DATABASE_URL must be a PostgreSQL URI") from None
        return value

    @field_validator("data_path")
    @classmethod
    def validate_path(cls, value):
        value = Path(os.path.abspath(value))
        legacy = Path(r"E:\Work\v4-double").resolve()
        if value == legacy or legacy in value.parents:
            raise ValueError("DATA_PATH must not point into the legacy project")
        return value


def load_settings(*, project_env=False, **overrides):
    """Explicit project-only dotenv; tests never inherit development settings."""
    if (
        not project_env
        or os.environ.get("TEST_DATABASE_URL")
        or os.environ.get("APP_MODE") == "test"
        or overrides.get("app_mode") == "test"
    ):
        return Settings(**overrides)
    # app/config.py -> app -> backend -> project
    root = Path(__file__).resolve().parents[2]
    return Settings(_env_file=root / ".env", _env_file_encoding="utf8", **overrides)
