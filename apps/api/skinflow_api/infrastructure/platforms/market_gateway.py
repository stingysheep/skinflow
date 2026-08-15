from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from skinflow_api.application.scan.models import AcquisitionPlatform
from skinflow_api.application.scan.ports import Candidate, MarketDataGateway, ScanEventSink
from skinflow_api.application.scan.upstream_errors import UpstreamError, UpstreamUnavailable
from skinflow_api.domain.market.snapshot import MarketSnapshot
from skinflow_api.domain.market.tiers import MarketSide


class CompositeMarketGateway(MarketDataGateway):
    def __init__(
        self,
        buff: MarketDataGateway,
        youpin: MarketDataGateway,
        steam: MarketDataGateway,
    ) -> None:
        self._buff = buff
        self._youpin = youpin
        self._steam = steam

    def fetch_snapshot(
        self,
        candidate: Candidate,
        item_nameid: int,
        acquisition_platforms: tuple[AcquisitionPlatform, ...],
        event_sink: ScanEventSink | None = None,
    ) -> MarketSnapshot:
        adapters: dict[str, MarketDataGateway] = {"steam": self._steam}
        if AcquisitionPlatform.BUFF in acquisition_platforms:
            adapters["buff"] = self._buff
        if AcquisitionPlatform.YOUPIN in acquisition_platforms:
            adapters["youpin"] = self._youpin
        snapshots: dict[str, MarketSnapshot] = {}
        failures: dict[str, UpstreamError] = {}
        with ThreadPoolExecutor(max_workers=len(adapters)) as executor:
            futures = {
                executor.submit(
                    adapter.fetch_snapshot,
                    candidate,
                    item_nameid,
                    acquisition_platforms,
                    event_sink,
                ): platform
                for platform, adapter in adapters.items()
            }
            for future, platform in ((future, futures[future]) for future in futures):
                try:
                    snapshots[platform] = future.result()
                except UpstreamError as error:
                    failures[platform] = error

        if "steam" not in snapshots:
            raise failures.get("steam", UpstreamUnavailable("Steam data unavailable"))
        source_snapshots = [
            snapshots[platform]
            for platform in ("buff", "youpin")
            if platform in snapshots
        ]
        if not source_snapshots:
            error = next(iter(failures.values()), UpstreamUnavailable("source data unavailable"))
            raise error
        for platform, error in failures.items():
            if event_sink is not None:
                event_sink(
                    "candidate.source_unavailable",
                    {
                        "market_hash_name": candidate.market_hash_name,
                        "platform": platform,
                        "reason_code": error.code,
                    },
                )

        steam_snapshot = snapshots["steam"]
        tiers = tuple(tier for snapshot in source_snapshots for tier in snapshot.tiers) + tuple(
            tier
            for tier in steam_snapshot.tiers
            if tier.side in {MarketSide.STEAM_BID, MarketSide.STEAM_ASK}
        )
        return MarketSnapshot(
            market_hash_name=candidate.market_hash_name,
            csqaq_observed_at=int(datetime.now(UTC).timestamp() * 1000),
            buff_observed_at=(
                snapshots.get("buff").buff_observed_at if "buff" in snapshots else None
            ),
            steam_observed_at=steam_snapshot.steam_observed_at,
            daily_volume_observed_at=None,
            currency=steam_snapshot.currency,
            appid=steam_snapshot.appid,
            tiers=tiers,
            fee_policy_version=steam_snapshot.fee_policy_version,
            youpin_observed_at=(
                snapshots.get("youpin").youpin_observed_at if "youpin" in snapshots else None
            ),
            daily_volume=steam_snapshot.daily_volume,
            steam_median_price=steam_snapshot.steam_median_price,
        )
