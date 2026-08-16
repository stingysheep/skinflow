import sqlite3
from collections import deque
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from skinflow_api.application.inventory.errors import (
    InventoryRateLimited,
    InventoryUnavailable,
    SteamSessionExpired,
)
from skinflow_api.application.inventory.service import InventoryService
from skinflow_api.application.scan.upstream_errors import RateLimited, UpstreamUnavailable
from skinflow_api.infrastructure.database.inventory import SqliteInventoryRepository
from skinflow_api.infrastructure.platforms.steam.inventory import SteamInventoryAdapter
from skinflow_api.infrastructure.platforms.steam.session import (
    InMemorySteamSession,
    SteamCredentials,
)
from skinflow_api.routes.errors import install_error_handlers


class SequenceClient:
    def __init__(self, responses: list[dict | Exception]) -> None:
        self.responses = deque(responses)
        self.calls = 0
        self.urls: list[str] = []

    def request_json(self, url: str, **_kwargs) -> dict:
        self.calls += 1
        self.urls.append(url)
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        return response


def active_session() -> InMemorySteamSession:
    session = InMemorySteamSession()
    session.set_credentials(SteamCredentials("76561198000000000", "secret", "csrf"))
    return session


def empty_page() -> dict:
    return {"success": 1, "assets": [], "descriptions": [], "more_items": 0}


def test_inventory_retries_rate_limit_then_reads_owned_context() -> None:
    client = SequenceClient([{}, RateLimited(), empty_page(), empty_page()])
    delays: list[float] = []
    adapter = SteamInventoryAdapter(active_session(), client, sleep=delays.append)

    assert adapter.fetch_inventory() == ()
    assert client.calls == 4
    assert delays == [2.0]


def test_inventory_continues_pagination_after_page_without_marketable_assets() -> None:
    client = SequenceClient(
        [
            {},
            {
                "success": 1,
                "assets": [{"assetid": "ignored", "classid": "1", "instanceid": "0"}],
                "descriptions": [],
                "more_items": 1,
                "last_assetid": "100",
            },
            {
                "success": 1,
                "assets": [{"assetid": "42", "classid": "9", "instanceid": "0"}],
                "descriptions": [
                    {
                        "classid": "9",
                        "instanceid": "0",
                        "market_hash_name": "AK-47 | Slate",
                        "name": "AK-47 | Slate",
                        "marketable": 1,
                        "tradable": 1,
                    }
                ],
                "more_items": 0,
            },
            empty_page(),
        ]
    )
    adapter = SteamInventoryAdapter(active_session(), client, sleep=lambda _delay: None)

    assets = adapter.fetch_inventory()

    assert [item.assetid for item in assets] == ["42"]
    assert client.calls == 4


def test_inventory_reads_trade_protected_context() -> None:
    protected_page = {
        "success": 1,
        "assets": [
            {
                "assetid": "protected",
                "contextid": "16",
                "classid": "9",
                "instanceid": "0",
            }
        ],
        "descriptions": [
            {
                "classid": "9",
                "instanceid": "0",
                "market_hash_name": "P90 | Neoqueen (Factory New)",
                "name": "P90 | Neoqueen",
                "marketable": 0,
                "tradable": 0,
            }
        ],
        "more_items": 0,
    }
    client = SequenceClient([{}, empty_page(), protected_page])
    adapter = SteamInventoryAdapter(active_session(), client, sleep=lambda _delay: None)

    assets = adapter.fetch_inventory()

    assert [(item.assetid, item.contextid) for item in assets] == [("protected", "16")]
    assert any("/730/16?" in url for url in client.urls)


def test_inventory_deduplicates_asset_visible_in_primary_and_trade_contexts() -> None:
    def page(contextid: str, tradable: int) -> dict:
        return {
            "success": 1,
            "assets": [{
                "assetid": "listed",
                "contextid": contextid,
                "classid": "9",
                "instanceid": "0",
            }],
            "descriptions": [{
                "classid": "9",
                "instanceid": "0",
                "market_hash_name": "P90 | Neoqueen (Factory New)",
                "name": "P90 | Neoqueen",
                "marketable": tradable,
                "tradable": tradable,
            }],
            "more_items": 0,
        }

    client = SequenceClient([{}, page("2", 1), page("16", 0)])
    adapter = SteamInventoryAdapter(active_session(), client, sleep=lambda _delay: None)

    assets = adapter.fetch_inventory()

    assert [(item.assetid, item.contextid) for item in assets] == [("listed", "2")]


def test_inventory_accepts_authenticated_probe_bad_request() -> None:
    client = SequenceClient(
        [
            UpstreamUnavailable("authenticated probe", status_code=400),
            empty_page(),
            empty_page(),
        ]
    )
    adapter = SteamInventoryAdapter(active_session(), client, sleep=lambda _delay: None)

    assert adapter.fetch_inventory() == ()


def test_inventory_exhausted_rate_limit_has_structured_retry_after() -> None:
    client = SequenceClient([{}, *[RateLimited(retry_after_seconds=5) for _ in range(4)]])
    delays: list[float] = []
    adapter = SteamInventoryAdapter(active_session(), client, sleep=delays.append)

    with pytest.raises(InventoryRateLimited) as caught:
        adapter.fetch_inventory()

    assert caught.value.retry_after_seconds == 5
    assert client.calls == 5
    assert delays == [5.0, 5.0, 5.0]


def test_inventory_marks_unauthorized_session_expired() -> None:
    session = active_session()
    client = SequenceClient([UpstreamUnavailable("unauthorized", status_code=401)])
    adapter = SteamInventoryAdapter(session, client, sleep=lambda _delay: None)

    with pytest.raises(SteamSessionExpired):
        adapter.fetch_inventory()

    assert session.status().status == "expired"


def test_failed_refresh_is_recorded_without_removing_existing_assets(tmp_path: Path) -> None:
    database = tmp_path / "inventory.db"
    repository = SqliteInventoryRepository(database)

    class FailingGateway:
        def fetch_inventory(self):
            raise InventoryUnavailable("Steam 库存服务暂时不可用")

    service = InventoryService(active_session(), FailingGateway(), repository)
    with pytest.raises(InventoryUnavailable):
        service.refresh()

    connection = sqlite3.connect(database)
    row = connection.execute(
        "SELECT status,failure_code FROM inventory_sync_run ORDER BY observed_at DESC LIMIT 1"
    ).fetchone()
    connection.close()
    assert row == ("failed", "STEAM_INVENTORY_UNAVAILABLE")


def test_inventory_rate_limit_api_error_is_retryable() -> None:
    app = FastAPI()

    @app.get("/limited")
    def limited() -> None:
        raise InventoryRateLimited(7)

    install_error_handlers(app)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/limited")

    assert response.status_code == 429
    assert (
        response.json()["error"]
        | {
            "code": "STEAM_INVENTORY_RATE_LIMITED",
            "retryable": True,
            "retry_after_seconds": 7,
        }
        == response.json()["error"]
    )
