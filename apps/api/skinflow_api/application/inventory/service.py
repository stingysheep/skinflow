from __future__ import annotations

import time
from threading import Lock, Thread

from .errors import InventoryError, SteamSessionExpired
from .models import InventoryRefreshResult, SteamSessionInfo, SteamSessionStatus
from .ports import (
    InventoryRepository,
    MarketDetailProvider,
    SteamInventoryGateway,
    SteamSessionGateway,
)


class InventoryService:
    def __init__(
        self,
        session: SteamSessionGateway,
        gateway: SteamInventoryGateway,
        repository: InventoryRepository,
        market_detail_provider: MarketDetailProvider | None = None,
    ) -> None:
        self._session = session
        self._gateway = gateway
        self._repository = repository
        self._market_detail_provider = market_detail_provider
        self._detail_refresh_lock = Lock()
        self._detail_refreshing: set[str] = set()
        self._detail_last_attempt: dict[str, float] = {}

    def session_status(self) -> SteamSessionInfo:
        return self._session.status()

    def refresh(self) -> InventoryRefreshResult:
        if self._session.status().status is not SteamSessionStatus.ACTIVE:
            self._repository.record_failure("STEAM_SESSION_REQUIRED")
            raise PermissionError("Steam session is required")
        try:
            return self._repository.sync(self._gateway.fetch_inventory())
        except SteamSessionExpired:
            self._repository.record_failure(SteamSessionExpired.code)
            raise
        except InventoryError as error:
            self._repository.record_failure(error.code)
            raise

    def list_assets(self) -> list[dict]:
        return self._repository.list_assets()

    def list_grouped_assets(self) -> list[dict]:
        return self._repository.list_grouped_assets()

    def get_group_details(self, market_hash_name: str) -> dict | None:
        details = self._repository.get_group_details(market_hash_name)
        trend = (details or {}).get("trend") or []
        has_csqaq_trend = any(point.get("source") == "csqaq" for point in trend)
        if self._market_detail_provider is not None and not has_csqaq_trend:
            # Do not hold the HTTP request open while CSQAQ pagination and chart
            # rate limits are applied. The next detail read will see the saved data.
            with self._detail_refresh_lock:
                now = time.monotonic()
                last_attempt = self._detail_last_attempt.get(market_hash_name, 0.0)
                if market_hash_name not in self._detail_refreshing and now - last_attempt >= 30.0:
                    self._detail_refreshing.add(market_hash_name)
                    self._detail_last_attempt[market_hash_name] = now
                    Thread(
                        target=self._refresh_group_details,
                        args=(market_hash_name,),
                        daemon=True,
                        name="skinflow-market-detail",
                    ).start()
        return details

    def _refresh_group_details(self, market_hash_name: str) -> None:
        try:
            self._market_detail_provider.refresh(market_hash_name)  # type: ignore[union-attr]
        finally:
            with self._detail_refresh_lock:
                self._detail_refreshing.discard(market_hash_name)
