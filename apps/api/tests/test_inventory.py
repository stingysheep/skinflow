from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from skinflow_api.application.inventory import (
    InventoryAsset,
    InventoryService,
    SteamSessionStatus,
)
from skinflow_api.application.scan.models import ScanJob, ScanRequest
from skinflow_api.domain.market.snapshot import MarketSnapshot
from skinflow_api.domain.market.tiers import MarketSide, MarketTier
from skinflow_api.infrastructure.database.inventory import SqliteInventoryRepository
from skinflow_api.infrastructure.database.ledger import LedgerRepository
from skinflow_api.infrastructure.database.sqlite_uow import SqliteScanUnitOfWork
from skinflow_api.infrastructure.platforms.steam.inventory import parse_inventory_page
from skinflow_api.infrastructure.platforms.steam.session import (
    InMemorySteamSession,
    SteamCredentials,
)
from skinflow_api.routes.ledger import create_ledger_router


class FakeGateway:
    def __init__(self, assets: tuple[InventoryAsset, ...]) -> None:
        self._assets = assets

    def fetch_inventory(self) -> tuple[InventoryAsset, ...]:
        return self._assets


def asset(assetid: str = "42", contextid: str = "2") -> InventoryAsset:
    return InventoryAsset(
        "steam", 730, contextid, assetid, "AK-47 | Slate", "AK-47 | Slate", "", "1", "0", True, True
    )


def test_inventory_parser_joins_assets_and_descriptions() -> None:
    items = parse_inventory_page(
        {
            "assets": [{"assetid": "1", "classid": "9", "instanceid": "0"}],
            "descriptions": [
                {
                    "classid": "9",
                    "instanceid": "0",
                    "market_hash_name": "AWP | Asiimov",
                    "name": "AWP | Asiimov",
                    "icon_url": "icon",
                    "marketable": 1,
                    "tradable": 0,
                    "tags": [{"category": "Exterior", "localized_tag_name": "略有磨损"}],
                }
            ],
        },
        "16",
    )
    assert items[0].contextid == "16"
    assert items[0].market_hash_name == "AWP | Asiimov"
    assert items[0].marketable is True
    assert items[0].wear_text == "略有磨损"


def test_inventory_parser_uses_asset_context_instead_of_requested_context() -> None:
    items = parse_inventory_page(
        {
            "assets": [
                {"assetid": "1", "contextid": "2", "classid": "9", "instanceid": "0"}
            ],
            "descriptions": [
                {
                    "classid": "9",
                    "instanceid": "0",
                    "market_hash_name": "AWP | Asiimov",
                    "name": "AWP | Asiimov",
                }
            ],
        },
        "16",
    )

    assert items[0].contextid == "2"


def test_inventory_sync_preserves_missing_assets(tmp_path: Path) -> None:
    repository = SqliteInventoryRepository(tmp_path / "inventory.db")
    repository.sync((asset("first"), asset("second", "16")))
    repository.sync((asset("second", "16"),))
    records = repository.list_assets()
    assert {record["status"] for record in records} == {"available", "missing"}


def test_inventory_service_requires_session_then_syncs(tmp_path: Path) -> None:
    session = InMemorySteamSession()
    repository = SqliteInventoryRepository(tmp_path / "inventory.db")
    service = InventoryService(session, FakeGateway((asset(),)), repository)
    assert service.session_status().status is SteamSessionStatus.ABSENT
    with pytest.raises(PermissionError):
        service.refresh()
    session.set_credentials(SteamCredentials("76561198000000000", "secret", "csrf"))
    assert service.refresh().asset_count == 1
    assert service.list_assets()[0]["assetid"] == "42"


def test_inventory_refresh_route_calls_inventory_service() -> None:
    class Inventory:
        def refresh(self):
            return type("Result", (), {"run_id": "run", "asset_count": 2, "observed_at": 3})()

    app = FastAPI()
    app.include_router(create_ledger_router(object(), Inventory()))
    with TestClient(app) as client:
        response = client.post("/api/inventory/refresh", json={})

    assert response.status_code == 200
    assert response.json() == {"run_id": "run", "asset_count": 2, "observed_at": 3}


def test_inventory_sync_populates_chinese_item_metadata(tmp_path: Path) -> None:
    database = tmp_path / "inventory.db"
    repository = SqliteInventoryRepository(database)
    localized = InventoryAsset(
        "steam", 730, "2", "42", "AK-47 | Slate", "AK-47 | 板岩", "image", "1", "0", True, True
    )
    repository.sync((localized,))

    import sqlite3

    connection = sqlite3.connect(database)
    row = connection.execute(
        "SELECT display_name_zh,image_url FROM item_metadata WHERE market_hash_name=?",
        ("AK-47 | Slate",),
    ).fetchone()
    connection.close()
    assert row == ("AK-47 | 板岩", "image")


def test_grouped_inventory_keeps_held_items_missing_from_current_steam_inventory(
    tmp_path: Path,
) -> None:
    database = tmp_path / "held-inventory.db"
    repository = SqliteInventoryRepository(database)
    repository.sync((asset("available"),))
    LedgerRepository(database).create_purchase("AK-47 | Held", 2, 100, 1_000, None, False)

    groups = repository.list_grouped_assets()

    held = next(group for group in groups if group["market_hash_name"] == "AK-47 | Held")
    assert held["held_quantity"] == 2
    assert held["available_quantity"] == 0


def test_inventory_group_details_returns_recent_steam_book_and_trend(tmp_path: Path) -> None:
    database = tmp_path / "inventory-details.db"
    repository = SqliteInventoryRepository(database)
    repository.sync((asset(),))
    scans = SqliteScanUnitOfWork(database)
    for median, ask, bid, observed in ((210, 220, 205, 1000), (230, 240, 220, 2000)):
        job = ScanJob(ScanRequest("manual", 1, ("AK-47 | Slate",)))
        scans.create_job(job)
        scans.persist_result_and_event(
            job,
            MarketSnapshot(
                "AK-47 | Slate", None, None, observed, None, "CNY", 730,
                (
                    MarketTier(MarketSide.STEAM_ASK, ask, 2),
                    MarketTier(MarketSide.STEAM_BID, bid, 3),
                ),
                "steam-cs2-cny-v1",
                steam_median_price=median,
            ),
            payload={"name": "AK-47 | 板岩"},
        )

    details = repository.get_group_details("AK-47 | Slate")

    assert details is not None
    assert details["display_name"] == "AK-47 | 板岩"
    assert details["current"]["lowest_ask"] == 240
    assert details["current"]["highest_bid"] == 220
    assert [point["median_price"] for point in details["trend"]] == [210, 230]
