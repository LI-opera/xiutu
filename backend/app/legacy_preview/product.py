"""Opt-in isolated product slice. The production application entry stays unchanged."""
import os
import hashlib
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import Depends, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.infrastructure.orm import chunks, document_versions, documents
from app.domain.policies import DomainError

from app.agents.state import ProposalContext, ProposalEnvelope
from app.api.dependencies import authenticated, writing
from app.config import Settings
from app.infrastructure.db_target import validate_target
from app.main import create_app
from app.services.proposal_service import ProposalService
from app.services.document_service import DocumentService

ROOT = Path(__file__).resolve().parents[3]
VEHICLE = dict(model="HT-2.0", year=2021, engine_family="SYNTH-F", engine_code="SYNTH-C")
SCOPE = dict(model="HT-2.0", year_from=2021, year_to=2021, engine_family="SYNTH-F", engine_code="SYNTH-C")

class PreviewIssue(BaseModel):
    code: str
    path: str
    detail: str

class PreviewResult(BaseModel):
    accepted: bool
    disposition: str
    issues: list[PreviewIssue]
    provenance: list[dict] = Field(default_factory=list)
    support: list[dict] = Field(default_factory=list)
    candidate: dict | None = None
    conclusion_support: dict | None = None
    published: Literal[False] = False
    diagnosis: Literal[False] = False


class PreviewSourceMapping(BaseModel):
    model_config = {"extra": "forbid"}
    document_id: UUID
    document_version_id: UUID
    chunk_id: UUID
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locator: dict


class PreviewDocumentService(DocumentService):
    def review(self, actor, identifier, vid, data, key):
        # get verifies owner/version; metadata is immutable, so no approval race can change nature.
        version = self.get(actor, identifier, vid)
        if version["metadata"].get("synthetic") is not True:
            raise DomainError("PREVIEW_REVIEW_SYNTHETIC_ONLY", "Nonfiction material requires separate verification; preview review is synthetic only", 403)
        return super().review(actor, identifier, vid, data, key)


def create_preview(settings: Settings | None = None, *, static_dir: Path | None = None):
    settings = settings or Settings(_env_file=None)
    if settings.app_mode != "test" or settings.retrieval_profile != "synthetic" or not settings.database_url:
        raise ValueError("Preview requires explicit isolated synthetic test settings")
    target = validate_target(settings.database_url.get_secret_value(), "test")
    if not target.database.startswith("xiutu_test_preview_"):
        raise ValueError("Preview database must have its dedicated prefix")
    if settings.deepseek_api_key is not None:
        raise ValueError("Paid model credentials are not allowed in preview")
    app = create_app(settings)
    app.title = "Xiutu synthetic product preview"
    secret = settings.operator_token.get_secret_value() if settings.operator_token else "unconfigured-no-auth"
    app.state.document_service = PreviewDocumentService(app.state.case_service.engine, settings, hashlib.sha256(secret.encode()).digest())
    service = ProposalService(app.state.case_service.engine, settings)  # No trusted rules installed.

    @app.get("/api/v2/preview/health")
    def preview_health():
        return {"preview": True, "instance": os.environ.get("PREVIEW_INSTANCE", "schema-only")}

    @app.get("/api/v2/preview/config")
    def config(principal=Depends(authenticated)):
        return dict(synthetic=True, vehicle=VEHICLE, scope=SCOPE, rules_installed=False,
                    upload_max_bytes=settings.upload_max_bytes,
                    note="Vehicle filter metadata is synthetic, not a vehicle certification")

    @app.get("/api/v2/preview/source")
    def example(principal=Depends(authenticated)):
        return FileResponse(ROOT / "tests/fixtures/wp10/cooling-synthetic.md",
                            media_type="text/plain; charset=utf-8", filename="cooling-synthetic.md")

    @app.get("/api/v2/preview/versions/{version_id}/chunks/{chunk_id}/source", response_model=PreviewSourceMapping)
    def chunk_source(version_id: UUID, chunk_id: UUID, principal=Depends(authenticated)):
        # Read-only relation lookup; UUIDs are not permission. Original content still
        # uses the existing owner/document/version protected endpoint.
        with service.engine.connect() as conn:
            row = conn.execute(select(documents.c.id.label("document_id"),
                document_versions.c.id.label("document_version_id"), document_versions.c.sha256,
                chunks.c.id.label("chunk_id"), chunks.c.locator_json.label("locator")).select_from(
                    documents.join(document_versions, document_versions.c.document_id == documents.c.id)
                    .join(chunks, chunks.c.document_version_id == document_versions.c.id)
                ).where(documents.c.owner_id == principal.actor_id,
                        document_versions.c.id == version_id, chunks.c.id == chunk_id)).mappings().first()
            if row is None:
                raise DomainError("NOT_FOUND", "Source relation not found", 404)
            return dict(row)

    @app.post("/api/v2/cases/{case_id}/proposal-preview", response_model=PreviewResult)
    def preview(case_id: UUID, body: ProposalEnvelope, request: Request, principal=Depends(writing)):
        snapshot = request.app.state.case_service.get(principal.actor_id, case_id)
        context = ProposalContext(principal.actor_id, case_id, snapshot["revision"])
        return service.validate(context, body.model_dump(mode="json"))

    @app.middleware("http")
    async def preview_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if not request.url.path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"
        return response

    base_openapi = app.openapi
    def preview_openapi():
        schema = base_openapi()
        for path in ("/api/v2/preview/config", "/api/v2/preview/source", "/api/v2/preview/versions/{version_id}/chunks/{chunk_id}/source"):
            schema["paths"][path]["get"]["security"] = [{"SessionCookie": []}]
        return schema
    app.openapi = preview_openapi

    dist = static_dir if static_dir is not None else ROOT / "frontend/dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="preview-ui")
    return app
