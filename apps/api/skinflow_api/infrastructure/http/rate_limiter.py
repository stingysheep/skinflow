from __future__ import annotations

import random
import time
from collections.abc import Callable
from threading import BoundedSemaphore, Lock
from typing import TypeVar

from skinflow_api.application.scan.ports import ScanEventSink
from skinflow_api.application.scan.upstream_errors import RateLimited, UpstreamUnavailable

T = TypeVar("T")


class PlatformRateLimiter:
    """Bound concurrency, pace launches and persist observable 429 backoff."""

    def __init__(
        self,
        platform: str,
        *,
        concurrency: int,
        min_interval_seconds: float = 0.0,
        max_attempts: int = 3,
    ) -> None:
        if concurrency < 1 or min_interval_seconds < 0 or max_attempts < 1:
            raise ValueError("invalid platform limiter configuration")
        self._platform = platform
        self._slots = BoundedSemaphore(concurrency)
        self._interval = min_interval_seconds
        self._max_attempts = max_attempts
        self._clock_lock = Lock()
        self._next_start = 0.0

    def run(
        self,
        operation: Callable[[], T],
        event_sink: ScanEventSink | None = None,
    ) -> T:
        with self._slots:
            for attempt in range(1, self._max_attempts + 1):
                self._wait_for_launch()
                try:
                    result = operation()
                except RateLimited as error:
                    if attempt >= self._max_attempts:
                        raise RateLimited(
                            str(error),
                            retry_after_seconds=error.retry_after_seconds,
                            platform=self._platform,
                        ) from error
                    delay = self._backoff_seconds(error, attempt)
                    self._reserve_cooldown(delay)
                    self._emit(
                        event_sink,
                        "upstream.backoff_started",
                        {
                            "platform": self._platform,
                            "reason_code": "UPSTREAM_RATE_LIMITED",
                            "retry_after_seconds": round(delay, 3),
                            "attempt": attempt,
                        },
                    )
                    time.sleep(delay)
                    self._emit(
                        event_sink,
                        "upstream.backoff_completed",
                        {
                            "platform": self._platform,
                            "reason_code": "UPSTREAM_RATE_LIMITED",
                            "retry_after_seconds": round(delay, 3),
                            "attempt": attempt,
                        },
                    )
                    continue
                except UpstreamUnavailable as error:
                    retryable = error.status_code is None or error.status_code >= 500
                    if not retryable or attempt >= self._max_attempts:
                        raise
                    delay = min(4.0, 0.5 * (2 ** (attempt - 1))) + random.uniform(0.05, 0.2)
                    self._reserve_cooldown(delay)
                    payload = {
                        "platform": self._platform,
                        "reason_code": "UPSTREAM_UNAVAILABLE",
                        "retry_after_seconds": round(delay, 3),
                        "attempt": attempt,
                    }
                    self._emit(event_sink, "upstream.backoff_started", payload)
                    time.sleep(delay)
                    self._emit(event_sink, "upstream.backoff_completed", payload)
                    continue
                return result
        raise AssertionError("unreachable limiter state")

    def _wait_for_launch(self) -> None:
        with self._clock_lock:
            now = time.monotonic()
            delay = max(0.0, self._next_start - now)
            self._next_start = max(now, self._next_start) + self._interval
        if delay:
            time.sleep(delay)

    def _reserve_cooldown(self, delay: float) -> None:
        with self._clock_lock:
            self._next_start = max(self._next_start, time.monotonic() + delay)

    @staticmethod
    def _backoff_seconds(error: RateLimited, attempt: int) -> float:
        if error.retry_after_seconds is not None:
            return max(0.1, float(error.retry_after_seconds))
        return min(8.0, float(2 ** (attempt - 1))) + random.uniform(0.05, 0.25)

    @staticmethod
    def _emit(event_sink: ScanEventSink | None, event_type: str, payload: dict) -> None:
        if event_sink is not None:
            event_sink(event_type, payload)
