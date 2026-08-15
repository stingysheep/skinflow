from datetime import UTC, datetime

from skinflow_api.application.scan.models import AcquisitionPlatform
from skinflow_api.application.scan.ports import Candidate, MarketDataGateway, ScanEventSink
from skinflow_api.domain.market.snapshot import MarketSnapshot
from skinflow_api.domain.pricing import steam_cny_policy
from skinflow_api.infrastructure.http.client import HttpClient
from skinflow_api.infrastructure.http.rate_limiter import PlatformRateLimiter

from .parser import parse_histogram

BASE_URL = "https://steamcommunity.com/market/itemordershistogram"


class SteamAdapter(MarketDataGateway):
    def __init__(
        self,
        client: HttpClient | None = None,
        limiter: PlatformRateLimiter | None = None,
    ) -> None:
        self._client = client or HttpClient()
        self._limiter = limiter or PlatformRateLimiter("steam", concurrency=4)

    def fetch_snapshot(
        self,
        candidate: Candidate,
        item_nameid: int,
        acquisition_platforms: tuple[AcquisitionPlatform, ...],
        event_sink: ScanEventSink | None = None,
    ) -> MarketSnapshot:
        del acquisition_platforms
        url = (
            f"{BASE_URL}?country=CN&language=schinese&currency=23"
            f"&item_nameid={item_nameid}&norender=1"
        )
        data = self._limiter.run(lambda: self._client.request_json(url), event_sink)
        now = int(datetime.now(UTC).timestamp() * 1000)
        policy = steam_cny_policy()
        return MarketSnapshot(
            candidate.market_hash_name,
            None,
            None,
            now,
            None,
            "CNY",
            730,
            parse_histogram(data),
            policy.version,
            daily_volume=candidate.daily_volume,
            steam_median_price=candidate.steam_transaction_price,
        )
