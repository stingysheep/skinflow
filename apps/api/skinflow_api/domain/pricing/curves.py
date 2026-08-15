from dataclasses import dataclass

from .fee_calculator import calculate_net
from .fee_policy import FeePolicy
from .tiers import Tier, expand_tiers

PPM = 1_000_000


@dataclass(frozen=True, slots=True)
class CurvePoint:
    quantity: int
    cost_total: int
    immediate_ratio_ppm: int | None
    recommended_ratio_ppm: int | None
    market_ask_ratio_ppm: int | None


def _ratio(cost: int, proceeds: int) -> int | None:
    return (cost * PPM) // proceeds if proceeds > 0 else None


def _cumulative_net(prices: tuple[int, ...], quantity: int, policy: FeePolicy) -> int | None:
    if len(prices) < quantity:
        return None
    total = 0
    for price in prices[:quantity]:
        try:
            total += calculate_net(price, policy).seller_proceeds
        except ValueError:
            return None
    return total


def build_price_curves(
    buff_asks: tuple[Tier, ...],
    steam_bids: tuple[Tier, ...],
    steam_asks: tuple[Tier, ...],
    policy: FeePolicy,
    recommended_price: int | None = None,
    limit: int = 10,
) -> tuple[CurvePoint, ...]:
    buff_prices = expand_tiers(buff_asks, limit)
    bid_prices = expand_tiers(steam_bids, limit)
    ask_prices = expand_tiers(steam_asks, limit)
    points: list[CurvePoint] = []
    cost = 0
    for quantity, price in enumerate(buff_prices, start=1):
        cost += price
        immediate = _cumulative_net(bid_prices, quantity, policy)
        market_ask = _cumulative_net(ask_prices, quantity, policy)
        recommended = (
            _cumulative_net((recommended_price,) * quantity, quantity, policy)
            if recommended_price is not None
            else None
        )
        points.append(
            CurvePoint(
                quantity,
                cost,
                _ratio(cost, immediate or 0),
                _ratio(cost, recommended or 0),
                _ratio(cost, market_ask or 0),
            )
        )
    return tuple(points)
