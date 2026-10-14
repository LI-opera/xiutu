"""Operator-installed skills only; uploaded manuals cannot become executable skills."""

import hashlib
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.tools.schemas import INPUTS

ROOT = Path(__file__).resolve().parents[3] / "skills"


class SkillError(Exception):
    pass


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    version: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    allowed_tools: list[str]
    applicable_systems: list[str]
    required_context: list[str]
    output_schema: str
    status: Literal["approved"]
    references: dict[str, str] = Field(default_factory=dict)


class SkillRegistry:
    def __init__(self, root=ROOT):
        self.root = Path(root).absolute()
        # Root is trusted operator configuration, never accepted from HTTP/model or upload payload.
        self.path(".")

    def path(self, relative):
        p = self.root / relative
        if p.is_absolute() and not p.is_relative_to(self.root):
            raise SkillError("SKILL_PATH_DENIED")
        if ".." in p.parts:
            raise SkillError("SKILL_PATH_DENIED")
        for x in [p, *p.parents]:
            if x.is_symlink() or x.is_junction():
                raise SkillError("SKILL_REPARSE_DENIED")
        if not p.resolve().is_relative_to(self.root.resolve()):
            raise SkillError("SKILL_PATH_DENIED")
        return p

    def metadata(self, name):
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", name):
            raise SkillError("SKILL_NAME_INVALID")
        try:
            m = Manifest.model_validate_json(
                self.path(name + "/manifest.json").read_text(encoding="utf8")
            )
        except Exception:
            raise SkillError("SKILL_MANIFEST_INVALID") from None
        if m.name != name or not set(m.allowed_tools) <= set(INPUTS):
            raise SkillError("SKILL_ALLOWLIST_INVALID")
        return m.model_dump()

    def list_metadata(self):
        return [self.metadata(p.name) for p in sorted(self.root.iterdir()) if p.is_dir()]

    def select(self, system, context):
        return [
            m
            for m in self.list_metadata()
            if system in m["applicable_systems"]
            and all(k in context and context[k] is not None for k in m["required_context"])
        ]

    def verify_hash(self, path, expected):
        raw = self.path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise SkillError("SKILL_HASH_MISMATCH")
        return raw

    def load_body(self, name, version):
        m = self.metadata(name)
        if m["version"] != version:
            raise SkillError("SKILL_VERSION_MISMATCH")
        text = self.verify_hash(name + "/SKILL.md", m["sha256"]).decode("utf8")
        parts = text.split("---", 2)
        if len(parts) != 3 or parts[0].strip():
            raise SkillError("SKILL_HEADER_INVALID")
        fields = {}
        for line in parts[1].strip().splitlines():
            k, sep, v = line.partition(":")
            if not sep or k.strip() in fields:
                raise SkillError("SKILL_HEADER_INVALID")
            fields[k.strip()] = v.strip()
        if set(fields) != {"name", "description"} or fields["name"] != name:
            raise SkillError("SKILL_HEADER_INVALID")
        return dict(metadata=m, body=parts[2].strip(), evidence=[])

    def load_references(self, name, allowlist):
        m = self.metadata(name)
        out = {}
        for rel in allowlist:
            if rel not in m["references"]:
                raise SkillError("SKILL_REFERENCE_DENIED")
            out[rel] = self.verify_hash(name + "/" + rel, m["references"][rel]).decode("utf8")
        return out
