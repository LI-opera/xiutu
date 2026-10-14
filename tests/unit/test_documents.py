import asyncio
import hashlib
import sys
import threading
from pathlib import Path

import pytest
from app.domain.documents import DocumentInput, IngestError
from app.domain.policies import DomainError
from app.infrastructure.storage import Storage
from app.infrastructure.upload import Upload
from app.retrieval.chunker import chunks
from app.retrieval.parsers import markdown, pdf
from app.retrieval.tokenization import count
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wp04_fixtures import MARKDOWN, metadata, pdf_bytes


def test_markdown_coverage_bpe_and_tables():
    parsed = markdown.parse(MARKDOWN.encode(), threading.Event())
    result = chunks(parsed, threading.Event())
    coverage = set()
    for item in result["chunks"]:
        assert item["token_count"] == count(item["text"]) <= 900
        assert item["text_hash"] == hashlib.sha256(item["text"].encode()).hexdigest()
        coverage.update(range(item["char_start"], item["char_end"]))
    assert coverage == set(range(len(MARKDOWN)))
    tables = [c for c in result["chunks"] if c["kind"] == "table"]
    assert len(tables) > 1
    assert all("| 项目 | 合成值 |" in c["text"] for c in tables)
    assert any(c["locator_json"].get("context") for c in tables)
    assert any("<script>" in c["text"] for c in result["chunks"])
    assert count("hello world") == 2
    print("complete character coverage, real BPE max=900, table headers/context retained")


@pytest.mark.parametrize(
    "kinds,issues", [(("text", "text"), []), (("scan",), [1]), (("text", "scan", "text"), [2])]
)
def test_pdf_pages_and_missing(kinds, issues):
    parsed = pdf.parse(pdf_bytes(kinds), threading.Event())
    assert [x["page"] for x in parsed["page_issues"]] == issues
    assert parsed["page_count"] == len(kinds)
    result = chunks(parsed, threading.Event())
    assert [x["page_start"] for x in result["chunks"]] == [
        i for i, k in enumerate(kinds, 1) if k == "text"
    ]


@pytest.mark.parametrize(
    "value", [b"not pdf", b"%PDF-1.7\nbroken\n%%EOF", pdf_bytes(encrypted=True)]
)
def test_invalid_encrypted_pdf(value):
    with pytest.raises(IngestError):
        pdf.reader(value)


@pytest.mark.parametrize("field", ["title", "source_reference", "source_kind"])
def test_metadata_nul(field):
    value = metadata()
    value[field] = "unsafe\x00input"
    with pytest.raises(ValidationError):
        DocumentInput.model_validate(value)


def test_storage_paths_and_immutable(tmp_path):
    store = Storage(tmp_path)
    with pytest.raises(DomainError):
        store.path("../outside")
    key, f = store.create()
    f.write(b"synthetic")
    f.close()
    assert store.read(key, hashlib.sha256(b"synthetic").hexdigest()) == b"synthetic"
    with pytest.raises(DomainError):
        store.read(key, "0" * 64)
    # Real junction test uses Windows native mklink in isolated tmp directories.
    import os
    import subprocess

    if os.name == "nt":
        outside = tmp_path / "outside"
        outside.mkdir()
        link = tmp_path / "junction"
        p = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True
        )
        assert p.returncode == 0
        try:
            with pytest.raises(DomainError):
                Storage(link).create()
            assert list(outside.iterdir()) == []
        finally:
            link.rmdir()  # removes only this empty directory junction


def test_streaming_limit_before_complete_receive(tmp_path):
    store = Storage(tmp_path)
    upload = Upload(store, 1024)
    delivered = []

    class Request:
        headers = {"content-type": "multipart/form-data; boundary=abc"}

        async def stream(self):
            yield b'--abc\r\nContent-Disposition: form-data; name="file"; filename="s.md"\r\n\r\n'
            for i in range(20):
                delivered.append(i)
                yield b"a" * 512

    with pytest.raises(DomainError) as exc:
        asyncio.run(upload.receive(Request()))
    assert exc.value.status == 413
    assert len(delivered) == 3
    assert store.path(upload.key).stat().st_size <= 1024
    store.discard(upload.key)
