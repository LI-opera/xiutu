import time

import pytest
from app.api.dependencies import AuthStore
from app.config import Settings
from app.domain.policies import DomainError
from app.main import create_app
from fastapi.testclient import TestClient
from pydantic import ValidationError

TOKEN = "synthetic-token-for-local-tests-only-12345"
ORIGIN = "http://127.0.0.1:8020"


def make(**kwargs):
    return create_app(Settings(database_url=None, operator_token=TOKEN, **kwargs))


def login(c, origin=ORIGIN):
    return c.post("/api/v2/auth/login", json={"token": TOKEN}, headers={"Origin": origin})


def test_auth_csrf_and_logout():
    with TestClient(make()) as c:
        assert c.get("/api/v2/cases").status_code == 401
        assert c.post("/api/v2/auth/login", json={"token": TOKEN}).status_code == 403
        assert login(c, "https://outside.invalid").status_code == 403
        result = login(c)
        assert result.status_code == 200
        cookie = result.headers["set-cookie"]
        assert "HttpOnly" in cookie and "SameSite=strict" in cookie
        assert "Secure" not in cookie and result.headers["cache-control"] == "no-store"
        actor = result.json()["actor_id"]
        csrf = result.json()["csrf_token"]
        assert csrf != TOKEN
        assert c.get("/api/v2/auth/session").json()["actor_id"] == actor
        assert c.post("/api/v2/auth/logout", headers={"Origin": ORIGIN}).status_code == 403
        result = c.post("/api/v2/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
        assert result.status_code == 200
        assert c.get("/api/v2/auth/session").status_code == 401
        assert login(c).json()["actor_id"] == actor
        assert TOKEN not in c.get("/api/v2/health/ready").text


def test_secure_cookie_and_expiration(monkeypatch):
    settings = Settings(
        database_url=None, operator_token=TOKEN, app_origin="https://localhost:8020"
    )
    app = create_app(settings)
    with TestClient(app, base_url="https://localhost:8020") as c:
        result = login(c, "https://localhost:8020")
        assert "Secure" in result.headers["set-cookie"]
    store = AuthStore(Settings(database_url=None, operator_token=TOKEN, auth_session_seconds=1))
    now = time.monotonic()
    cookie, _ = store.login(TOKEN)
    monkeypatch.setattr(time, "monotonic", lambda: now + 2)
    with pytest.raises(DomainError) as e:
        store.get(cookie)
    assert e.value.status == 401


def test_missing_token_and_secret_validation():
    with TestClient(create_app(Settings(database_url=None, operator_token=None))) as c:
        result = login(c)
        assert result.status_code == 503 and result.json()["error"]["code"] == "AUTH_NOT_CONFIGURED"
        assert c.get("/api/v2/health/live").status_code == 200
    with TestClient(make()) as c:
        result = c.post(
            "/api/v2/auth/login", json={"token": "private-short"}, headers={"Origin": ORIGIN}
        )
        assert result.status_code == 422 and "private-short" not in result.text


def test_rotation_revokes_previous_cookie():
    store = AuthStore(Settings(database_url=None, operator_token=TOKEN))
    old, a = store.login(TOKEN)
    new, b = store.login(TOKEN, old)
    assert a.actor_id == b.actor_id
    with pytest.raises(DomainError):
        store.get(old)
    assert store.get(new) == b


def test_openapi_security_contract():
    app = make()
    spec = app.openapi()
    create = spec["paths"]["/api/v2/cases"]["post"]
    assert create["security"] == [{"SessionCookie": [], "CSRFToken": []}]
    params = {x["name"].lower(): x for x in create["parameters"]}
    assert params["origin"]["required"] and params["idempotency-key"]["required"]
    assert spec["paths"]["/api/v2/cases"]["get"]["security"] == [{"SessionCookie": []}]
    assert "security" not in spec["paths"]["/api/v2/auth/login"]["post"]


def test_loopback_auto_identity_survives_a_process_restart_without_token():
    settings = Settings(
        database_url=None,
        operator_token=TOKEN,
        app_mode="test",
        app_origin="http://localhost:5215",
        local_dev_auto_identity=True,
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8215",
                    client=("127.0.0.1", 49001)) as first:
        initial = first.get("/api/v2/auth/session")
        assert initial.status_code == 200
        assert "HttpOnly" in initial.headers["set-cookie"]
        assert first.get("/api/v2/auth/session").json()["csrf_token"] == initial.json()["csrf_token"]
        old_cookie = first.cookies.get("xiutu_session")
        assert old_cookie
        assert first.post("/api/v2/auth/logout", headers={"Origin": settings.app_origin}).status_code == 403
        assert first.post("/api/v2/auth/logout", headers={
            "Origin": settings.app_origin, "X-CSRF-Token": initial.json()["csrf_token"]
        }).status_code == 200
        assert first.get("/api/v2/auth/session").status_code == 200
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8215",
                    client=("127.0.0.1", 49002)) as restarted:
        restarted.cookies.set("xiutu_session", old_cookie)
        renewed = restarted.get("/api/v2/auth/session")
        assert renewed.status_code == 200
        assert renewed.json()["actor_id"] == initial.json()["actor_id"] == str(settings.operator_id)
        assert renewed.json()["csrf_token"] != initial.json()["csrf_token"]


def test_auto_identity_is_opt_in_and_requires_actual_loopback_sockets():
    settings = Settings(database_url=None, operator_token=TOKEN, app_mode="test",
                        app_origin="http://localhost:5215", local_dev_auto_identity=True)
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8215",
                    client=("192.0.2.8", 49001), headers={
                        "Host": "localhost:5215", "X-Forwarded-For": "127.0.0.1"
                    }) as remote:
        assert remote.get("/api/v2/auth/session").status_code == 401
    with TestClient(create_app(settings.model_copy(update={"local_dev_auto_identity": False})),
                    base_url="http://127.0.0.1:8215", client=("127.0.0.1", 49001)) as disabled:
        assert disabled.get("/api/v2/auth/session").status_code == 401
    with pytest.raises(ValidationError):
        Settings(database_url=None, app_mode="production", local_dev_auto_identity=True)
    with pytest.raises(ValidationError):
        Settings(database_url=None, app_origin="https://example.com",
                 local_dev_auto_identity=True)
