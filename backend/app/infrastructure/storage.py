"""Local immutable UUID files. No user filename is a filesystem path."""

import hashlib
import os
import re
import stat
from pathlib import Path
from uuid import uuid4

from app.domain.policies import DomainError


def plain_path(path):
    path = Path(os.path.abspath(path))
    legacy = Path(r"E:\Work\v4-double")
    if path == legacy or legacy in path.parents:
        raise DomainError("STORAGE_UNAVAILABLE", "Unsafe storage root", 500)
    for item in [*reversed(path.parents), path]:
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise DomainError("STORAGE_UNAVAILABLE", "Reparse paths are not supported", 500)
    return path


class Storage:
    def __init__(self, root):
        self.root = Path(os.path.abspath(root)) / "documents"

    def path(self, key):
        if not re.fullmatch(r"[0-9a-f]{32}\.bin", key):
            raise DomainError("STORAGE_UNAVAILABLE", "Invalid storage key", 500)
        plain_path(self.root)
        return plain_path(self.root / key)

    def create(self):
        plain_path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        key = uuid4().hex + ".bin"
        path = self.path(key)
        fd = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600
        )
        return key, os.fdopen(fd, "wb")

    def read(self, key, digest):
        try:
            data = self.path(key).read_bytes()
        except OSError:
            raise DomainError("SOURCE_UNAVAILABLE", "Source file unavailable", 500) from None
        if hashlib.sha256(data).hexdigest() != digest:
            raise DomainError("SOURCE_UNAVAILABLE", "Source integrity check failed", 500)
        return data

    def discard(self, key):
        self.path(key).unlink(missing_ok=True)
