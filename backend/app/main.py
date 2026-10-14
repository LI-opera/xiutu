import hashlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.cases import router as cases_router
from app.api.area_rankings import router as area_rankings_router
from app.api.area_analyses import router as area_analyses_router
from app.api.template_repairs import router as template_repairs_router
from app.api.case_analyses import router as case_analyses_router
from app.api.client_config import router as client_config_router
from app.api.dependencies import AuthStore
from app.api.documents import router as documents_router
from app.api.errors import register_errors
from app.api.evidence import router as evidence_router
from app.api.measurements import router as measurements_router
from app.api.openapi import configure_openapi
from app.api.reports import router as reports_router
from app.api.runs import router as runs_router
from app.config import Settings, load_settings
from app.domain.schemas import ErrorEnvelope
from app.infrastructure.db import Database
from app.infrastructure.uow import make_engine
from app.retrieval.service import RetrievalService
from app.services.area_service import AreaService
from app.services.area_ranking_service import AreaRankingService
from app.services.area_analysis_service import AreaAnalysisService
from app.services.template_repair_service import TemplateRepairService
from app.services.case_service import CaseService
from app.services.case_analysis_read_service import CaseAnalysisReadService
from app.services.correction_service import CorrectionService
from app.services.diagnosis_read_service import DiagnosisReadService
from app.services.document_service import DocumentService
from app.services.evidence_service import EvidenceService
from app.services.index_service import IndexService
from app.services.observation_service import ObservationService
from app.services.report_read_service import ReportReadService
from app.services.run_service import RunService
from app.services.workbench_view_service import WorkbenchViewService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings(
        project_env=__import__("os").environ.get("XIUTU_LOAD_PROJECT_ENV") == "1"
    )
    db = Database(settings.database_url.get_secret_value() if settings.database_url else None)

    engine = make_engine(
        settings.database_url.get_secret_value() if settings.database_url else None
    )

    @asynccontextmanager
    async def lifespan(app):
        db.open()
        try:
            yield
        finally:
            db.close()
            if engine is not None:
                engine.dispose()

    app = FastAPI(title="Xiutu environment", lifespan=lifespan)

    app.state.settings = settings
    app.state.auth = AuthStore(settings)
    secret = (
        settings.operator_token.get_secret_value()
        if settings.operator_token
        else "unconfigured-no-auth"
    )
    app.state.case_service = CaseService(
        engine, hashlib.sha256(("cursor:" + secret).encode()).digest(),
        settings.retrieval_profile, settings
    )
    app.state.area_ranking_service = AreaRankingService(app.state.case_service, settings)
    app.state.area_analysis_service = AreaAnalysisService(app.state.case_service, settings)
    app.state.template_repair_service = TemplateRepairService(engine)
    app.state.run_service = RunService(engine)
    app.state.diagnosis_read_service = DiagnosisReadService(engine, settings)
    app.state.observation_service = ObservationService(engine, settings)
    app.state.correction_service = CorrectionService(engine, settings)
    app.state.area_service = AreaService(engine, settings)
    app.state.workbench_view_service = WorkbenchViewService(engine)
    app.state.document_service = DocumentService(
        engine, settings, hashlib.sha256(secret.encode()).digest()
    )
    app.state.evidence_service = EvidenceService(engine, settings)
    app.state.index_service = IndexService(engine, settings)
    app.state.retrieval_service = RetrievalService(engine, settings)
    app.state.report_read_service = ReportReadService(engine, settings)
    app.state.case_analysis_read_service = CaseAnalysisReadService(app.state.case_service, settings)
    register_errors(app)
    errors = {
        code: {"model": ErrorEnvelope}
        for code in [400, 401, 403, 404, 409, 413, 415, 422, 500, 502, 503]
    }
    app.include_router(auth_router, responses=errors)
    app.include_router(cases_router, responses=errors)
    app.include_router(area_rankings_router, responses=errors)
    app.include_router(area_analyses_router, responses=errors)
    app.include_router(template_repairs_router, responses=errors)
    app.include_router(case_analyses_router, responses=errors)
    app.include_router(client_config_router, responses=errors)
    app.include_router(reports_router, responses=errors)
    app.include_router(runs_router, responses=errors)
    app.include_router(documents_router, responses=errors)
    app.include_router(evidence_router, responses=errors)
    app.include_router(measurements_router, responses=errors)

    @app.get("/api/v2/health/live")
    def live():
        return {"status": "live"}

    @app.get("/api/v2/health/ready")
    def ready():
        ok = db.ready()
        return JSONResponse(
            status_code=200 if ok else 503,
            content={
                "status": "ready" if ok else "not_ready",
                "database_ready": ok,
                "model_configured": bool(settings.deepseek_api_key),
                "model_verified": False,
            },
        )

    @app.middleware("http")
    async def no_private_cache(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(
            (
                "/api/v2/cases",
                "/api/v2/client-config",
                "/api/v2/auth",
                "/api/v2/runs",
                "/api/v2/documents",
                "/api/v2/evidence",
                "/api/v2/measurement",
                "/api/v2/prototype",
            )
        ):
            response.headers["Cache-Control"] = "no-store"
        return response

    configure_openapi(app)
    return app


app = create_app()
