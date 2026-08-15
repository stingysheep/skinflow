from datetime import UTC, datetime

from skinflow_api.application.scan.models import AcquisitionPlatform
from skinflow_api.application.scan.ports import Candidate, MarketDataGateway, ScanEventSink
from skinflow_api.application.scan.upstream_errors import UpstreamUnavailable
from skinflow_api.domain.market.snapshot import MarketSnapshot
from skinflow_api.domain.market.tiers import MarketSide, MarketTier
from skinflow_api.domain.pricing import steam_cny_policy
from skinflow_api.infrastructure.http.client import HttpClient
from skinflow_api.infrastructure.http.rate_limiter import PlatformRateLimiter

from .parser import parse_sell_orders

BASE_URL = "https://buff.163.com/api/market/goods/sell_order"


class BuffAdapter(MarketDataGateway):
    def __init__(
        self,
        client: HttpClient | None = None,
        limiter: PlatformRateLimiter | None = None,
    ) -> None:
        self._client = client or HttpClient()
        self._limiter = limiter or PlatformRateLimiter(
            "buff", concurrency=2, min_interval_seconds=0.5
        )

    def fetch_snapshot(
        self,
        candidate: Candidate,
        item_nameid: int,
        acquisition_platforms: tuple[AcquisitionPlatform, ...],
        event_sink: ScanEventSink | None = None,
    ) -> MarketSnapshot:
        del item_nameid, acquisition_platforms
        if candidate.buff_goods_id < 1:
            raise UpstreamUnavailable("candidate has no BUFF goods id")
        payload = self._limiter.run(
            lambda: self._client.request_json(
                f"{BASE_URL}?game=csgo&goods_id={candidate.buff_goods_id}"
                "&page_num=1&sort_by=default",
                headers={
                    "Referer": "https://buff.163.com/market/csgo",
                    "X-Requested-With": "XMLHttpRequest",
                },
            ),
            event_sink,
        )
        now = int(datetime.now(UTC).timestamp() * 1000)
        data = payload.get("data") or {}
        tiers = parse_sell_orders(data.get("items") or ())
        if not tiers:
            raise UpstreamUnavailable("BUFF returned no public listings")
        policy = steam_cny_policy()
        return MarketSnapshot(
            candidate.market_hash_name, None, now, None, None, "CNY", 730,
            tuple(MarketTier(MarketSide.BUFF_ASK, tier.price, tier.quantity) for tier in tiers),
            policy.version,
        )
