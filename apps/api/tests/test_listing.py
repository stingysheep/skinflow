import sqlite3
from pathlib import Path
from threading import Event, Thread

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from skinflow_api.application.inventory.models import InventoryAsset
from skinflow_api.application.listing.models import (
    ListingGatewayResult,
    ListingGroupSelection,
    ListingMarketSnapshot,
    ListingSelection,
)
from skinflow_api.application.listing.service import ListingService
from skinflow_api.domain.market.snapshot import MarketSnapshot
from skinflow_api.domain.market.tiers import MarketSide, MarketTier
from skinflow_api.infrastructure.database.inventory import SqliteInventoryRepository
from skinflow_api.infrastructure.database.ledger import LedgerRepository
from skinflow_api.infrastructure.database.listing import SqliteListingRepository
from skinflow_api.infrastructure.database.sqlite_uow import SqliteScanUnitOfWork
from skinflow_api.routes.listing import PreviewRequest, create_listing_router


class Gateway:
    def __init__(self, result: ListingGatewayResult) -> None:
        self.result = result
        self.calls = 0
        self.decisions: list[dict] = []

    def submit(self, decision: dict) -> ListingGatewayResult:
        self.calls += 1
        self.decisions.append(decision)
        return self.result


def test_cancel_route_reconciles_missing_listing_ids_before_cancelling() -> None:
    events: list[str] = []

    class Service:
        def cancel_items(self, item_ids: tuple[str, ...]) -> dict:
            events.append("cancel")
            return {"items": [{"id": item_ids[0], "status": "cancelled"}]}

    class Reconciler:
        async def reconcile_now(self) -> dict:
            events.append("reconcile")
            return {"checked": 1}

    app = FastAPI()
    app.include_router(create_listing_router(Service(), Reconciler()))  # type: ignore[arg-type]

    with TestClient(app) as client:
        response = client.post("/api/listing-requests/cancel", json={"item_ids": ["item-1"]})

    assert response.status_code == 200
    assert events == ["reconcile", "cancel"]


def _seed(path: Path) -> tuple[SqliteListingRepository, str]:
    asset = InventoryAsset(
        "steam", 730, "2", "asset", "AK-47 | Slate", "AK-47 | Slate", "", "1", "0", True, True
    )
    SqliteInventoryRepository(path).sync((asset,))
    LedgerRepository(path).create_purchase("AK-47 | Slate", 1, 100, 1000, None, False)
    uow = SqliteScanUnitOfWork(path)
    snapshot = MarketSnapshot(
        "AK-47 | Slate", None, None, 1000, None, "CNY", 730,
        (MarketTier(MarketSide.STEAM_ASK, 200, 5),), "steam-cs2-cny-v1",
    )
    from skinflow_api.application.scan.models import ScanJob, ScanRequest

    job = ScanJob(ScanRequest("manual", 1, ("AK-47 | Slate",)))
    uow.create_job(job)
    uow.persist_result_and_event(job, snapshot, payload={"name": "AK-47 | Slate"})
    return SqliteListingRepository(path), asset.assetid


def test_listing_preview_and_idempotent_submit(tmp_path: Path) -> None:
    repository, assetid = _seed(tmp_path / "listing.db")
    gateway = Gateway(ListingGatewayResult(True, True, "123", None))
    service = ListingService(repository, repository, gateway)
    preview = service.create_preview((ListingSelection("steam", 730, "2", assetid),))
    assert preview["items"][0]["seller_proceeds"] > 0
    first = service.submit(preview["id"], "test-key")
    second = service.submit(preview["id"], "test-key")
    assert first["status"] == "submitted"
    assert second["replayed"] is True
    assert gateway.calls == 1


def test_buyer_paid_price_is_converted_to_steam_seller_price_before_submit(
    tmp_path: Path,
) -> None:
    repository, assetid = _seed(tmp_path / "listing-price-contract.db")
    gateway = Gateway(ListingGatewayResult(True, True, "123", None))
    service = ListingService(repository, repository, gateway)

    preview = service.create_preview(
        (ListingSelection("steam", 730, "2", assetid, buyer_pays=31),)
    )
    service.submit(preview["id"], "price-contract-key")

    assert gateway.decisions[0]["buyer_pays"] == 31
    assert gateway.decisions[0]["seller_proceeds"] == 21


def test_listing_preview_refreshes_live_book_and_uses_highest_bid(tmp_path: Path) -> None:
    repository, assetid = _seed(tmp_path / "listing-live-book.db")
    calls = 0

    class Provider:
        def fetch(self, context):
            nonlocal calls
            calls += 1
            snapshot = MarketSnapshot(
                context.asset.market_hash_name,
                None,
                None,
                2000,
                None,
                "CNY",
                730,
                (
                    MarketTier(MarketSide.STEAM_BID, 220, 2),
                    MarketTier(MarketSide.STEAM_ASK, 230, 2),
                ),
                "steam-cs2-cny-v1",
            )
            snapshot_id, job_id = repository.save_listing_snapshot(snapshot)
            return ListingMarketSnapshot(
                snapshot,
                snapshot_id,
                job_id,
                snapshot.for_side(MarketSide.STEAM_ASK),
                snapshot.for_side(MarketSide.STEAM_BID),
            )

    service = ListingService(
        repository,
        repository,
        Gateway(ListingGatewayResult(True, False, "1", None)),
        Provider(),
    )

    preview = service.create_preview((ListingSelection("steam", 730, "2", assetid),))

    assert calls == 1
    assert preview["items"][0]["buyer_pays"] == 220
    assert preview["items"][0]["bid_levels"][0]["price"] == 220


def test_reconciliation_activation_persists_steam_id_and_inventory_status(
    tmp_path: Path,
) -> None:
    repository, assetid = _seed(tmp_path / "listing-activation-state.db")
    service = ListingService(
        repository,
        repository,
        Gateway(ListingGatewayResult(True, True, None, None)),
    )
    preview = service.create_preview((ListingSelection("steam", 730, "2", assetid),))
    request = service.submit(preview["id"], "activation-state-key")

    repository.mark_active(request["items"][0]["id"], 2_000, "listing-real")

    current = repository.get_request(request["id"])
    inventory = SqliteInventoryRepository(tmp_path / "listing-activation-state.db")
    assert current is not None
    assert current["items"][0]["steam_listing_id"] == "listing-real"
    assert current["items"][0]["status"] == "active"
    assert inventory.list_assets()[0]["status"] == "listed"


def test_reconciliation_backfills_steam_id_for_existing_active_item(tmp_path: Path) -> None:
    repository, assetid = _seed(tmp_path / "listing-active-id-backfill.db")
    service = ListingService(
        repository,
        repository,
        Gateway(ListingGatewayResult(True, True, None, None)),
    )
    preview = service.create_preview((ListingSelection("steam", 730, "2", assetid),))
    request = service.submit(preview["id"], "active-id-backfill-key")
    item_id = request["items"][0]["id"]
    repository.mark_active(item_id, 2_000)

    repository.mark_active(item_id, 3_000, "listing-backfilled")

    current = repository.get_request(request["id"])
    assert current is not None
    assert current["items"][0]["status"] == "active"
    assert current["items"][0]["steam_listing_id"] == "listing-backfilled"


def test_listing_blocks_active_asset(tmp_path: Path) -> None:
    repository, assetid = _seed(tmp_path / "listing.db")
    service = ListingService(
        repository, repository, Gateway(ListingGatewayResult(True, False, "1", None))
    )
    preview = service.create_preview((ListingSelection("steam", 730, "2", assetid),))
    service.submit(preview["id"], "key-one")
    with pytest.raises(ValueError, match="active listing"):
        service.create_preview((ListingSelection("steam", 730, "2", assetid),))


def test_listing_uncertain_transport_is_not_retried(tmp_path: Path) -> None:
    repository, assetid = _seed(tmp_path / "listing.db")

    class FailingGateway:
        def submit(self, _decision: dict) -> ListingGatewayResult:
            raise TimeoutError

    service = ListingService(repository, repository, FailingGateway())
    preview = service.create_preview((ListingSelection("steam", 730, "2", assetid),))
    request = service.submit(preview["id"], "uncertain-key")
    assert request["status"] == "pending_reconciliation"
    assert len(repository.list_requests()) == 1


def test_listing_reconciliation_promotes_request_after_uncertain_submit(tmp_path: Path) -> None:
    repository, assetid = _seed(tmp_path / "listing-reconcile-active.db")

    class FailingGateway:
        def submit(self, _decision: dict) -> ListingGatewayResult:
            raise TimeoutError

    service = ListingService(repository, repository, FailingGateway())
    preview = service.create_preview((ListingSelection("steam", 730, "2", assetid),))
    request = service.submit(preview["id"], "uncertain-active-key")

    repository.mark_active(request["items"][0]["id"], 2_000)

    updated = repository.get_request(request["id"])
    assert updated is not None
    assert updated["status"] == "submitted"
    assert updated["items"][0]["status"] == "active"


def test_listing_preview_fetches_missing_steam_snapshot(tmp_path: Path) -> None:
    repository, assetid = _seed(tmp_path / "listing-missing-snapshot.db")
    repository._connection.execute("DELETE FROM market_tier")
    repository._connection.execute("DELETE FROM scan_result")
    repository._connection.execute("DELETE FROM market_snapshot")
    repository._connection.execute("DELETE FROM scan_event")
    repository._connection.execute("DELETE FROM scan_job")
    repository._connection.commit()

    class Provider:
        def fetch(self, context):
            snapshot = MarketSnapshot(
                context.asset.market_hash_name, None, None, 2000, None, "CNY", 730,
                (MarketTier(MarketSide.STEAM_ASK, 230, 2),), "steam-cs2-cny-v1",
            )
            snapshot_id, job_id = repository.save_listing_snapshot(snapshot)
            return ListingMarketSnapshot(
                snapshot, snapshot_id, job_id, snapshot.for_side(MarketSide.STEAM_ASK)
            )

    service = ListingService(
        repository,
        repository,
        Gateway(ListingGatewayResult(True, False, "1", None)),
        Provider(),
    )
    preview = service.create_preview((ListingSelection("steam", 730, "2", assetid),))
    assert preview["items"][0]["market_snapshot_id"]
    assert preview["items"][0]["buyer_pays"] > 0


def test_listing_preview_does_not_wait_for_advisory_trend_refresh(tmp_path: Path) -> None:
    repository, assetid = _seed(tmp_path / "listing-trend-refresh.db")
    started = Event()
    completed = Event()
    release = Event()

    class SlowTrendProvider:
        def refresh_trend(self, _market_hash_name):
            started.set()
            release.wait(2)

        def fetch(self, context):
            snapshot = MarketSnapshot(
                context.asset.market_hash_name, None, None, 2000, None, "CNY", 730,
                (MarketTier(MarketSide.STEAM_ASK, 230, 2),), "steam-cs2-cny-v1",
            )
            snapshot_id, job_id = repository.save_listing_snapshot(snapshot)
            return ListingMarketSnapshot(
                snapshot, snapshot_id, job_id, snapshot.for_side(MarketSide.STEAM_ASK)
            )

    service = ListingService(
        repository,
        repository,
        Gateway(ListingGatewayResult(True, False, "1", None)),
        SlowTrendProvider(),
    )
    result: list[dict] = []

    def create_preview():
        try:
            result.append(service.create_preview((ListingSelection("steam", 730, "2", assetid),)))
        finally:
            completed.set()

    worker = Thread(
        target=create_preview,
        daemon=True,
    )
    worker.start()
    try:
        assert started.wait(1)
        assert completed.wait(1)
        worker.join(1)
        assert not worker.is_alive()
        assert result[0]["items"][0]["buyer_pays"] > 0
    finally:
        release.set()
        worker.join(1)


def test_listing_repository_migrates_old_preview_item_schema(tmp_path: Path) -> None:
    path = tmp_path / "old-listing.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        "CREATE TABLE listing_preview_item ("
        "id TEXT PRIMARY KEY, preview_id TEXT, platform TEXT, appid INTEGER, "
        "contextid TEXT, assetid TEXT, market_hash_name TEXT, market_snapshot_id TEXT, "
        "buyer_pays INTEGER, steam_fee INTEGER, publisher_fee INTEGER, "
        "seller_proceeds INTEGER, cost_each INTEGER, ratio_ppm INTEGER, "
        "fee_policy_version TEXT NOT NULL);"
    )
    connection.close()
    SqliteListingRepository(path)
    columns = {
        row[1]
        for row in sqlite3.connect(path).execute(
            "PRAGMA table_info(listing_preview_item)"
        ).fetchall()
    }
    assert "market_snapshot_job_id" in columns


def test_grouped_preview_uses_moving_average_and_oldest_tradable_assets(tmp_path: Path) -> None:
    path = tmp_path / "grouped-listing.db"
    assets = tuple(
        InventoryAsset(
            "steam", 730, "2", assetid, "AK-47 | Slate", "AK-47 | Slate", "", "1", "0", True, True
        )
        for assetid in ("older", "newer")
    )
    SqliteInventoryRepository(path).sync(assets)
    ledger = LedgerRepository(path)
    ledger.create_purchase("AK-47 | Slate", 1, 100, 1000, None, False)
    ledger.create_purchase("AK-47 | Slate", 1, 300, 2000, None, False)
    uow = SqliteScanUnitOfWork(path)
    snapshot = MarketSnapshot(
        "AK-47 | Slate", None, None, 1000, None, "CNY", 730,
        (MarketTier(MarketSide.STEAM_ASK, 200, 5),), "steam-cs2-cny-v1",
    )
    from skinflow_api.application.scan.models import ScanJob, ScanRequest

    job = ScanJob(ScanRequest("manual", 1, ("AK-47 | Slate",)))
    uow.create_job(job)
    uow.persist_result_and_event(job, snapshot, payload={"name": "AK-47 | Slate"})
    repository = SqliteListingRepository(path)
    service = ListingService(
        repository, repository, Gateway(ListingGatewayResult(True, False, "1", None))
    )

    preview = service.create_grouped_preview((ListingGroupSelection("AK-47 | Slate", 2, 200),))

    assert [item["assetid"] for item in preview["items"]] == ["older", "newer"]
    assert {item["cost_each"] for item in preview["items"]} == {200}


def test_grouped_preview_accepts_up_to_one_hundred_assets(tmp_path: Path) -> None:
    path = tmp_path / "large-grouped-listing.db"
    assets = tuple(
        InventoryAsset(
            "steam",
            730,
            "2",
            f"asset-{index}",
            "AK-47 | Slate",
            "AK-47 | Slate",
            "",
            "1",
            "0",
            True,
            True,
        )
        for index in range(100)
    )
    SqliteInventoryRepository(path).sync(assets)
    LedgerRepository(path).create_purchase("AK-47 | Slate", 100, 100, 1000, None, False)
    uow = SqliteScanUnitOfWork(path)
    snapshot = MarketSnapshot(
        "AK-47 | Slate",
        None,
        None,
        1000,
        None,
        "CNY",
        730,
        (MarketTier(MarketSide.STEAM_ASK, 200, 100),),
        "steam-cs2-cny-v1",
    )
    from skinflow_api.application.scan.models import ScanJob, ScanRequest

    job = ScanJob(ScanRequest("manual", 1, ("AK-47 | Slate",)))
    uow.create_job(job)
    uow.persist_result_and_event(job, snapshot, payload={"name": "AK-47 | Slate"})
    repository = SqliteListingRepository(path)
    service = ListingService(
        repository, repository, Gateway(ListingGatewayResult(True, False, "1", None))
    )

    preview = service.create_grouped_preview(
        (ListingGroupSelection("AK-47 | Slate", 100, 200),)
    )

    assert len(preview["items"]) == 100
    with pytest.raises(ValueError, match="between 1 and 100 assets"):
        service.create_grouped_preview(
            (ListingGroupSelection("AK-47 | Slate", 101, 200),)
        )


def test_listing_preview_route_accepts_one_hundred_asset_selections() -> None:
    request = PreviewRequest(
        items=[
            {
                "platform": "steam",
                "appid": 730,
                "contextid": "2",
                "assetid": f"asset-{index}",
            }
            for index in range(100)
        ]
    )

    assert len(request.items) == 100


def test_custom_group_price_updates_all_expanded_assets(tmp_path: Path) -> None:
    repository, assetid = _seed(tmp_path / "custom-price.db")
    service = ListingService(
        repository, repository, Gateway(ListingGatewayResult(True, False, "1", None))
    )

    preview = service.create_preview((ListingSelection("steam", 730, "2", assetid),))
    updated = service.update_preview_prices(preview["id"], {"AK-47 | Slate": 300})

    assert updated["items"][0]["buyer_pays"] == 300
    assert updated["items"][0]["seller_proceeds"] > 0


def test_custom_price_uses_nearest_reachable_steam_total(tmp_path: Path) -> None:
    repository, assetid = _seed(tmp_path / "custom-unreachable-price.db")
    service = ListingService(
        repository, repository, Gateway(ListingGatewayResult(True, False, "1", None))
    )

    preview = service.create_preview((ListingSelection("steam", 730, "2", assetid),))
    updated = service.update_preview_prices(preview["id"], {"AK-47 | Slate": 2_000})

    assert updated["items"][0]["buyer_pays"] == 1_998
    assert updated["items"][0]["seller_proceeds"] > 0
