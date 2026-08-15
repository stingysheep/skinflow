from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SteamSessionStatus(StrEnum):
    ABSENT = "absent"
    ACTIVE = "active"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class SteamSessionInfo:
    status: SteamSessionStatus
    steamid64: str | None = None


@dataclass(frozen=True, slots=True)
class InventoryAsset:
    platform: str
    appid: int
    contextid: str
    assetid: str
    market_hash_name: str
    display_name: str
    image_url: str
    classid: str
    instanceid: str
    marketable: bool
    tradable: bool
    hold_text: str | None = None
    wear_text: str | None = None

    def __post_init__(self) -> None:
        if self.platform != "steam" or self.appid != 730:
            raise ValueError("only Steam CS2 inventory assets are supported")
        if not self.contextid or not self.assetid or not self.market_hash_name:
            raise ValueError("inventory asset identity and market name are required")


@dataclass(frozen=True, slots=True)
class InventoryRefreshResult:
    run_id: str
    asset_count: int
    observed_at: int
