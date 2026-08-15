from dataclasses import dataclass

from ..money import CNY
from .errors import UnsupportedFeePolicy


@dataclass(frozen=True, slots=True)
class FeePolicy:
    appid: int
    currency: str
    version: str
    steam_rate_ppm: int
    publisher_rate_ppm: int
    min_steam_fee: int
    min_publisher_fee: int
    market_price_increment: int = 1

    def __post_init__(self) -> None:
        if self.steam_rate_ppm < 0 or self.publisher_rate_ppm < 0:
            raise ValueError("fee rates cannot be negative")
        if self.min_steam_fee < 0 or self.min_publisher_fee < 0:
            raise ValueError("minimum fees cannot be negative")
        if self.market_price_increment < 1:
            raise ValueError("market price increment must be positive")


def steam_cny_policy(appid: int = 730, currency: str = CNY) -> FeePolicy:
    if appid != 730 or currency != CNY:
        raise UnsupportedFeePolicy(f"unsupported fee policy appid={appid}, currency={currency}")
    return FeePolicy(
        appid=appid,
        currency=currency,
        version="steam-cs2-cny-v2-min5",
        steam_rate_ppm=50_000,
        publisher_rate_ppm=100_000,
        # Steam's CNY wallet currently exposes a 5-fen minimum market price
        # for each fee component. This is wallet metadata, not a new rate.
        min_steam_fee=5,
        min_publisher_fee=5,
        market_price_increment=1,
    )
