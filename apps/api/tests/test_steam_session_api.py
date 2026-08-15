from pathlib import Path

from fastapi.testclient import TestClient

from skinflow_api.main import create_app
from skinflow_api.settings import Settings


def test_steam_session_status_is_safe(tmp_path: Path) -> None:
    settings = Settings(environment="test", database_path=str(tmp_path / "session.db"))
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/steam/session")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "absent"
    assert "sessionid" not in body
    assert "login_secure" not in body
