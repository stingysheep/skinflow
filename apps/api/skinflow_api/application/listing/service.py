from __future__ import annotations

import time
from contextlib import suppress
from dataclasses import replace
from threading import Thread

from skinflow_api.domain.listing import ListingDecision
from skinflow_api.domain.listing.errors import InvalidListing
from skinflow_api.domain.pricing import (
    FeeBreakdown,
    Tier,
    calculate_net,
    receive_to_pays,
    recommend_listing_price,
    steam_cny_policy,
)

from .models import MAX_LISTING_PREVIEW_ASSETS, ListingGroupSelection, ListingSelection
from .ports import ListingCatalog, ListingGateway, ListingMarketSnapshotProvider, ListingPersistence


class ListingService:
    def __init__(
        self,
        catalog: ListingCatalog,
        persistence: ListingPersistence,
        gateway: ListingGateway,
        market_snapshot_provider: ListingMarketSnapshotProvider | None = None,
    ) -> None:
        self._catalog = catalog
        self._persistence = persistence
        self._gateway = gateway
        self._market_snapshot_provider = market_snapshot_provider

    def create_preview(self, selections: tuple[ListingSelection, ...]) -> dict:
        if not 1 <= len(selections) <= MAX_LISTING_PREVIEW_ASSETS:
            raise InvalidListing(
                f"a preview must contain between 1 and {MAX_LISTING_PREVIEW_ASSETS} assets"
            )
        identities = {
            (item.platform, item.appid, item.contextid, item.assetid) for item in selections
        }
        if len(identities) != len(selections):
            raise InvalidListing("duplicate assets are not allowed")
        decisions = tuple(self._decision(selection) for selection in selections)
        return self._persistence.create_preview(decisions, int(time.time() * 1000) + 300_000)

    def create_grouped_preview(
        self, selections: tuple[ListingGroupSelection, ...]
    ) -> dict:
        if not 1 <= len(selections) <= MAX_LISTING_PREVIEW_ASSETS:
            raise InvalidListing(
                "a preview must contain between 1 and "
                f"{MAX_LISTING_PREVIEW_ASSETS} item groups"
            )
        names = [item.market_hash_name.strip() for item in selections]
        if any(not name for name in names) or len(set(names)) != len(names):
            raise InvalidListing("duplicate or empty item groups are not allowed")
        expanded: list[ListingSelection] = []
        for item, name in zip(selections, names, strict=True):
            if item.quantity < 1:
                raise InvalidListing("group quantity must be positive")
            if len(expanded) + item.quantity > MAX_LISTING_PREVIEW_ASSETS:
                raise InvalidListing(
                    "a preview must contain between 1 and "
                    f"{MAX_LISTING_PREVIEW_ASSETS} assets"
                )
            normalized = ListingGroupSelection(name, item.quantity, item.buyer_pays)
            contexts = self._catalog.contexts_for_group(normalized)
            if len(contexts) < item.quantity:
                raise InvalidListing(
                    f"insufficient tradable inventory for {name}: {len(contexts)} available"
                )
            average_cost = self._catalog.average_cost_for_group(name)
            for context in contexts[: item.quantity]:
                expanded.append(
                    ListingSelection(
                        context.asset.platform,
                        context.asset.appid,
                        context.asset.contextid,
                        context.asset.assetid,
                        item.buyer_pays,
                        average_cost,
                    )
                )
        return self.create_preview(tuple(expanded))

    def update_preview_prices(self, preview_id: str, prices: dict[str, int]) -> dict:
        preview = self._persistence.get_preview(preview_id)
        if preview is None:
            raise LookupError("listing preview not found")
        if preview["status"] != "ready" or preview["expires_at"] < int(time.time() * 1000):
            raise InvalidListing("listing preview expired or is not ready")
        normalized = {name.strip(): int(price) for name, price in prices.items() if name.strip()}
        if any(price < 1 for price in normalized.values()):
            raise InvalidListing("listing price must be positive")
        policy = steam_cny_policy()
        updates: list[dict] = []
        for item in preview["items"]:
            if item["market_hash_name"] not in normalized:
                continue
            buyer_pays = normalized[item["market_hash_name"]]
            fees = _fee_breakdown_for_buyer_pays(buyer_pays, policy)
            cost_each = item["cost_each"]
            ratio = (
                cost_each * 1_000_000 // fees.seller_proceeds
                if cost_each is not None and fees.seller_proceeds > 0
                else None
            )
            updates.append(
                {
                    "assetid": item["assetid"],
                    "buyer_pays": fees.buyer_pays,
                    "steam_fee": fees.steam_fee,
                    "publisher_fee": fees.publisher_fee,
                    "seller_proceeds": fees.seller_proceeds,
                    "ratio_ppm": ratio,
                }
            )
        if not updates and normalized:
            raise InvalidListing("no matching preview item for custom price")
        self._persistence.update_preview_items(preview_id, tuple(updates))
        return self._persistence.get_preview(preview_id) or {}

    def submit(
        self, preview_id: str, idempotency_key: str, prices: dict[str, int] | None = None
    ) -> dict:
        if not idempotency_key or len(idempotency_key) > 100:
            raise InvalidListing("idempotency key is required")
        preview = self._persistence.get_preview(preview_id)
        if preview is None:
            raise LookupError("listing preview not found")
        if preview["status"] != "ready" or preview["expires_at"] < int(time.time() * 1000):
            raise InvalidListing("listing preview expired or is not ready")
        if prices:
            self.update_preview_prices(preview_id, prices)
            preview = self._persistence.get_preview(preview_id) or preview
        request = self._persistence.create_request(preview_id, idempotency_key)
        if request.get("replayed"):
            return request
        for item in preview["items"]:
            try:
                result = self._gateway.submit(item)
            except PermissionError:
                raise
            except Exception as error:
                result = self._uncertain_result(type(error).__name__)
            self._persistence.record_result(request["id"], item, result)
        return self._persistence.complete_request(request["id"])

    def get_request(self, request_id: str) -> dict:
        request = self._persistence.get_request(request_id)
        if request is None:
            raise LookupError("listing request not found")
        return request

    def list_requests(self) -> list[dict]:
        return self._persistence.list_requests()

    def cancel_items(self, item_ids: tuple[str, ...]) -> dict:
        if not item_ids or len(item_ids) > 100:
            raise InvalidListing("select between 1 and 100 listing items")
        cancel = getattr(self._gateway, "cancel", None)
        if cancel is None:
            raise InvalidListing("Steam cancellation is unavailable")
        rows = self._persistence.list_cancellable_items(tuple(dict.fromkeys(item_ids)))
        results: list[dict] = []
        for item in rows:
            listing_id = str(item.get("steam_listing_id") or "")
            if not listing_id:
                results.append(
                    {"id": item["id"], "status": "failed", "message": "STEAM_LISTING_ID_MISSING"}
                )
                continue
            try:
                accepted = bool(cancel(listing_id))
            except Exception as error:
                results.append(
                    {"id": item["id"], "status": "failed", "message": type(error).__name__}
                )
                continue
            if accepted:
                self._persistence.mark_cancelled(item["id"], int(time.time() * 1000))
                results.append({"id": item["id"], "status": "cancelled", "message": None})
            else:
                results.append(
                    {"id": item["id"], "status": "failed", "message": "STEAM_CANCEL_REJECTED"}
                )
        selected = {item["id"] for item in rows}
        for item_id in item_ids:
            if item_id not in selected:
                results.append(
                    {"id": item_id, "status": "failed", "message": "LISTING_NOT_CANCELLABLE"}
                )
        return {"items": results}

    def _decision(self, selection: ListingSelection) -> ListingDecision:
        context = self._catalog.context_for(selection)
        if context is None:
            raise InvalidListing(f"asset {selection.assetid} is not available")
        if not context.asset.marketable:
            raise InvalidListing(f"asset {selection.assetid} is not marketable")
        if context.active_listing:
            raise InvalidListing(f"asset {selection.assetid} already has an active listing")
        refresh_trend = getattr(self._market_snapshot_provider, "refresh_trend", None)
        if refresh_trend is not None:
            # Trend history is advisory. Run the potentially slow upstream
            # refresh in the background so preview latency is bounded by the
            # live Steam order-book request instead.
            Thread(
                target=self._refresh_trend,
                args=(refresh_trend, context.asset.market_hash_name),
                daemon=True,
                name="skinflow-listing-trend",
            ).start()
        if context.snapshot_id is None or context.snapshot_job_id is None or not context.asks:
            if self._market_snapshot_provider is None:
                raise InvalidListing("STEAM_SNAPSHOT_REQUIRED")
            try:
                market = self._market_snapshot_provider.fetch(context)
            except Exception as error:
                raise InvalidListing("STEAM_SNAPSHOT_UNAVAILABLE") from error
            context = replace(
                context,
                snapshot_id=market.snapshot_id,
                snapshot_job_id=market.snapshot_job_id,
                asks=market.asks,
            )
        if not context.asks:
            raise InvalidListing("STEAM_SNAPSHOT_UNAVAILABLE")
        policy = steam_cny_policy()
        buyer_pays = selection.buyer_pays or recommend_listing_price(
            lowest_ask=context.asks[0].price,
            price_tick=1,
            fee_policy=policy,
            requested_qty=1,
            ask_levels=tuple(Tier(item.price, item.quantity) for item in context.asks),
            min_price=1,
            daily_volume=None,
        ).recommended_price
        fees = calculate_net(buyer_pays, policy)
        cost_each = selection.cost_each if selection.cost_each is not None else context.cost_each
        ratio = (
            cost_each * 1_000_000 // fees.seller_proceeds
            if cost_each is not None and fees.seller_proceeds > 0
            else None
        )
        return ListingDecision(
            context.asset.platform,
            context.asset.appid,
            context.asset.contextid,
            context.asset.assetid,
            context.asset.market_hash_name,
            context.snapshot_id,
            context.snapshot_job_id,
            buyer_pays,
            fees.steam_fee,
            fees.publisher_fee,
            fees.seller_proceeds,
            cost_each,
            ratio,
            policy.version,
        )

    @staticmethod
    def _refresh_trend(refresh_trend, market_hash_name: str) -> None:
        with suppress(Exception):
            refresh_trend(market_hash_name)

    @staticmethod
    def _uncertain_result(message: str):
        from .models import ListingGatewayResult

        return ListingGatewayResult(False, False, None, f"uncertain:{message}")


def _fee_breakdown_for_buyer_pays(buyer_pays: int, policy) -> FeeBreakdown:
    try:
        return calculate_net(buyer_pays, policy)
    except ValueError:
        # Steam prices have small gaps caused by the minimum fee rounding. Use
        # the nearest reachable price below the user's target instead of
        # dropping all preview calculations for values such as 20.00 yuan.
        lower: FeeBreakdown | None = None
        low, high = 1, buyer_pays
        while low <= high:
            receive = (low + high) // 2
            candidate = receive_to_pays(receive, policy)
            if candidate.buyer_pays <= buyer_pays:
                lower = candidate
                low = receive + 1
            else:
                high = receive - 1
        if lower is None:
            raise
        return lower
