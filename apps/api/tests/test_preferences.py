from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from skinflow_api.application.preferences.csqaq import CsqaqConfigurationService
from skinflow_api.infrastructure.preferences.file_store import JsonPreferencesStore
from skinflow_api.main import create_app
from skinflow_api.routes.preferences import create_preferences_router
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


def test_csqaq_token_is_not_exposed_through_generic_preferences(tmp_path: Path) -> None:
    class MemoryTokenStore:
        def __init__(self) -> None:
            self.value: str | None = None

        def load(self) -> str | None:
            return self.value

        def save(self, token: str) -> None:
            self.value = token or None

    class ReadyConnection:
        def __init__(self) -> None:
            self.token = ""

        def configure(self, token: str) -> None:
            self.token = token

        def validate_connection(self) -> str:
            return "ready" if self.token else "missing"

    database = tmp_path / "skinflow.db"
    store = JsonPreferencesStore(database)
    tokens = MemoryTokenStore()
    connection = ReadyConnection()
    service = CsqaqConfigurationService(store, tokens, connection, "")

    app = FastAPI()
    app.include_router(create_preferences_router(store, service))
    with TestClient(app) as client:
        saved = client.put(
            "/api/preferences/csqaq",
            json={"token": "secret-token", "whitelist_ip": "203.0.113.9"},
        )
        all_preferences = client.get("/api/preferences")

    assert saved.json() == {
        "token_configured": True,
        "whitelist_ip": "203.0.113.9",
        "status": "ready",
    }
    assert tokens.load() == "secret-token"
    assert "secret-token" not in str(all_preferences.json())
