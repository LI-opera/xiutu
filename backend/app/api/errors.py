from uuid import uuid4

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg import OperationalError as DriverOperationalError
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from starlette.exceptions import HTTPException

from app.domain.policies import DomainError


def error_response(error):
    body = dict(
        code=error.code, message=error.message, retryable=error.retryable, trace_id=str(uuid4())
    )
    if error.details is not None:
        body["details"] = error.details
    return JSONResponse(
        status_code=error.status, content={"error": body}, headers={"Cache-Control": "no-store"}
    )


def classify_database_error(error):
    """Classify structured driver state, never exception text or SQL parameters.

    Constraint/data failures have no established client-error mapping at this
    boundary. Business conflicts must be raised explicitly as DomainError.
    """
    state = getattr(getattr(error, "orig", None), "sqlstate", None)
    if isinstance(error, PoolTimeout):
        return DomainError("DATABASE_BUSY", "Database temporarily busy", 503, retryable=True)
    if isinstance(error, DBAPIError):
        # A failed connection does not establish that unchanged retries can help.
        # Known authentication/catalog failures take precedence over invalidation.
        if (state and state.startswith("28")) or state == "3D000":
            return DomainError("DATABASE_UNAVAILABLE", "Database unavailable", 503)
        if (
            state is None
            and error.statement is None
            and isinstance(error.orig, DriverOperationalError)
        ):
            return DomainError("DATABASE_UNAVAILABLE", "Database unavailable", 503)
        if (
            error.connection_invalidated
            or (state and state.startswith("08"))
            or state in {"57P01", "57P02", "57P03"}
        ):
            return DomainError("DATABASE_UNAVAILABLE", "Database unavailable", 503, retryable=True)
        if state in {"40001", "40P01", "55P03", "57014"}:
            return DomainError("DATABASE_BUSY", "Database temporarily busy", 503, retryable=True)
        if state and state.startswith("22"):
            return DomainError("DATABASE_DATA_ERROR", "Database operation failed", 500)
        if state and state.startswith("23"):
            return DomainError("DATABASE_CONSTRAINT_ERROR", "Database operation failed", 500)
    return DomainError("INTERNAL_ERROR", "Internal error", 500)


def register_errors(app):
    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        return error_response(error)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return error_response(
            DomainError(
                "VALIDATION_ERROR",
                "Invalid request",
                422,
                details={
                    "fields": [
                        {"location": list(e["loc"]), "type": e["type"]} for e in error.errors()
                    ]
                },
            )
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, error):
        return error_response(classify_database_error(error))

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return error_response(
            DomainError(
                "NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR",
                "Request not available",
                error.status_code,
            )
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        return error_response(DomainError("INTERNAL_ERROR", "Internal error", 500))
