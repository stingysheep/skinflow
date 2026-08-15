"""Read-only live smoke check for anonymous CS2 market sources."""

from __future__ import annotations

import os
import time

from skinflow_api.application.scan.models import AcquisitionPlatform, ScanRequest
from skinflow_api.domain.market.tiers import MarketSide
from skinflow_api.infrastructure.platforms.buff.adapter import BuffAdapter
from skinflow_api.infrastructure.platforms.csqaq.adapter import CsqaqAdapter
from skinflow_api.infrastructure.platforms.market_gateway import CompositeMarketGateway
from skinflow_api.infrastructure.platforms.steam.adapter import SteamAdapter
from skinflow_api.infrastructure.platforms.steam.nameid_resolver import JsonNameIdResolver
from skinflow_api.infrastructure.platforms.youpin import EdgeYoupinBrowser, YoupinAdapter


def main() -> int:
    token = os.environ.get("SKINFLOW_CSQAQ_API_TOKEN", "").strip()
    if not token:
        print("SKIP: csqaq token is not configured")
        return 2
    request = ScanRequest(
        "csqaq",
        20,
        acquisition_platforms=(AcquisitionPlatform.BUFF, AcquisitionPlatform.YOUPIN),
    )
    candidates = CsqaqAdapter(token).list_candidates(request)
    resolver = JsonNameIdResolver("data/cs2_nameids.json")
    candidate = next(
        (item for item in candidates if resolver.resolve(item.market_hash_name) is not None),
        None,
    )
    if candidate is None:
        print("FAIL: no candidate has a Steam item_nameid")
        return 1
    browser = EdgeYoupinBrowser(idle_seconds=1)
    events: list[tuple[str, dict]] = []
    gateway = CompositeMarketGateway(BuffAdapter(), YoupinAdapter(browser), SteamAdapter())
    started = time.perf_counter()
    try:
        snapshot = gateway.fetch_snapshot(
            candidate,
            resolver.resolve(candidate.market_hash_name) or 0,
            request.acquisition_platforms,
            lambda event_type, payload: events.append((event_type, payload)),
        )
    finally:
        browser.close()
    counts = {
        side.value: sum(tier.quantity for tier in snapshot.for_side(side))
        for side in MarketSide
    }
    print(
        {
            "name": candidate.name,
            "market_hash_name": candidate.market_hash_name,
            "tiers": counts,
            "daily_volume": snapshot.daily_volume,
            "elapsed_seconds": round(time.perf_counter() - started, 2),
            "events": events,
        }
    )
    required = {"buff_ask", "youpin_ask", "steam_bid", "steam_ask"}
    return 0 if all(counts.get(side, 0) > 0 for side in required) else 1


if __name__ == "__main__":
    raise SystemExit(main())
