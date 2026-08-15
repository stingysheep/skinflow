from fastapi.testclient import TestClient

from skinflow_api.main import create_app
from skinflow_api.settings import Settings


def test_health_contract() -> None:
    app = create_app(
        Settings(
            app_name="Skinflow Test",
            api_version="9.9.9",
            environment="test",
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Skinflow Test",
        "api_version": "9.9.9",
        "environment": "test",
    }


def test_inventory_and_platform_health_are_available(tmp_path) -> None:
    app = create_app(Settings(environment="test", database_path=str(tmp_path / "api.db")))
    with TestClient(app) as client:
        inventory = client.get("/api/inventory")
        platform = client.get("/api/platform-health")
    assert inventory.status_code == 200
    assert inventory.json()["status"] == "session_required"
    assert platform.status_code == 200
