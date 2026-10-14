"""Download pinned public model artifacts, never upload inputs or overwrite unknown files."""

import hashlib
import json
import os
import urllib.request
from pathlib import Path
from uuid import uuid4

from app.infrastructure.embedding_gateway import FILES, MODEL, REVISION


def plain(path):
    for item in [*reversed(path.parents), path]:
        if item.exists() or item.is_symlink():
            info = item.stat(follow_symlinks=False)
            if item.is_symlink() or getattr(info, "st_file_attributes", 0) & 1024:
                raise RuntimeError("Refuse model cache reparse path")


def main():
    root = Path(os.path.abspath(__file__)).parents[1]
    folder = root / ".local-data" / "models" / "multilingual-e5-small" / REVISION
    plain(folder)
    folder.mkdir(parents=True, exist_ok=True)
    plain(folder)
    records = {}
    sources = {"model.onnx": "onnx/model.onnx", "tokenizer.json": "onnx/tokenizer.json"}
    expected = dict(
        FILES, **{"README.md": "0038de97aee16258cecbad7ffda4b4febd6953e747a00e0ddbc8e6ed241e9c1c"}
    )
    sources["README.md"] = "README.md"
    for name, digest in expected.items():
        target = folder / name
        plain(target)
        if target.exists():
            with target.open("rb") as f:
                if hashlib.file_digest(f, "sha256").hexdigest() != digest:
                    raise RuntimeError("Existing model artifact hash mismatch; refusing overwrite")
            records[name] = "verified_existing"
            continue
        temporary = folder / ("download-" + uuid4().hex + ".part")
        try:
            with (
                urllib.request.urlopen(
                    f"https://huggingface.co/{MODEL}/resolve/{REVISION}/{sources[name]}", timeout=90
                ) as response,
                temporary.open("xb") as out,
            ):
                while data := response.read(1024 * 1024):
                    out.write(data)
                out.flush()
                os.fsync(out.fileno())
            with temporary.open("rb") as f:
                if hashlib.file_digest(f, "sha256").hexdigest() != digest:
                    raise RuntimeError("Downloaded model artifact hash mismatch")
            # Windows rename refuses an existing destination; no replacement API.
            if target.exists():
                raise RuntimeError("Model destination appeared during download")
            temporary.rename(target)
            records[name] = "downloaded_and_verified"
        finally:
            if temporary.exists():
                temporary.unlink()  # Only this invocation's unique partial artifact.
    print(json.dumps(dict(model=MODEL, revision=REVISION, directory=str(folder), files=records)))


if __name__ == "__main__":
    main()
