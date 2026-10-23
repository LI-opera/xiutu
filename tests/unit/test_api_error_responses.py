import json
from uuid import uuid4

import psycopg
import pytest
from app.api.errors import classify_database_error, register_errors
from app.config import Settings
from app.main import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)
from sqlalchemy.exc import (
    TimeoutError as PoolTimeout,
)

TOKEN = "synthetic-remediation-token-1234567890"
ORIGIN = "http://127.0.0.1:8020"


@pytest.mark.parametrize("field", ["fault_description", "model", "engine_code", "engine_family"])
@pytest.mark.parametrize("position", [0, 3, 6])
def test_nul_rejected_before_service(field, position):
    app = create_app(Settings(database_url=None, operator_token=TOKEN))
    entered = []

    def forbidden(*args):
        entered.append(True)
        raise AssertionError("Invalid input reached business service")

    app.state.case_service.create = forbidden
    with TestClient(app) as client:
        login = client.post("/api/v2/auth/login", headers={"Origin": ORIGIN}, json={"token": TOKEN})
        headers = {
            "Origin": ORIGIN,
            "X-CSRF-Token": login.json()["csrf_token"],
            "Idempotency-Key": uuid4().hex,
        }
        body = {"vehicle": {"model": "测试车辆"}, "fault_description": "正常正文"}
        target = body if field == "fault_description" else body["vehicle"]
        target[field] = "secret"[:position] + "\x00" + "secret"[position:]
        response = client.post(
            "/api/v2/cases",
            headers=headers,
            content=json.dumps(body),
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert response.json()["error"]["retryable"] is False
        assert "secret" not in response.text and TOKEN not in response.text
        assert not entered


@pytest.mark.parametrize(
    "error,status,code,retryable",
    [
        (
            DataError(
                "secret SQL",
                {"secret": "value"},
                psycopg.errors.InvalidTextRepresentation("secret"),
            ),
            500,
            "DATABASE_DATA_ERROR",
            False,
        ),
        (
            IntegrityError("secret SQL", {}, psycopg.errors.UniqueViolation("secret")),
            500,
            "DATABASE_CONSTRAINT_ERROR",
            False,
        ),
        (
            IntegrityError("secret SQL", {}, psycopg.errors.ForeignKeyViolation("secret")),
            500,
            "DATABASE_CONSTRAINT_ERROR",
            False,
        ),
        (
            ProgrammingError("secret SQL", {}, psycopg.errors.UndefinedTable("secret")),
            500,
            "INTERNAL_ERROR",
            False,
        ),
        (SQLAlchemyError("secret"), 500, "INTERNAL_ERROR", False),
        (
            OperationalError(None, None, psycopg.OperationalError("secret")),
            503,
            "DATABASE_UNAVAILABLE",
            False,
        ),
        (
            OperationalError("SELECT secret", {}, psycopg.OperationalError("secret")),
            500,
            "INTERNAL_ERROR",
            False,
        ),
        (
            OperationalError(None, None, psycopg.errors.InvalidCatalogName("secret")),
            503,
            "DATABASE_UNAVAILABLE",
            False,
        ),
        (
            OperationalError("SELECT secret", {}, psycopg.errors.SerializationFailure("secret")),
            503,
            "DATABASE_BUSY",
            True,
        ),
    ],
)
def test_database_error_response(error, status, code, retryable):
    app = FastAPI()
    register_errors(app)

    @app.get("/")
    def fail():
        raise error

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/")
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["retryable"] is retryable
    assert "secret" not in response.text and "SQL" not in response.text
    assert classify_database_error(error).status == status


@pytest.mark.parametrize(
    "error,code,retryable",
    [
        (
            OperationalError(None, None, psycopg.errors.InvalidPassword("secret")),
            "DATABASE_UNAVAILABLE",
            False,
        ),
        (
            OperationalError(
                None,
                None,
                psycopg.errors.InvalidAuthorizationSpecification("secret"),
                connection_invalidated=True,
            ),
            "DATABASE_UNAVAILABLE",
            False,
        ),
        (
            OperationalError(
                None, None, psycopg.errors.InvalidCatalogName("secret"), connection_invalidated=True
            ),
            "DATABASE_UNAVAILABLE",
            False,
        ),
        (
            OperationalError(
                None, None, psycopg.OperationalError("secret"), connection_invalidated=True
            ),
            "DATABASE_UNAVAILABLE",
            False,
        ),
        (
            OperationalError(None, None, psycopg.errors.ConnectionFailure("secret")),
            "DATABASE_UNAVAILABLE",
            True,
        ),
        (
            OperationalError(None, None, psycopg.errors.CannotConnectNow("secret")),
            "DATABASE_UNAVAILABLE",
            True,
        ),
        (
            OperationalError("SELECT secret", {}, psycopg.errors.DeadlockDetected("secret")),
            "DATABASE_BUSY",
            True,
        ),
        (
            OperationalError("SELECT secret", {}, psycopg.errors.LockNotAvailable("secret")),
            "DATABASE_BUSY",
            True,
        ),
        (
            OperationalError("SELECT secret", {}, psycopg.errors.QueryCanceled("secret")),
            "DATABASE_BUSY",
            True,
        ),
        (PoolTimeout("secret"), "DATABASE_BUSY", True),
    ],
)
def test_retry_requires_structured_evidence(error, code, retryable):
    # Exercise the registered ASGI handler, including secrecy checks.
    test_database_error_response(error, 503, code, retryable)
