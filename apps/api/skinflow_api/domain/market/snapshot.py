from dataclasses import dataclass

from .tiers import MarketTier


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    market_hash_name: str
    csqaq_observed_at: int | None
    buff_observed_at: int | None
    steam_observed_at: int | None
    daily_volume_observed_at: int | None
    currency: str
    appid: int
    tiers: tuple[MarketTier, ...]
    fee_policy_version: str
    youpin_observed_at: int | None = None
    daily_volume: int | None = None
    steam_median_price: int | None = None

    def for_side(self, side: str) -> tuple[MarketTier, ...]:
        return tuple(tier for tier in self.tiers if tier.side == side)
