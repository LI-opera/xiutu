"""Pinned offline BGE-M3 dense ONNX adapter; no shared-cache writes."""

import hashlib
import threading
from pathlib import Path

import numpy as np

from app.infrastructure.embedding_gateway import EmbeddingError, validate_vectors

FILES = {
    "model.onnx": "f84251230831afb359ab26d9fd37d5936d4d9bb5d1d5410e66442f630f24435b",
    "model.onnx_data": "1eebfb28493f67bba03ce0ef64bfdc7fc5a3bd9d7493f818bb1d78cd798416b4",
    "Constant_7_attr__value": "cdf16f72c5d07b36484056e601ed9687f78477e5d85cee85a34f2406b7fb5906",
    "tokenizer.json": "6710678b12670bc442b99edc952c4d996ae309a7020c1fa0096dd245c2faf790",
    "config.json": "f24afd5de914fba8c668426c43d208a1a54022500c63b2c160be20891686fce8",
}
CONFIG = dict(
    provider="local_bge_m3",
    model="BAAI/bge-m3",
    revision="5617a9f61b028005a4858fdac845db406aefb181",
    dimension=1024,
    config_version="bge-m3-onnx-v1",
    normalization="L2",
    pooling="CLS",
    preprocessing="bge-no-prefix-window480-v1",
    window_tokens=480,
    aggregation="content-token-weighted-mean-L2",
    files=FILES,
)


class BGEGateway:
    config = CONFIG

    def __init__(self, directory):
        self.directory = Path(directory)
        self._session = None
        self._mutex = threading.Lock()

    def _load(self):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        d = self.directory / "onnx" if (self.directory / "onnx").is_dir() else self.directory
        for n, digest in FILES.items():
            with (d / n).open("rb") as f:
                if hashlib.file_digest(f, "sha256").hexdigest() != digest:
                    raise EmbeddingError("MODEL_HASH_MISMATCH")
        self._tokenizer = Tokenizer.from_file(str(d / "tokenizer.json"))
        self._tokenizer.no_truncation()
        self._tokenizer.no_padding()
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        options.log_severity_level = 4
        self._session = ort.InferenceSession(
            str(d / "model.onnx"), options, providers=["CPUExecutionProvider"]
        )

    def embed_documents(self, texts):
        if not texts or any(not isinstance(t, str) or not t.strip() for t in texts):
            raise EmbeddingError("INVALID_EMBEDDING_INPUT")
        try:
            with self._mutex:
                if self._session is None:
                    self._load()
                result = []
                for text in texts:
                    ids = self._tokenizer.encode(text, add_special_tokens=False).ids
                    vs = []
                    weights = []
                    for start in range(0, len(ids), 480):
                        part = ids[start : start + 480]
                        inp = np.array([[0] + part + [2]], dtype=np.int64)
                        feed = {"input_ids": inp, "attention_mask": np.ones_like(inp)}
                        for node in self._session.get_inputs():
                            if node.name == "token_type_ids":
                                feed[node.name] = np.zeros_like(inp)
                        hidden = self._session.run(None, feed)[0]
                        pooled = hidden[:, 0, :] if hidden.ndim == 3 else hidden
                        vs.append(validate_vectors(pooled, 1, 1024)[0])
                        weights.append(len(part))
                    result.append(np.average(vs, axis=0, weights=weights))
                return validate_vectors(result, len(texts), 1024)
        except EmbeddingError:
            raise
        except Exception:
            raise EmbeddingError() from None

    def embed_query(self, text):
        return self.embed_documents([text])[0]
