"""Streaming multipart: enforce quotas before writing each received file fragment."""

import hashlib
import json
import logging
import os
from pathlib import PurePosixPath

from pydantic import ValidationError
from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header
from starlette.concurrency import run_in_threadpool

from app.domain.documents import DocumentInput
from app.domain.policies import DomainError


class Upload:
    def __init__(self, storage, maximum):
        self.storage, self.maximum = storage, maximum
        self.key, self.file, self.size = None, None, 0
        self.digest = hashlib.sha256()
        self.parts, self.finished, self.metadata = set(), False, bytearray()
        self.name, self.filename = None, None
        self.header_size, self.field, self.value, self.headers = 0, bytearray(), bytearray(), {}

    def fail(self, code="INVALID_UPLOAD", status=422):
        raise DomainError(code, "Upload rejected", status)

    def on_part_begin(self):
        if len(self.parts) >= 2:
            self.fail()
        self.headers, self.field, self.value, self.header_size = {}, bytearray(), bytearray(), 0

    def on_header_field(self, data, start, end):
        self.header_size += end - start
        if self.header_size > 8192:
            self.fail("UPLOAD_TOO_LARGE", 413)
        self.field.extend(data[start:end])

    def on_header_value(self, data, start, end):
        self.header_size += end - start
        if self.header_size > 8192:
            self.fail("UPLOAD_TOO_LARGE", 413)
        self.value.extend(data[start:end])

    def on_header_end(self):
        field = bytes(self.field).lower()
        if field in self.headers:
            self.fail()
        self.headers[field] = bytes(self.value)
        self.field, self.value = bytearray(), bytearray()

    def on_headers_finished(self):
        kind, options = parse_options_header(self.headers.get(b"content-disposition", b""))
        self.name = options.get(b"name")
        if (
            kind != b"form-data"
            or self.name not in {b"file", b"metadata"}
            or self.name in self.parts
        ):
            self.fail()
        self.parts.add(self.name)
        filename = options.get(b"filename")
        if self.name == b"file":
            try:
                self.filename = filename.decode("utf-8")
            except (AttributeError, UnicodeError):
                self.fail()
            if (
                len(self.filename) > 255
                or any(ord(c) < 32 for c in self.filename)
                or any(c in self.filename for c in "/\\:")
            ):
                self.fail()
            self.suffix = PurePosixPath(self.filename).suffix.lower()
            if self.suffix not in {".md", ".markdown", ".pdf"}:
                self.fail("UNSUPPORTED_FORMAT", 415)
            self.key, self.file = self.storage.create()
        elif filename is not None:
            self.fail()

    def on_part_data(self, data, start, end):
        part = data[start:end]
        if self.name == b"file":
            self.size += len(part)
            if self.size > self.maximum:
                self.fail("UPLOAD_TOO_LARGE", 413)
            self.file.write(part)
            self.digest.update(part)
        else:
            if len(self.metadata) + len(part) > 16384:
                self.fail("UPLOAD_TOO_LARGE", 413)
            self.metadata.extend(part)

    def on_end(self):
        self.finished = True

    async def receive(self, request):
        kind, options = parse_options_header(request.headers.get("content-type", ""))
        boundary = options.get(b"boundary", b"")
        if kind != b"multipart/form-data" or not 1 <= len(boundary) <= 200:
            self.fail("UNSUPPORTED_FORMAT", 415)
        callbacks = {
            name: getattr(self, name)
            for name in [
                "on_part_begin",
                "on_header_field",
                "on_header_value",
                "on_header_end",
                "on_headers_finished",
                "on_part_data",
                "on_end",
            ]
        }
        parser = MultipartParser(boundary, callbacks)
        received = 0
        try:
            async for data in request.stream():
                received += len(data)
                if received > self.maximum + 65536:
                    self.fail("UPLOAD_TOO_LARGE", 413)
                await run_in_threadpool(parser.write, data)
            parser.finalize()
            if not self.finished or self.parts != {b"file", b"metadata"} or not self.size:
                self.fail()
            metadata = DocumentInput.model_validate(json.loads(self.metadata))
            self.file.flush()
            os.fsync(self.file.fileno())
            self.file.close()
            self.file = None
            return metadata
        except (MultipartParseError, ValueError, ValidationError, UnicodeError):
            self.fail()
        finally:
            if self.file:
                self.file.close()
                self.file = None


# Uploaded content is untrusted; expose only our structured, sanitized errors.
_library_log = logging.getLogger("python_multipart.multipart")
_library_log.addHandler(logging.NullHandler())
_library_log.propagate = False
