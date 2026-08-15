from datetime import UTC, datetime

from skinflow_api.application.scan.models import AcquisitionPlatform
from skinflow_api.application.scan.ports import Candidate, MarketDataGateway, ScanEventSink
from skinflow_api.application.scan.upstream_errors import UpstreamUnavailable
from skinflow_api.domain.market.snapshot import MarketSnapshot
from skinflow_api.domain.pricing import steam_cny_policy
from skinflow_api.infrastructure.http.rate_limiter import PlatformRateLimiter

from .browser import EdgeYoupinBrowser
from .parser import parse_on_sale_response


class YoupinAdapter(MarketDataGateway):
    def __init__(
        self,
        browser: EdgeYoupinBrowser,
        limiter: PlatformRateLimiter | None = None,
    ) -> None:
        self._browser = browser
        self._limiter = limiter or PlatformRateLimiter("youpin", concurrency=2, max_attempts=1)

    def fetch_snapshot(
        self,
        candidate: Candidate,
        item_nameid: int,
        acquisition_platforms: tuple[AcquisitionPlatform, ...],
        event_sink: ScanEventSink | None = None,
    ) -> MarketSnapshot:
        del item_nameid, acquisition_platforms
        if candidate.youpin_goods_id < 1:
            raise UpstreamUnavailable("candidate has no youpin template id")
        payload = self._limiter.run(
            lambda: self._browser.fetch_listing_payload(candidate.youpin_goods_id),
            event_sink,
        )
        tiers = parse_on_sale_response(payload)
        if not tiers:
            raise UpstreamUnavailable("youpin returned no public listings")
        now = int(datetime.now(UTC).timestamp() * 1000)
        policy = steam_cny_policy()
        return MarketSnapshot(
            market_hash_name=candidate.market_hash_name,
            csqaq_observed_at=None,
            buff_observed_at=None,
            steam_observed_at=None,
            daily_volume_observed_at=None,
            currency="CNY",
            appid=730,
            tiers=tiers,
            fee_policy_version=policy.version,
            youpin_observed_at=now,
        )

    def close(self) -> None:
        self._browser.close()
