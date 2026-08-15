import logging
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from skinflow_api.domain.market.snapshot import MarketSnapshot
from skinflow_api.domain.market.tiers import MarketSide, MarketTier
from skinflow_api.domain.pricing import (
    Tier,
    build_price_curves,
    recommend_listing_price,
    steam_cny_policy,
)
from skinflow_api.domain.pricing.fee_calculator import calculate_net
from skinflow_api.domain.pricing.errors import BelowMinimumPrice, NegativeProceeds, UnreachablePrice

from .errors import ScanConfigurationError
from .models import AcquisitionPlatform, ScanJob, ScanRequest, ScanStatus
from .ports import (
    Candidate,
    CandidateSource,
    MarketDataGateway,
    NameIdResolver,
    ScanPersistenceUnitOfWork,
)
from .upstream_errors import UpstreamError

LOGGER = logging.getLogger(__name__)


class ScanService:
    def __init__(
        self,
        persistence: ScanPersistenceUnitOfWork,
        candidates: CandidateSource,
        nameids: NameIdResolver,
        market: MarketDataGateway,
    ) -> None:
        self._persistence = persistence
        self._candidates = candidates
        self._nameids = nameids
        self._market = market

    def create(self, request: ScanRequest) -> ScanJob:
        if self._persistence.has_active_job():
            raise ValueError("an active scan already exists")
        job = ScanJob(request=request)
        self._persistence.create_job(job)
        return job

    def run(self, job_id: str) -> ScanJob:
        job = self._require(job_id)
        if job.status != ScanStatus.QUEUED:
            return job
        job.transition(ScanStatus.RUNNING)
        self._persistence.append_event(job, "job.started")
        try:
            candidates = self._candidates.list_candidates(
                job.request,
                self._event_sink(job_id),
            )
            cancelled = self._run_candidates(job_id, tuple(candidates))
            if cancelled:
                return self._cancel_running(self._require(job_id))
        except Exception as error:
            LOGGER.error("scan job %s failed with %s", job_id, type(error).__name__)
            return self._fail(job_id, self._failure_code(error))

        current = self._require(job_id)
        if current.status == ScanStatus.CANCELLING:
            return self._cancel_running(current)
        current.transition(ScanStatus.SUCCEEDED)
        self._persistence.append_event(current, "job.succeeded")
        return current

    def cancel(self, job_id: str) -> ScanJob:
        job = self._require(job_id)
        if job.status == ScanStatus.QUEUED:
            job.transition(ScanStatus.CANCELLED)
            self._persistence.append_event(job, "job.cancelled")
        elif job.status == ScanStatus.RUNNING:
            job.transition(ScanStatus.CANCELLING)
            self._persistence.append_event(job, "job.cancelling")
        return job

    def get(self, job_id: str) -> ScanJob | None:
        return self._persistence.get_job(job_id)

    def events(self, job_id: str, after: int = 0) -> list[dict]:
        return self._persistence.list_events(job_id, after)

    def results(self, job_id: str) -> list[dict]:
        self._require(job_id)
        return self._persistence.list_results(job_id)

    def charts(
        self, job_id: str, market_hash_name: str, platforms: tuple[str, ...]
    ) -> dict[str, tuple[dict, ...]]:
        """Fetch CSQAQ history when a result row is opened, not for every scan row."""
        self._require(job_id)
        result = next(
            (item for item in self._persistence.list_results(job_id)
             if item.get("market_hash_name") == market_hash_name),
            None,
        )
        if result is None:
            raise LookupError(market_hash_name)
        fetch_chart = getattr(self._candidates, "fetch_chart", None)
        good_id = int(result.get("good_id") or 0)
        if not callable(fetch_chart) or good_id < 1:
            return {platform: () for platform in platforms}
        platform_codes = {"buff": 1, "youpin": 2, "steam": 3}
        loaded: dict[str, tuple[dict, ...]] = {}
        for platform in platforms:
            code = platform_codes.get(platform)
            if code is None:
                continue
            try:
                loaded[platform] = tuple(
                    fetch_chart(good_id, platform=code, event_sink=self._event_sink(job_id))
                )
            except UpstreamError as error:
                LOGGER.warning(
                    "chart unavailable for %s/%s: %s", market_hash_name, platform, error.code
                )
                loaded[platform] = ()
            except Exception:
                LOGGER.exception("chart request failed for %s/%s", market_hash_name, platform)
                loaded[platform] = ()
        return loaded

    def _cancel_running(self, job: ScanJob) -> ScanJob:
        job.transition(ScanStatus.CANCELLED)
        self._persistence.append_event(job, "job.cancelled")
        return job

    def _fail(self, job_id: str, failure_code: str) -> ScanJob:
        job = self._require(job_id)
        if job.status == ScanStatus.CANCELLING:
            return self._cancel_running(job)
        if job.status == ScanStatus.RUNNING:
            job.transition(ScanStatus.FAILED, failure_code)
            self._persistence.append_event(
                job,
                "job.failed",
                {"reason_code": failure_code},
            )
        return job

    @staticmethod
    def _failure_code(error: Exception) -> str:
        if isinstance(error, ScanConfigurationError):
            return error.code
        if isinstance(error, UpstreamError):
            return error.code
        return "SCAN_UNEXPECTED_ERROR"

    def _curves(self, snapshot: MarketSnapshot, recommended_price: int | None = None):
        policy = steam_cny_policy(snapshot.appid, snapshot.currency)
        acquisition = tuple(
            Tier(tier.price, tier.quantity)
            for tier in snapshot.tiers
            if tier.side == self._acquisition_side(snapshot)
        )
        bids = tuple(
            Tier(tier.price, tier.quantity)
            for tier in snapshot.tiers
            if tier.side == MarketSide.STEAM_BID
        )
        asks = tuple(
            Tier(tier.price, tier.quantity)
            for tier in snapshot.tiers
            if tier.side == MarketSide.STEAM_ASK
        )
        return build_price_curves(
            acquisition, bids, asks, policy, recommended_price=recommended_price, limit=10
        )

    def _result_payload(
        self,
        candidate,
        snapshot,
        curves,
        recommendation: dict,
        trend: tuple[dict, ...] = (),
    ) -> dict:
        buff = [tier for tier in snapshot.tiers if tier.side == MarketSide.BUFF_ASK]
        youpin = [tier for tier in snapshot.tiers if tier.side == MarketSide.YOUPIN_ASK]
        bids = [tier for tier in snapshot.tiers if tier.side == MarketSide.STEAM_BID]
        asks = [tier for tier in snapshot.tiers if tier.side == MarketSide.STEAM_ASK]
        acquisition_side = self._acquisition_side(snapshot)
        acquisition = buff if acquisition_side == MarketSide.BUFF_ASK else youpin
        acquisition_platform = (
            AcquisitionPlatform.BUFF
            if acquisition_side == MarketSide.BUFF_ASK
            else AcquisitionPlatform.YOUPIN
        )
        bid_seller_proceeds = None
        if bids:
            try:
                bid_seller_proceeds = calculate_net(
                    bids[0].price, steam_cny_policy(snapshot.appid, snapshot.currency)
                ).seller_proceeds
            except (ValueError, BelowMinimumPrice, NegativeProceeds, UnreachablePrice):
                bid_seller_proceeds = None
        return {
            "market_hash_name": candidate.market_hash_name,
            "name": candidate.name,
            "image_url": candidate.image_url,
            "good_id": candidate.good_id,
            "csqaq_url": candidate.csqaq_url,
            "buff_goods_id": candidate.buff_goods_id,
            "youpin_goods_id": candidate.youpin_goods_id,
            "acquisition_platform": acquisition_platform,
            "acquisition_lowest_ask": acquisition[0].price if acquisition else None,
            "buff_lowest_ask": buff[0].price if buff else None,
            "youpin_lowest_ask": youpin[0].price if youpin else None,
            "steam_highest_bid": bids[0].price if bids else None,
            "steam_lowest_ask": asks[0].price if asks else None,
            "steam_transaction_price": snapshot.steam_median_price,
            "steam_bid_seller_proceeds": bid_seller_proceeds,
            "buff_observed_at": snapshot.buff_observed_at,
            "youpin_observed_at": snapshot.youpin_observed_at,
            "steam_observed_at": snapshot.steam_observed_at,
            "daily_volume": snapshot.daily_volume,
            "fee_policy_version": snapshot.fee_policy_version,
            "buff_depth": sum(tier.quantity for tier in buff[:10]),
            "youpin_depth": sum(tier.quantity for tier in youpin[:10]),
            "steam_bid_depth": sum(tier.quantity for tier in bids[:10]),
            "steam_ask_depth": sum(tier.quantity for tier in asks[:10]),
            "steam_ask_levels": [
                {"price": tier.price, "quantity": tier.quantity} for tier in asks[:10]
            ],
            "steam_bid_levels": [
                {"price": tier.price, "quantity": tier.quantity} for tier in bids[:10]
            ],
            "steam_trend": [
                {
                    "observed_at": point.get("observed_at"),
                    "price": point.get("value"),
                    "quantity": point.get("quantity"),
                }
                for point in trend
                if point.get("observed_at") is not None and point.get("value") is not None
            ],
            **recommendation,
            "curves": [
                {
                    "quantity": point.quantity,
                    "cost_total": point.cost_total,
                    "immediate_ratio_ppm": point.immediate_ratio_ppm,
                    "recommended_ratio_ppm": point.recommended_ratio_ppm,
                    "market_ask_ratio_ppm": point.market_ask_ratio_ppm,
                }
                for point in curves
            ],
        }

    def _run_candidates(self, job_id: str, candidates: tuple[Candidate, ...]) -> bool:
        executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="skinflow-scan")
        futures: dict[Future[tuple], Candidate] = {}
        candidate_iter = iter(candidates)
        accepted = 0
        stop_submitting = False
        cancelled = False

        def persist_partial(candidate: Candidate, reason_code: str) -> bool:
            nonlocal accepted
            current = self._require(job_id)
            snapshot = self._partial_snapshot(candidate, current.request)
            if snapshot is None:
                self._reject(job_id, candidate, reason_code)
                return False
            curves = self._curves(snapshot)
            payload = self._result_payload(
                candidate,
                snapshot,
                curves,
                self._recommendation(snapshot),
            )
            payload["job_id"] = job_id
            payload.update({
                "data_incomplete": True,
                "unavailable_reason": reason_code,
            })
            accepted += 1
            current.result_count += 1
            self._persistence.persist_result_and_event(
                current,
                snapshot,
                curves,
                payload=payload,
            )
            return True

        def submit_available() -> None:
            nonlocal stop_submitting
            target = self._require(job_id).request.candidate_limit
            while not stop_submitting and len(futures) < 4 and accepted < target:
                try:
                    candidate = next(candidate_iter)
                except StopIteration:
                    stop_submitting = True
                    return
                item_nameid = self._nameids.resolve(candidate.market_hash_name)
                if item_nameid is None:
                    persist_partial(candidate, "STEAM_NAMEID_UNRESOLVED")
                    continue
                futures[executor.submit(self._analyze_candidate, job_id, candidate, item_nameid)] = candidate

        try:
            submit_available()
            while futures:
                future = next(as_completed(tuple(futures)))
                current = self._require(job_id)
                if current.status == ScanStatus.CANCELLING:
                    cancelled = True
                    break
                candidate = futures.pop(future)
                try:
                    snapshot, curves, payload = future.result()
                except UpstreamError as error:
                    persist_partial(candidate, error.code)
                    submit_available()
                    continue
                if not self._matches_actual_filters(current.request, snapshot):
                    payload["data_incomplete"] = True
                    payload["unavailable_reason"] = "SCAN_FILTERED_OUT"
                    accepted += 1
                    current.result_count += 1
                    self._persistence.persist_result_and_event(
                        current, snapshot, curves, payload=payload
                    )
                    submit_available()
                    continue
                accepted += 1
                current.result_count += 1
                self._persistence.persist_result_and_event(
                    current,
                    snapshot,
                    curves,
                    payload=payload,
                )
                if accepted >= current.request.candidate_limit:
                    stop_submitting = True
                    break
                else:
                    submit_available()
        finally:
            executor.shutdown(
                wait=not cancelled,
                cancel_futures=cancelled or stop_submitting,
            )
        return cancelled

    @staticmethod
    def _partial_snapshot(candidate: Candidate, request: ScanRequest) -> MarketSnapshot | None:
        tiers: list = []
        now = int(datetime.now(UTC).timestamp() * 1000)
        if AcquisitionPlatform.BUFF in request.acquisition_platforms and candidate.buff_summary_ask:
            tiers.append(MarketTier(MarketSide.BUFF_ASK, candidate.buff_summary_ask, 1))
        if AcquisitionPlatform.YOUPIN in request.acquisition_platforms and candidate.youpin_summary_ask:
            tiers.append(MarketTier(MarketSide.YOUPIN_ASK, candidate.youpin_summary_ask, 1))
        if candidate.steam_summary_bid:
            tiers.append(MarketTier(MarketSide.STEAM_BID, candidate.steam_summary_bid, 1))
        if not any(tier.side in {MarketSide.BUFF_ASK, MarketSide.YOUPIN_ASK} for tier in tiers):
            return None
        return MarketSnapshot(
            market_hash_name=candidate.market_hash_name,
            csqaq_observed_at=now,
            buff_observed_at=now if candidate.buff_summary_ask else None,
            steam_observed_at=None,
            daily_volume_observed_at=now if candidate.daily_volume is not None else None,
            currency="CNY",
            appid=730,
            tiers=tuple(tiers),
            fee_policy_version=steam_cny_policy().version,
            youpin_observed_at=now if candidate.youpin_summary_ask else None,
            daily_volume=candidate.daily_volume,
            steam_median_price=candidate.steam_transaction_price,
        )

    def _analyze_candidate(
        self, job_id: str, candidate: Candidate, item_nameid: int
    ) -> tuple:
        request = self._require(job_id).request
        snapshot = self._market.fetch_snapshot(
            candidate,
            item_nameid,
            request.acquisition_platforms,
            self._event_sink(job_id),
        )
        recommendation = self._recommendation(snapshot)
        curves = self._curves(snapshot, recommendation.get("recommendation_price"))
        payload = self._result_payload(candidate, snapshot, curves, recommendation)
        payload["job_id"] = job_id
        return snapshot, curves, payload

    def _reject(self, job_id: str, candidate: Candidate, reason_code: str) -> None:
        current = self._require(job_id)
        self._persistence.append_event(
            current,
            "candidate.rejected",
            {
                "market_hash_name": candidate.market_hash_name,
                "reason_code": reason_code,
            },
        )

    def _event_sink(self, job_id: str):
        def emit(event_type: str, payload: dict) -> None:
            current = self._require(job_id)
            if current.status in {ScanStatus.RUNNING, ScanStatus.CANCELLING}:
                self._persistence.append_event(current, event_type, payload)

        return emit

    @staticmethod
    def _acquisition_side(snapshot: MarketSnapshot) -> MarketSide:
        available = [
            side
            for side in (MarketSide.BUFF_ASK, MarketSide.YOUPIN_ASK)
            if snapshot.for_side(side)
        ]
        if not available:
            raise ValueError("snapshot has no acquisition asks")
        return min(available, key=lambda side: snapshot.for_side(side)[0].price)

    def _matches_actual_filters(
        self, request: ScanRequest, snapshot: MarketSnapshot
    ) -> bool:
        side = self._acquisition_side(snapshot)
        price = snapshot.for_side(side)[0].price
        if request.min_price is not None and price < request.min_price:
            return False
        if request.max_price is not None and price > request.max_price:
            return False
        return (snapshot.daily_volume or 0) >= request.min_daily_volume

    @staticmethod
    def _recommendation(snapshot: MarketSnapshot) -> dict:
        asks = [tier for tier in snapshot.tiers if tier.side == MarketSide.STEAM_ASK]
        if not asks:
            return {
                "recommendation_unavailable": True,
                "recommendation_price": None,
                "recommendation_gross": None,
                "recommendation_fees": None,
                "recommendation_seller_proceeds": None,
                "queue_ahead": None,
                "eta_estimate_days": None,
                "recommendation_confidence": "low",
            }
        try:
            policy = steam_cny_policy(snapshot.appid, snapshot.currency)
            estimate = recommend_listing_price(
                lowest_ask=asks[0].price,
                price_tick=1,
                fee_policy=policy,
                requested_qty=10,
                ask_levels=tuple(Tier(tier.price, tier.quantity) for tier in asks),
                min_price=1,
                daily_volume=None,
            )
        except (BelowMinimumPrice, UnreachablePrice, ValueError):
            return {
                "recommendation_unavailable": True,
                "recommendation_price": None,
                "recommendation_gross": None,
                "recommendation_fees": None,
                "recommendation_seller_proceeds": None,
                "queue_ahead": None,
                "eta_estimate_days": None,
                "recommendation_confidence": "low",
            }
        return {
            "recommendation_unavailable": False,
            "recommendation_price": estimate.recommended_price,
            "recommendation_gross": estimate.gross_proceeds,
            "recommendation_fees": estimate.fees,
            "recommendation_seller_proceeds": estimate.seller_proceeds,
            "queue_ahead": estimate.queue_ahead,
            "eta_estimate_days": estimate.eta_estimate,
            "recommendation_confidence": estimate.confidence,
        }

    def _require(self, job_id: str) -> ScanJob:
        job = self._persistence.get_job(job_id)
        if job is None:
            raise LookupError(f"scan job {job_id} not found")
        return job
