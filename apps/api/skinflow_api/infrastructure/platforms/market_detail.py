from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from skinflow_api.application.inventory.ports import MarketDetailProvider
from skinflow_api.application.scan.models import AcquisitionPlatform, ScanRequest
from skinflow_api.application.scan.ports import Candidate
from skinflow_api.infrastructure.database.listing import SqliteListingRepository
from skinflow_api.infrastructure.platforms.csqaq.adapter import CsqaqAdapter
from skinflow_api.infrastructure.platforms.steam.adapter import SteamAdapter
from skinflow_api.infrastructure.platforms.steam.nameid_resolver import JsonNameIdResolver


class CsqaqMarketDetailProvider(MarketDetailProvider):
    def __init__(
        self,
        csqaq: CsqaqAdapter,
        resolver: JsonNameIdResolver,
        steam: SteamAdapter,
        store: SqliteListingRepository,
    ) -> None:
        self._csqaq = csqaq
        self._resolver = resolver
        self._steam = steam
        self._store = store

    def refresh(self, market_hash_name: str) -> bool:
        cached_trend = self._store.read_market_trend(market_hash_name)
        cached_good_id = getattr(self._store, "read_csqaq_good_id", lambda _name: None)(market_hash_name)
        localized_name = getattr(self._store, "read_localized_name", lambda _name: None)(market_hash_name)
        try:
            if cached_good_id:
                candidates = ()
            elif localized_name and hasattr(self._csqaq, "lookup_candidate"):
                direct = self._csqaq.lookup_candidate(market_hash_name, search_text=localized_name)
                candidates = (direct,) if direct else ()
            else:
                candidates = self._csqaq.list_candidates(
                    ScanRequest(
                        source_mode="manual",
                        candidate_limit=1,
                        manual_names=(market_hash_name,),
                        acquisition_platforms=(AcquisitionPlatform.BUFF, AcquisitionPlatform.YOUPIN),
                    )
                )
        except Exception:
            return False
        candidate = candidates[0] if candidates else Candidate(
            market_hash_name=market_hash_name,
            name=market_hash_name,
            image_url="",
            buff_goods_id=0,
            good_id=cached_good_id or 0,
        )
        chart_loaded = bool(cached_trend)
        if candidate.good_id > 0 and not cached_trend:
            try:
                points = self._csqaq.fetch_chart(candidate.good_id, platform=3)
            except Exception:
                points = ()
        else:
            points = ()
        if points:
            self._store.save_market_trend(market_hash_name, candidate.good_id, points)
            chart_loaded = True
        item_nameid = self._resolver.resolve(market_hash_name)
        if item_nameid is None:
            return chart_loaded
        snapshot = self._steam.fetch_snapshot(candidate, item_nameid, ())
        snapshot = replace(snapshot, csqaq_observed_at=int(datetime.now(UTC).timestamp() * 1000))
        self._store.save_listing_snapshot(snapshot)
        return True
