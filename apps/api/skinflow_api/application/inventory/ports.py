from __future__ import annotations

from typing import Protocol

from .models import InventoryAsset, InventoryRefreshResult, SteamSessionInfo


class SteamSessionGateway(Protocol):
    def status(self) -> SteamSessionInfo: ...


class SteamInventoryGateway(Protocol):
    def fetch_inventory(self) -> tuple[InventoryAsset, ...]: ...


class InventoryRepository(Protocol):
    def sync(self, assets: tuple[InventoryAsset, ...]) -> InventoryRefreshResult: ...

    def record_failure(self, failure_code: str) -> None: ...

    def list_assets(self) -> list[dict]: ...

    def list_grouped_assets(self) -> list[dict]: ...

    def get_group_details(self, market_hash_name: str) -> dict | None: ...


class MarketDetailProvider(Protocol):
    def refresh(self, market_hash_name: str) -> bool: ...
