import hashlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.area_analyses import router as area_analyses_router
from app.api.area_rankings import router as area_rankings_router
from app.api.area_references import router as area_references_router
from app.api.auth import router as auth_router
from app.api.cases import router as cases_router
from app.api.dependencies import AuthStore
from app.api.errors import register_errors
from app.api.openapi import configure_openapi
from app.api.template_repairs import router as template_repairs_router
from app.config import Settings, load_settings
from app.domain.schemas import ErrorEnvelope
from app.infrastructure.db import Database
from app.infrastructure.uow import make_engine
from app.services.area_analysis_service import AreaAnalysisService
from app.services.area_ranking_service import AreaRankingService
from app.services.case_service import CaseService
from app.services.reference_ingest import ReferenceIngestService
from app.services.template_repair_service import TemplateRepairService
from app.services.workbench_observation_service import TopicService


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
        engine, hashlib.sha256(("cursor:" + secret).encode()).digest()
    )
    app.state.area_ranking_service = AreaRankingService(app.state.case_service, settings)
    app.state.area_analysis_service = AreaAnalysisService(app.state.case_service, settings)
    app.state.reference_ingest_service = ReferenceIngestService(engine)
    app.state.template_repair_service = TemplateRepairService(
        engine, TopicService(app.state.case_service))
    register_errors(app)
    errors = {
        code: {"model": ErrorEnvelope}
        for code in [400, 401, 403, 404, 409, 413, 415, 422, 500, 502, 503]
    }
    app.include_router(auth_router, responses=errors)
    app.include_router(cases_router, responses=errors)
    app.include_router(area_rankings_router, responses=errors)
    app.include_router(area_analyses_router, responses=errors)
    app.include_router(area_references_router, responses=errors)
    app.include_router(template_repairs_router, responses=errors)

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
        if request.url.path.startswith(("/api/v2/cases", "/api/v2/auth", "/api/v2/area-references")):
            response.headers["Cache-Control"] = "no-store"
        return response

    configure_openapi(app)
    return app


app = create_app()
