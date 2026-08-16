from __future__ import annotations

from dataclasses import dataclass

from skinflow_api.application.inventory.models import InventoryAsset
from skinflow_api.domain.market.snapshot import MarketSnapshot
from skinflow_api.domain.market.tiers import MarketTier

MAX_LISTING_PREVIEW_ASSETS = 100


@dataclass(frozen=True, slots=True)
class ListingSelection:
    platform: str
    appid: int
    contextid: str
    assetid: str
    buyer_pays: int | None = None
    cost_each: int | None = None


@dataclass(frozen=True, slots=True)
class ListingGroupSelection:
    """User-facing selection for a quantity of identical inventory items."""

    market_hash_name: str
    quantity: int
    buyer_pays: int | None = None


@dataclass(frozen=True, slots=True)
class ListingContext:
    asset: InventoryAsset
    snapshot_id: str | None
    snapshot_job_id: str | None
    asks: tuple[MarketTier, ...]
    cost_each: int | None
    active_listing: bool


@dataclass(frozen=True, slots=True)
class ListingMarketSnapshot:
    """Fresh public Steam market data prepared for a listing preview."""

    snapshot: MarketSnapshot
    snapshot_id: str
    snapshot_job_id: str
    asks: tuple[MarketTier, ...]
    bids: tuple[MarketTier, ...] = ()


@dataclass(frozen=True, slots=True)
class ListingGatewayResult:
    accepted: bool
    needs_confirmation: bool
    listing_id: str | None
    message: str | None
