import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from app.config import Settings
from app.domain.policies import DomainError
from app.domain.schemas import CreateCase
from app.infrastructure.orm import cases, idempotency_keys
from app.infrastructure.uow import make_engine
from app.main import create_app
from app.repositories.cases import CaseRepository
from app.services.case_service import CaseService
from fastapi.testclient import TestClient
from sqlalchemy import func, select

pytestmark = pytest.mark.database
TOKEN = "synthetic-integration-token-local-only-123"
ORIGIN = "http://127.0.0.1:8020"
DATA = {
    "workbench_flow": "template-match-v1",
    "vehicle": {"brand": "大众", "model": "探岳", "year": 2019},
    "fault_description": "Synthetic only",
    "fault_codes": ["p0299"],
}


@pytest.fixture
def service(database_url):
    engine = make_engine(database_url)
    try:
        yield CaseService(engine, b"synthetic-cursor-key")
    finally:
        engine.dispose()


def test_owner_isolation_and_paging(service):
    a, b = uuid4(), uuid4()
    one = service.create(a, CreateCase.model_validate(DATA), "owner-key")[1]
    service.create(b, CreateCase.model_validate(DATA), "owner-key")
    assert len(service.list(a, 50)["items"]) == 1
    with pytest.raises(DomainError) as e:
        service.get(b, UUID(one["id"]))
    assert e.value.status == 404
    for i in range(3):
        service.create(a, CreateCase.model_validate(DATA), f"page-{i}")
    first = service.list(a, 2)
    second = service.list(a, 2, first["next_cursor"])
    assert len({x["id"] for x in first["items"] + second["items"]}) == 4
    assert second["next_cursor"] is None
    for cursor in ["garbage", first["next_cursor"] + "a"]:
        with pytest.raises(DomainError):
            service.list(a, 2, cursor)
    with pytest.raises(DomainError):
        service.list(b, 2, first["next_cursor"])


def test_idempotency_serial_and_revision(service):
    actor = uuid4()
    data = CreateCase.model_validate(DATA)
    result = service.create(actor, data, "same")
    assert service.create(actor, data, "same") == result
    equivalent = CreateCase.model_validate(
        DATA | {"fault_codes": [" P0299 ", "p0299"], "fault_description": " Synthetic only "}
    )
    assert service.create(actor, equivalent, "same") == result
    with pytest.raises(DomainError) as e:
        service.create(
            actor, CreateCase.model_validate(DATA | {"fault_description": "other"}), "same"
        )
    assert e.value.code == "IDEMPOTENCY_CONFLICT"
    with pytest.raises(DomainError) as e:
        service.get(actor, UUID(result[1]["id"]), expected_revision=2)
    assert e.value.code == "REVISION_CONFLICT"
    assert service.get(actor, UUID(result[1]["id"])) == result[1]
    assert result[1]["revision"] == 1 and result[1]["template_progress"]["recorded"] == 0


def test_true_concurrent_idempotency(service):
    actor = uuid4()
    barrier = threading.Barrier(4)

    def create(_):
        barrier.wait(timeout=10)
        return service.create(actor, CreateCase.model_validate(DATA), "parallel")

    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(create, range(4)))
    assert all(x == results[0] for x in results)
    with service.engine.connect() as c:
        assert (
            c.scalar(select(func.count()).select_from(cases).where(cases.c.owner_id == actor)) == 1
        )
        assert (
            c.scalar(
                select(func.count())
                .select_from(idempotency_keys)
                .where(idempotency_keys.c.actor_id == actor)
            )
            == 1
        )
    print("concurrent_same_key: four transactions -> one case and one response")


def test_failure_rolls_back_both(service, monkeypatch):
    actor = uuid4()
    original = CaseRepository.create

    def fail_after_insert(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("synthetic rollback trigger")

    with monkeypatch.context() as m:
        m.setattr(CaseRepository, "create", fail_after_insert)
        with pytest.raises(RuntimeError):
            service.create(actor, CreateCase.model_validate(DATA), "rollback")
    with service.engine.connect() as c:
        assert (
            c.scalar(select(func.count()).select_from(cases).where(cases.c.owner_id == actor)) == 0
        )
        assert (
            c.scalar(
                select(func.count())
                .select_from(idempotency_keys)
                .where(idempotency_keys.c.actor_id == actor)
            )
            == 0
        )
    assert service.create(actor, CreateCase.model_validate(DATA), "rollback")[0] == 201


def test_http_auth_create_read_list(database_url):
    owner = uuid4()
    app = create_app(Settings(database_url=database_url, operator_token=TOKEN, operator_id=owner))
    other = create_app(
        Settings(database_url=database_url, operator_token=TOKEN, operator_id=uuid4())
    )
    with TestClient(app) as c, TestClient(other) as stranger:
        result = c.post("/api/v2/auth/login", json={"token": TOKEN}, headers={"Origin": ORIGIN})
        csrf = result.json()["csrf_token"]
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf, "Idempotency-Key": "http"}
        assert c.post("/api/v2/cases", json=DATA, headers={"Origin": ORIGIN}).status_code == 403
        assert (
            c.post(
                "/api/v2/cases", json=DATA, headers=headers | {"Origin": "https://evil.invalid"}
            ).status_code
            == 403
        )
        assert (
            c.post(
                "/api/v2/cases", json=DATA | {"owner_id": str(owner)}, headers=headers
            ).status_code
            == 422
        )
        assert (
            c.post(
                "/api/v2/cases",
                json=DATA | {"vehicle": {"model": "x", "extra": 1}},
                headers=headers,
            ).status_code
            == 422
        )
        result = c.post("/api/v2/cases", json=DATA, headers=headers)
        assert result.status_code == 201
        body = result.json()
        assert body == c.get("/api/v2/cases/" + body["id"]).json()
        assert c.get("/api/v2/cases").json()["items"] == [body]
        assert c.get("/api/v2/cases?limit=51").status_code == 422
        assert c.get("/api/v2/cases?cursor=broken").status_code == 400
        assert c.post("/api/v2/cases", json=DATA, headers=headers).json() == body
        assert (
            c.post(
                "/api/v2/cases", json=DATA, headers=headers | {"X-CSRF-Token": "wrong"}
            ).status_code
            == 403
        )
        assert (
            c.post(
                "/api/v2/cases", json=DATA | {"fault_description": "different"}, headers=headers
            ).status_code
            == 409
        )
        stranger.post("/api/v2/auth/login", json={"token": TOKEN}, headers={"Origin": ORIGIN})
        assert stranger.get("/api/v2/cases/" + body["id"]).status_code == 404
        assert stranger.get("/api/v2/cases").json()["items"] == []
        assert "owner_id" not in body
        spec = c.get("/openapi.json").json()
        assert set(spec["paths"]["/api/v2/cases"]) == {"get", "post"}
        assert spec["paths"]["/api/v2/cases"]["post"]["responses"]["422"]["content"][
            "application/json"
        ]["schema"]["$ref"].endswith("ErrorEnvelope")
