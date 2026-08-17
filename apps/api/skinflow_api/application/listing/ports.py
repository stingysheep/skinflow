from __future__ import annotations

from typing import Protocol

from skinflow_api.domain.listing import ListingDecision
from skinflow_api.domain.market.snapshot import MarketSnapshot

from .models import (
    ListingContext,
    ListingGatewayResult,
    ListingGroupSelection,
    ListingMarketSnapshot,
    ListingSelection,
)


class ListingCatalog(Protocol):
    def context_for(self, selection: ListingSelection) -> ListingContext | None: ...

    def contexts_for_group(
        self, selection: ListingGroupSelection
    ) -> tuple[ListingContext, ...]: ...

    def average_cost_for_group(self, market_hash_name: str) -> int | None: ...


class ListingPersistence(Protocol):
    def create_preview(self, decisions: tuple[ListingDecision, ...], expires_at: int) -> dict: ...

    def get_preview(self, preview_id: str) -> dict | None: ...

    def update_preview_items(
        self, preview_id: str, updates: tuple[dict, ...]
    ) -> None: ...

    def create_request(self, preview_id: str, idempotency_key: str) -> dict: ...

    def begin_submission(self, request_id: str, decision: dict) -> None: ...

    def abort_request(self, request_id: str, message: str) -> None: ...

    def record_result(
        self, request_id: str, decision: dict, result: ListingGatewayResult
    ) -> None: ...

    def complete_request(self, request_id: str) -> dict: ...

    def recover_interrupted_requests(self) -> None: ...

    def get_request(self, request_id: str) -> dict | None: ...

    def list_requests(self) -> list[dict]: ...

    def list_cancellable_items(self, item_ids: tuple[str, ...]) -> list[dict]: ...

    def mark_cancelled(self, item_id: str, checked_at: int) -> None: ...

    def mark_cancellation_pending(
        self, item_id: str, checked_at: int, message: str
    ) -> None: ...


class ListingGateway(Protocol):
    def submit(self, decision: dict) -> ListingGatewayResult: ...

    def cancel(self, listing_id: str) -> bool: ...


class ListingMarketSnapshotProvider(Protocol):
    def fetch(self, context: ListingContext) -> ListingMarketSnapshot: ...


class ListingSnapshotStore(Protocol):
    def save_listing_snapshot(self, snapshot: MarketSnapshot) -> tuple[str, str]: ...
