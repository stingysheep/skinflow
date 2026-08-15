from pathlib import Path

from fastapi.testclient import TestClient

from skinflow_api.main import create_app
from skinflow_api.settings import Settings


def test_desktop_auth_cookie_and_write_guards(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        database_path=str(tmp_path / "auth.db"),
        startup_token="a" * 32,
        allowed_origin="http://127.0.0.1:58150",
        allowed_host="127.0.0.1:58150",
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:58150") as client:
        rejected = client.post("/api/purchases", json={})
        assert rejected.status_code == 403
        exchange = client.post("/api/auth/session", json={"startup_token": "a" * 32})
        assert exchange.status_code == 200
        assert "HttpOnly" in exchange.headers["set-cookie"]
        assert "SameSite=strict" in exchange.headers["set-cookie"]
        accepted_origin = {"Origin": "http://127.0.0.1:58150"}
        invalid = client.post("/api/purchases", json={}, headers=accepted_origin)
        assert invalid.status_code == 422


def test_write_rejects_non_json(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        database_path=str(tmp_path / "auth.db"),
        startup_token="b" * 32,
        allowed_origin="http://127.0.0.1:58150",
        allowed_host="127.0.0.1:58150",
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:58150") as client:
        client.post("/api/auth/session", json={"startup_token": "b" * 32})
        response = client.post(
            "/api/purchases",
            content="x=1",
            headers={"Origin": "http://127.0.0.1:58150", "Content-Type": "text/plain"},
        )
        assert response.status_code == 415
