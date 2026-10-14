"""Pinned local ONNX inference only. No network or remote-code loader."""

import hashlib
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np

MODEL = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
CONFIG_VERSION = "e5-small-onnx-v1"
DIMENSION = 384
FILES = {
    "model.onnx": "ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665",
    "tokenizer.json": "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39",
}
CONFIG = dict(
    provider="onnxruntime-cpu",
    model=MODEL,
    revision=REVISION,
    dimension=DIMENSION,
    config_version=CONFIG_VERSION,
    pooling="attention-mean",
    normalization="L2",
    window_tokens=480,
    window_overlap=0,
    aggregation="content-token-weighted-mean-L2",
    document_prefix="passage: ",
    query_prefix="query: ",
    files=FILES,
)


class EmbeddingError(Exception):
    def __init__(self, code="EMBEDDING_UNAVAILABLE"):
        self.code = code
        super().__init__(code)


def validate_vectors(values, count, dimension=DIMENSION):
    try:
        a = np.asarray(values, dtype=np.float32)
        if a.shape != (count, dimension) or not np.isfinite(a).all():
            raise ValueError()
        norms = np.linalg.norm(a, axis=1)
        if (norms < 1e-8).any() or not np.isfinite(norms).all():
            raise ValueError()
        return (a / norms[:, None]).tolist()
    except (ValueError, TypeError, OverflowError):
        raise EmbeddingError("INVALID_EMBEDDING") from None


class EmbeddingGateway:
    config = CONFIG

    def __init__(self, directory):
        self.directory = Path(directory)
        self._session = None
        self._mutex = threading.Lock()

    def _load(self):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        for name, expected in FILES.items():
            with (self.directory / name).open("rb") as f:
                digest = hashlib.file_digest(f, "sha256").hexdigest()
            if digest != expected:
                raise EmbeddingError("MODEL_HASH_MISMATCH")
        tokenizer = Tokenizer.from_file(str(self.directory / "tokenizer.json"))
        tokenizer.no_truncation()
        tokenizer.no_padding()
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        options.log_severity_level = 4
        session = ort.InferenceSession(
            str(self.directory / "model.onnx"), options, providers=["CPUExecutionProvider"]
        )
        self._tokenizer, self._session = tokenizer, session

    def _embed(self, texts, prefix):
        if not texts or any(not isinstance(t, str) or not t.strip() for t in texts):
            raise EmbeddingError("INVALID_EMBEDDING_INPUT")
        try:
            with self._mutex:
                if self._session is None:
                    self._load()
                result = []
                for value in texts:
                    ids = self._tokenizer.encode(value, add_special_tokens=False).ids
                    prefix_ids = self._tokenizer.encode(prefix, add_special_tokens=False).ids
                    vectors, weights = [], []
                    for start in range(0, len(ids), 480):
                        part = ids[start : start + 480]
                        tokens = [0] + prefix_ids + part + [2]
                        inp = np.asarray([tokens], dtype=np.int64)
                        mask = np.ones_like(inp)
                        feed = {"input_ids": inp, "attention_mask": mask}
                        for node in self._session.get_inputs():
                            if node.name == "token_type_ids":
                                feed[node.name] = np.zeros_like(inp)
                        hidden = self._session.run(None, feed)[0]
                        pooled = hidden.mean(axis=1) if hidden.ndim == 3 else hidden
                        vectors.append(validate_vectors(pooled, 1)[0])
                        weights.append(len(part))
                    result.append(np.average(vectors, axis=0, weights=weights))
                return validate_vectors(result, len(texts))
        except EmbeddingError:
            raise
        except Exception:
            raise EmbeddingError() from None

    def embed_documents(self, texts):
        return self._embed(texts, "passage: ")

    def embed_query(self, text):
        return self._embed([text], "query: ")[0]


@lru_cache(maxsize=2)
def gateway(directory):
    return EmbeddingGateway(directory)
