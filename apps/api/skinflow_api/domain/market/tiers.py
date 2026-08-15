from dataclasses import dataclass
from enum import StrEnum


class MarketSide(StrEnum):
    BUFF_ASK = "buff_ask"
    YOUPIN_ASK = "youpin_ask"
    STEAM_BID = "steam_bid"
    STEAM_ASK = "steam_ask"


@dataclass(frozen=True, slots=True)
class MarketTier:
    side: MarketSide
    price: int
    quantity: int

    def __post_init__(self) -> None:
        if self.price < 1 or self.quantity < 1:
            raise ValueError("market tier price and quantity must be positive")
