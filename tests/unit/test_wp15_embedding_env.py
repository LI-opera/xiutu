"""The launched API and worker use the project's configured embedding model, not the E5 default."""
from pathlib import Path
from types import SimpleNamespace

from scripts.wp15_workbench import embedding_environment


def test_configured_model_is_passed_and_unset_fields_are_left_out():
    settings = SimpleNamespace(
        embedding_provider="local_bge_m3", embedding_path=Path("models/e5"),
        embedding_model_path=Path("models/bge-m3"), embedding_model="BAAI/bge-m3",
        embedding_revision=None, embedding_dimension=1024)
    assert embedding_environment(settings) == {
        "EMBEDDING_PROVIDER": "local_bge_m3", "EMBEDDING_PATH": str(Path("models/e5")),
        "EMBEDDING_MODEL_PATH": str(Path("models/bge-m3")), "EMBEDDING_MODEL": "BAAI/bge-m3",
        "EMBEDDING_DIMENSION": "1024"}


def test_default_settings_keep_the_default_model():
    settings = SimpleNamespace(embedding_provider="local_e5", embedding_path=Path("models/e5"))
    assert embedding_environment(settings) == {"EMBEDDING_PROVIDER": "local_e5",
                                               "EMBEDDING_PATH": str(Path("models/e5"))}
