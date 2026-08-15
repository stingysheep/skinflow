from pathlib import Path

from fastapi.testclient import TestClient

from skinflow_api.main import create_app
from skinflow_api.settings import Settings


def test_preferences_survive_a_new_app_instance(tmp_path: Path) -> None:
    database = tmp_path / "skinflow.db"
    settings = Settings(environment="test", database_path=str(database))

    with TestClient(create_app(settings)) as client:
        saved = client.put(
            "/api/preferences/skinflow.inventory.trade",
            json={"value": "cooldown"},
        )
        assert saved.status_code == 200

    with TestClient(create_app(settings)) as client:
        restored = client.get("/api/preferences/skinflow.inventory.trade")

    assert restored.status_code == 200
    assert restored.json() == {
        "key": "skinflow.inventory.trade",
        "found": True,
        "value": "cooldown",
    }
