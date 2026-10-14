"""Opt-in, isolated, server-configured DKVB retrieval slice. No diagnostic rules."""
import hashlib
import json
import os
import re
from pathlib import Path
from uuid import UUID

from fastapi import Depends, Header
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from sqlalchemy import select
from app.api.dependencies import authenticated, writing
from app.domain.schemas import InputModel, CreateCase
from app.domain.retrieval import SearchInput
from app.domain.policies import DomainError
from app.infrastructure.orm import chunks
from app.legacy_preview.product import create_preview
from app.legacy_case_creation import LegacyCaseService
from app.services.evidence_scope import source, owned_case

MANUALS = ("维修知识手册.md", "规格与判断关系.md")
PDFS = {"S01": ("originals/S01-identification.pdf", 1), "S02": ("originals/S02-charge-air.pdf", 6), "S03": ("originals/S03-turbocharger.pdf", 9)}
VEHICLE = dict(model="探岳", engine_code="DKVB")


def safe_file(root, relative):
    root = Path(root).absolute()
    p = root / relative
    if p.is_absolute() and not p.resolve().is_relative_to(root.resolve()):
        raise ValueError("Path outside topic package")
    for item in (p, *p.parents):
        if item.is_symlink() or (item.exists() and getattr(item.stat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("Reparse paths are not supported")
    if not p.is_file():
        raise ValueError("Topic file missing")
    return p


def verify_package(root):
    manifest = json.loads(safe_file(root, "manifest.json").read_text(encoding="utf8"))
    if manifest["package_id"] != "DKVB-P0299-DEMO-v1":
        raise ValueError("Unexpected package")
    for f in manifest["files"]:
        p = safe_file(root, f["path"])
        if p.stat().st_size != f["bytes"] or hashlib.sha256(p.read_bytes()).hexdigest() != f["sha256"]:
            raise ValueError("Package hash mismatch: " + f["path"])
    return manifest


def references(raw, chunk):
    # Bound context by consecutive level-2 through level-6 headings;
    # the preamble ends at the first such heading. Never follow links on disk.
    pos = chunk["locator_json"].get("char_start", 0)
    pos += len(raw[pos:]) - len(raw[pos:].lstrip())
    headings = list(re.finditer(r"(?m)^#{2,6} .+$", raw))
    start, end = 0, headings[0].start() if headings else len(raw)
    for i, m in enumerate(headings):
        if m.start() <= pos:
            start = m.start(); end = headings[i+1].start() if i+1 < len(headings) else len(raw)
    section = raw[start:end]
    def page_refs(text):
        out=set()
        for match in re.finditer(r"(?<![A-Za-z0-9])(S0[123])-P(\d+)((?:/P?\d+)*)", text):
            out.add((match[1], match[2]))
            for n in re.findall(r"/P?(\d+)", match[3]): out.add((match[1], n))
        return sorted(out)
    direct = page_refs(chunk["text"])
    context = page_refs(section)
    pages = [dict(source_id=s, page=int(p), relation="chunk" if (s,p) in direct else "section_reference") for s,p in (direct or context) if 1 <= int(p) <= PDFS[s][1]]
    ds = sorted(set(re.findall(r"(?<![A-Za-z0-9])DS-0[123](?![0-9])", section)))
    return dict(pages=pages, simulation_specs=ds, mapping_scope="direct_chunk" if direct else "containing_section", section_context=section,
                note="整理段落引用，不等于该页支持整段所有说法。DS为模拟阈值，PDF不证明模拟数值。")


class TopicQuery(InputModel):
    case_id: UUID
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10, strict=True)


def create_topic():
    registry_path = Path(os.environ["DKVB_REGISTRY"])
    app = create_preview(static_dir=Path(os.environ["DKVB_DIST"]) / "not-mounted")
    engine = app.state.case_service.engine

    def registry(actor):
        if not registry_path.exists():
            raise DomainError("TOPIC_NOT_READY", "专题导入尚未完成", 503)
        d = json.loads(registry_path.read_text(encoding="utf8"))
        if d["actor"] != str(actor):
            raise DomainError("NOT_FOUND", "Topic not found", 404)
        if not d.get("ready"):
            raise DomainError("TOPIC_NOT_READY", "专题导入尚未完成", 503)
        return d

    def scoped(actor, cid):
        d = registry(actor)
        case = app.state.case_service.get(actor, cid)
        expected = {v["version_id"] for k,v in d["documents"].items() if k in MANUALS}
        if {x["document_version_id"] for x in case["corpus_manifest"]} != expected or case["vehicle"]["engine_code"] != "DKVB":
            raise DomainError("TOPIC_SCOPE_INVALID", "会话不属于当前专题冻结范围", 409)
        return d, case

    @app.get("/api/v2/topic")
    def topic(principal=Depends(authenticated)):
        d = registry(principal.actor_id)
        state=[]
        for name, v in d["documents"].items():
            data=app.state.document_service.get(principal.actor_id, UUID(v["document_id"]), UUID(v["version_id"]))
            state.append(dict(name=name, **data))
        return dict(id="dkvb-p0299", title="虚拟探岳 DKVB / P0299", synthetic=True, formal_usable=False, documents=state)

    @app.post("/api/v2/topic/cases")
    def new_case(principal=Depends(writing), idempotency_key: str=Header()):
        registry(principal.actor_id)
        legacy = LegacyCaseService(engine, app.state.case_service.cursor_secret,
                                   profile=app.state.case_service.profile)
        status, body=legacy.create(principal.actor_id, CreateCase(vehicle=VEHICLE, fault_description="虚拟DKVB/P0299资料检索体验；不启动诊断", fault_codes=["P0299"]), idempotency_key)
        scoped(principal.actor_id, UUID(body["id"]))
        return JSONResponse(status_code=status, content=body)

    @app.post("/api/v2/topic/search")
    def search(body: TopicQuery, principal=Depends(writing)):
        _, case=scoped(principal.actor_id, body.case_id)
        result = app.state.retrieval_service.search(principal.actor_id, SearchInput(query=body.query, vehicle_scope=VEHICLE, top_k=body.top_k), manifest=case["corpus_manifest"])
        for hit in result["chunks"]:
            located = chunk_source(body.case_id, UUID(hit["chunk_id"]), principal)
            hit["simulation_specs"] = located["simulation_specs"]
        return result

    @app.get("/api/v2/topic/cases/{cid}/chunks/{chunk_id}")
    def chunk_source(cid: UUID, chunk_id: UUID, principal=Depends(authenticated)):
        d, case=scoped(principal.actor_id, cid)
        with engine.connect() as c:
            row=c.execute(select(chunks).where(chunks.c.id==chunk_id)).mappings().one_or_none()
            if row is None: raise DomainError("NOT_FOUND", "Chunk not found", 404)
            entry=next((x for x in case["corpus_manifest"] if x["document_version_id"]==str(row["document_version_id"])), None)
            if entry is None: raise DomainError("NOT_FOUND", "Chunk outside case", 404)
            source(c, principal.actor_id, owned_case(c, principal.actor_id, cid), row["document_version_id"], UUID(entry["index_id"]), "synthetic")
            name, v=next((k,v) for k,v in d["documents"].items() if v["version_id"]==str(row["document_version_id"]))
            raw, _, _=app.state.document_service.content(principal.actor_id, UUID(v["document_id"]), UUID(v["version_id"]), None)
            raw=raw.decode("utf-8-sig")
            if hashlib.sha256(row["text"].encode()).hexdigest()!=row["text_hash"]: raise DomainError("SOURCE_INVALID", "Chunk hash mismatch")
            links=references(raw, row)
            for page in links["pages"]:
                pdf=d["documents"][PDFS[page["source_id"]][0]]
                page.update(document_id=pdf["document_id"], version_id=pdf["version_id"], sha256=pdf["sha256"])
            return dict(manual=name, document_id=v["document_id"], version_id=v["version_id"], sha256=v["sha256"], chunk_id=str(chunk_id), chunk_hash=row["text_hash"], text=row["text"], raw=raw, locator=row["locator_json"], synthetic=True, formal_usable=False, simulation_source=f"/api/v2/documents/{d['documents'][MANUALS[1]]['document_id']}/versions/{d['documents'][MANUALS[1]]['version_id']}/content", **links)

    def asset(sid, page, actor, image=False):
        d=registry(actor)
        if sid not in PDFS or page<1 or page>PDFS[sid][1]: raise DomainError("NOT_FOUND", "Source page not found", 404)
        v=d["documents"][PDFS[sid][0]]
        data, _, _=app.state.document_service.content(actor, UUID(v["document_id"]), UUID(v["version_id"]), None)
        if hashlib.sha256(data).hexdigest()!=v["sha256"]: raise DomainError("SOURCE_INVALID", "PDF hash mismatch")
        mime="application/pdf"
        if image:
            name=f"figures/{sid}-{page}.png"; p=safe_file(d["assets"],name); data=p.read_bytes()
            if hashlib.sha256(data).hexdigest()!=d["figures"][name]: raise DomainError("SOURCE_INVALID", "Image hash mismatch")
            mime="image/png"
        return Response(data,media_type=mime,headers={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","X-Source-SHA256":v["sha256"],"X-Physical-Page":str(page)})

    @app.get("/api/v2/topic/sources/{sid}/{page}")
    def pdf(sid: str,page:int,principal=Depends(authenticated)):return asset(sid,page,principal.actor_id)

    @app.get("/api/v2/topic/sources/{sid}/{page}/image")
    def image(sid:str,page:int,principal=Depends(authenticated)):return asset(sid,page,principal.actor_id,True)

    app.mount("/",StaticFiles(directory=os.environ["DKVB_DIST"],html=True),name="dkvb-ui")
    return app
