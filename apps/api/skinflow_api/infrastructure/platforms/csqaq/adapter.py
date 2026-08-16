import time
from collections.abc import Sequence
from threading import RLock
from urllib.parse import quote

from skinflow_api.application.scan.models import AcquisitionPlatform, ScanRequest
from skinflow_api.application.scan.ports import Candidate, CandidateSource, ScanEventSink
from skinflow_api.application.scan.upstream_errors import (
    CsqaqAccessDenied,
    UpstreamUnavailable,
)
from skinflow_api.infrastructure.http.client import HttpClient
from skinflow_api.infrastructure.http.rate_limiter import PlatformRateLimiter

from .chart import parse_chart
from .parser import parse_candidates

BASE_URL = "https://api.csqaq.com/api/v1/info/exchange_detail"
SUGGEST_URL = "https://api.csqaq.com/api/v1/search/suggest"
GOOD_URL = "https://api.csqaq.com/api/v1/info/good"
CHART_URL = "https://api.csqaq.com/api/v1/info/chart"


class CsqaqAdapter(CandidateSource):
    def __init__(
        self,
        token: str,
        client: HttpClient | None = None,
        limiter: PlatformRateLimiter | None = None,
    ) -> None:
        self._token = token
        self._client = client or HttpClient()
        self._limiter = limiter or PlatformRateLimiter(
            "csqaq", concurrency=1, min_interval_seconds=1.25
        )
        self._candidate_cache: dict[str, Candidate] = {}
        self._chart_cache: dict[tuple[int, int, str, str], tuple[float, tuple[dict, ...]]] = {}
        self._candidate_cache_lock = RLock()
        self._chart_cache_ttl_seconds = 900.0

    def list_candidates(
        self,
        request: ScanRequest,
        event_sink: ScanEventSink | None = None,
    ) -> Sequence[Candidate]:
        if not self._token:
            return ()
        platforms = set(request.acquisition_platforms)
        if platforms == {AcquisitionPlatform.BUFF, AcquisitionPlatform.YOUPIN}:
            platform_query = "BUFF-YYYP"
        elif AcquisitionPlatform.YOUPIN in platforms:
            platform_query = "YYYP"
        else:
            platform_query = "BUFF"
        wanted = set(request.manual_names)
        with self._candidate_cache_lock:
            cached = {
                name: self._candidate_cache[name]
                for name in wanted
                if name in self._candidate_cache
            }
        if wanted and wanted <= cached.keys():
            return tuple(cached[name] for name in request.manual_names)

        # Inventory/holdings detail uses an exact name rather than the ranked
        # list. CSQAQ exposes a public suggestion endpoint for this case, so a
        # rare item does not require walking hundreds of ranking pages.
        if wanted:
            for name in request.manual_names:
                if name in cached:
                    continue
                candidate = self._lookup_candidate(name, event_sink)
                if candidate is not None:
                    cached[name] = candidate
            if wanted <= cached.keys():
                return tuple(cached[name] for name in request.manual_names)

        candidates_by_name: dict[str, Candidate] = {}
        announced: set[str] = set()
        matching_count = 0
        page_index = 1
        while page_index <= 20 and (wanted or matching_count < request.candidate_limit):
            try:
                data = self._limiter.run(
                    lambda page=page_index: self._client.request_json(
                        BASE_URL,
                        method="POST",
                        headers={"ApiToken": self._token},
                        body={
                            "page_index": page,
                            "res": 0,
                            "platforms": platform_query,
                            "sort_by": 1,
                            "turnover": request.min_daily_volume,
                            "min_price": (request.min_price or 1) / 100,
                            "max_price": (request.max_price or 300_000) / 100,
                        },
                    ),
                    event_sink,
                )
            except UpstreamUnavailable as error:
                if error.status_code in {401, 403}:
                    raise CsqaqAccessDenied("csqaq rejected the configured API token") from error
                raise
            rows = data.get("data") or []
            page_candidates = parse_candidates(rows)
            for candidate in page_candidates:
                candidates_by_name.setdefault(candidate.market_hash_name, candidate)
                with self._candidate_cache_lock:
                    self._candidate_cache[candidate.market_hash_name] = candidate
                if (
                    event_sink is not None
                    and candidate.market_hash_name not in announced
                    and len(announced) < request.candidate_limit
                    and _matches_request(candidate, request)
                ):
                    announced.add(candidate.market_hash_name)
                    event_sink(
                        "candidate.discovered",
                        {
                            "market_hash_name": candidate.market_hash_name,
                            "name": candidate.name,
                            "good_id": candidate.good_id,
                        },
                    )
            matching_count = sum(
                _matches_request(candidate, request) for candidate in candidates_by_name.values()
            )
            if wanted and wanted.issubset(candidates_by_name.keys() | cached.keys()):
                break
            if not rows or len(page_candidates) == 0:
                break
            page_index += 1
        candidates = tuple(candidates_by_name.values())
        if request.manual_names:
            wanted = set(request.manual_names)
            merged = {**cached, **candidates_by_name}
            candidates = tuple(merged[name] for name in request.manual_names if name in merged)
        return tuple(candidate for candidate in candidates if _matches_request(candidate, request))[
            : request.candidate_limit
        ]

    def lookup_candidate(
        self,
        market_hash_name: str,
        *,
        search_text: str | None = None,
        event_sink: ScanEventSink | None = None,
    ) -> Candidate | None:
        """Resolve a non-ranked item through CSQAQ's public autocomplete API."""
        return self._lookup_candidate(market_hash_name, event_sink, search_text=search_text)

    def _lookup_candidate(
        self,
        market_hash_name: str,
        event_sink: ScanEventSink | None = None,
        *,
        search_text: str | None = None,
    ) -> Candidate | None:
        try:
            suggestions = self._limiter.run(
                lambda: self._client.request_json(
                    f"{SUGGEST_URL}?text={quote((search_text or market_hash_name).upper())}",
                    headers={"ApiToken": self._token},
                ),
                event_sink,
            )
            rows = suggestions.get("data") or []
            for suggestion in rows[:10]:
                good_id = int(suggestion.get("id") or 0)
                if good_id < 1:
                    continue
                detail = self._limiter.run(
                    lambda good_id=good_id: self._client.request_json(
                        f"{GOOD_URL}?id={good_id}",
                        headers={"ApiToken": self._token},
                    ),
                    event_sink,
                )
                goods = (detail.get("data") or {}).get("goods_info") or {}
                candidates = parse_candidates([goods])
                candidate = candidates[0] if candidates else None
                if (
                    candidate
                    and candidate.market_hash_name.casefold() == market_hash_name.casefold()
                ):
                    with self._candidate_cache_lock:
                        self._candidate_cache[market_hash_name] = candidate
                    return candidate
            return None
        except (TypeError, ValueError, UpstreamUnavailable):
            return None

    def fetch_chart(
        self,
        good_id: int,
        *,
        key: str = "sell_price",
        platform: int = 3,
        # One year is enough to show direction and keeps the first detail load small.
        period: str = "365",
        style: str = "all_style",
        event_sink: ScanEventSink | None = None,
    ) -> tuple[dict[str, int | str | None], ...]:
        if not self._token or good_id < 1:
            return ()
        cache_key = (good_id, platform, key, period)
        now = time.monotonic()
        with self._candidate_cache_lock:
            cached = self._chart_cache.get(cache_key)
            if cached is not None and now - cached[0] < self._chart_cache_ttl_seconds:
                return cached[1]
        try:
            data = self._limiter.run(
                lambda: self._client.request_json(
                    CHART_URL,
                    method="POST",
                    headers={"ApiToken": self._token},
                    body={
                        "good_id": str(good_id),
                        "key": key,
                        "platform": platform,
                        "period": period,
                        "style": style,
                    },
                ),
                event_sink,
            )
        except UpstreamUnavailable as error:
            if error.status_code in {401, 403}:
                raise CsqaqAccessDenied("csqaq rejected the configured API token") from error
            raise
        points = parse_chart(data, key=key)
        with self._candidate_cache_lock:
            self._chart_cache[cache_key] = (time.monotonic(), points)
        return points


def _matches_request(candidate: Candidate, request: ScanRequest) -> bool:
    prices = []
    if AcquisitionPlatform.BUFF in request.acquisition_platforms:
        prices.append(candidate.buff_summary_ask)
    if AcquisitionPlatform.YOUPIN in request.acquisition_platforms:
        prices.append(candidate.youpin_summary_ask)
    prices = [price for price in prices if price is not None]
    if not prices:
        return False
    price = min(prices)
    if request.min_price is not None and price < request.min_price:
        return False
    if request.max_price is not None and price > request.max_price:
        return False
    return (candidate.daily_volume or 0) >= request.min_daily_volume
