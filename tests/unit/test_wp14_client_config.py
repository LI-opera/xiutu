from uuid import uuid4

from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

TOKEN = "wp14-client-config-token-value-123456"
ORIGIN = "http://localhost:5214"


def test_client_config_requires_session_and_reports_effective_limit(tmp_path):
    app = create_app(
        Settings(
            _env_file=None,
            app_mode="test",
            retrieval_profile="formal",
            database_url=None,
            data_path=tmp_path,
            operator_id=uuid4(),
            operator_token=TOKEN,
            app_origin=ORIGIN,
            upload_max_bytes=4096,
            deepseek_api_key=None,
            tool_mode="local",
        )
    )
    with TestClient(app) as client:
        operation = app.openapi()["paths"]["/api/v2/client-config"]["get"]
        assert operation["security"] == [{"SessionCookie": []}]
        assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/ClientConfig")
        assert client.get("/api/v2/client-config").status_code == 401
        login = client.post(
            "/api/v2/auth/login", headers={"Origin": ORIGIN}, json={"token": TOKEN}
        )
        assert login.status_code == 200
        response = client.get("/api/v2/client-config")
        assert response.status_code == 200
        assert response.json() == {
            "upload_max_bytes": 4096,
            "retrieval_profile": "formal",
        }
