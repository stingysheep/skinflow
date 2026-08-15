from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Tier:
    price: int
    quantity: int

    def __post_init__(self) -> None:
        if self.price < 1 or self.quantity < 1:
            raise ValueError("tier price and quantity must be positive")


def expand_tiers(tiers: tuple[Tier, ...], limit: int = 10) -> tuple[int, ...]:
    if limit < 1:
        raise ValueError("limit must be positive")
    prices: list[int] = []
    for tier in tiers:
        remaining = limit - len(prices)
        if remaining <= 0:
            break
        prices.extend([tier.price] * min(tier.quantity, remaining))
    return tuple(prices)
