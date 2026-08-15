from __future__ import annotations

from skinflow_api.application.listing.models import ListingContext, ListingMarketSnapshot
from skinflow_api.application.listing.ports import ListingSnapshotStore
from skinflow_api.application.scan.models import AcquisitionPlatform, ScanRequest
from skinflow_api.application.scan.ports import Candidate
from skinflow_api.domain.market.tiers import MarketSide
from skinflow_api.infrastructure.platforms.csqaq.adapter import CsqaqAdapter

from .adapter import SteamAdapter
from .nameid_resolver import JsonNameIdResolver


class SteamListingMarketSnapshotProvider:
    """Fetch and persist one anonymous Steam order book for listing preview."""

    def __init__(
        self,
        resolver: JsonNameIdResolver,
        steam: SteamAdapter,
        store: ListingSnapshotStore,
        csqaq: CsqaqAdapter | None = None,
    ) -> None:
        self._resolver = resolver
        self._steam = steam
        self._store = store
        self._csqaq = csqaq

    def refresh_trend(self, market_hash_name: str) -> None:
        if self._csqaq is None:
            return
        candidates = self._csqaq.list_candidates(
            ScanRequest(
                source_mode="manual",
                candidate_limit=1,
                manual_names=(market_hash_name,),
                acquisition_platforms=(AcquisitionPlatform.BUFF, AcquisitionPlatform.YOUPIN),
            )
        )
        if not candidates:
            return
        points = self._csqaq.fetch_chart(candidates[0].good_id, platform=3)
        if points and hasattr(self._store, "save_market_trend"):
            self._store.save_market_trend(market_hash_name, candidates[0].good_id, points)

    def fetch(self, context: ListingContext) -> ListingMarketSnapshot:
        item_nameid = self._resolver.resolve(context.asset.market_hash_name)
        if item_nameid is None:
            raise RuntimeError("STEAM_NAMEID_UNRESOLVED")
        candidate = Candidate(
            market_hash_name=context.asset.market_hash_name,
            name=context.asset.display_name,
            image_url=context.asset.image_url,
            buff_goods_id=0,
            good_id=0,
        )
        snapshot = self._steam.fetch_snapshot(candidate, item_nameid, ())
        if snapshot.appid != 730 or snapshot.currency != "CNY":
            raise RuntimeError("STEAM_UNSUPPORTED_MARKET")
        asks = snapshot.for_side(MarketSide.STEAM_ASK)
        if not asks:
            raise RuntimeError("STEAM_ORDERBOOK_EMPTY")
        snapshot_id, job_id = self._store.save_listing_snapshot(snapshot)
        return ListingMarketSnapshot(snapshot, snapshot_id, job_id, asks)
