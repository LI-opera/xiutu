"""Trusted configuration selects adapters. Immutable index fingerprints select queries."""

from functools import lru_cache
from typing import Protocol

from app.infrastructure.bge_gateway import CONFIG as BGE
from app.infrastructure.bge_gateway import BGEGateway
from app.infrastructure.embedding_gateway import CONFIG as E5
from app.infrastructure.embedding_gateway import EmbeddingError, gateway


class Embedding(Protocol):
    config: dict

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class LLM(Protocol):
    def generate_structured(self, schema, messages): ...
    def invoke_with_tools(self, messages, tool_schemas): ...
    def health_config(self): ...


def supports_fingerprint(config):
    return config in (E5, BGE)


def check_fingerprint(config):
    if config not in (E5, BGE):
        raise EmbeddingError("INDEX_CONFIG_UNAVAILABLE")
    return config


def selected_config(settings):
    provider = getattr(settings, "embedding_provider", "local_e5")
    if provider == "local_e5":
        for key, expected in [
            ("embedding_model", E5["model"]),
            ("embedding_revision", E5["revision"]),
            ("embedding_dimension", 384),
        ]:
            actual = getattr(settings, key, None)
            if actual is not None and actual != expected:
                raise EmbeddingError("EMBEDDING_CONFIG_MISMATCH")
        return E5
    if provider == "local_bge_m3":
        for k, v in [
            ("embedding_model", BGE["model"]),
            ("embedding_revision", BGE["revision"]),
            ("embedding_dimension", 1024),
        ]:
            actual = getattr(settings, k, None)
            if actual is not None and actual != v:
                raise EmbeddingError("EMBEDDING_CONFIG_MISMATCH")
        return BGE
    raise EmbeddingError("EMBEDDING_PROVIDER_UNKNOWN")


@lru_cache(maxsize=2)
def bge(directory):
    return BGEGateway(directory)


def embedding_factory(settings, config=None):
    config = check_fingerprint(config or selected_config(settings))
    if config == E5:
        return gateway(str(settings.embedding_path))
    path = getattr(settings, "embedding_model_path", None)
    if path is None or not path.is_dir():
        raise EmbeddingError("MODEL_PATH_UNAVAILABLE")
    return bge(str(path))


def llm_factory(settings, **kwargs):
    if settings.llm_provider != "deepseek":
        raise ValueError("LLM_PROVIDER_UNKNOWN")
    from app.infrastructure.model_gateway import DeepSeekGateway

    return DeepSeekGateway(settings, **kwargs)
