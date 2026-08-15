from dataclasses import dataclass

from .errors import BelowMinimumPrice, UnreachablePrice
from .fee_calculator import FeeBreakdown, calculate_net
from .fee_policy import FeePolicy
from .tiers import Tier


@dataclass(frozen=True, slots=True)
class ListingPriceEstimate:
    recommended_price: int
    gross_proceeds: int
    fees: int
    seller_proceeds: int
    queue_ahead: int
    eta_estimate: float | None
    confidence: str
    fee_policy_version: str


def _pays_to_receive(pays: int, policy: FeePolicy) -> FeeBreakdown | None:
    try:
        return calculate_net(pays, policy)
    except ValueError:
        return None


def recommend_listing_price(
    lowest_ask: int,
    price_tick: int,
    fee_policy: FeePolicy,
    requested_qty: int,
    ask_levels: tuple[Tier, ...],
    min_price: int,
    daily_volume: int | None,
) -> ListingPriceEstimate:
    if lowest_ask < 1 or price_tick < 1 or requested_qty < 1 or min_price < 1:
        raise ValueError("listing price inputs must be positive")
    target = lowest_ask - price_tick
    if target < min_price:
        raise BelowMinimumPrice(f"target={target} min_price={min_price}")

    breakdown = None
    for candidate in range(target, max(min_price, target - 3) - 1, -1):
        breakdown = _pays_to_receive(candidate, fee_policy)
        if breakdown is not None:
            target = candidate
            break
    if breakdown is None:
        raise UnreachablePrice(f"target={target}")

    queue_ahead = sum(level.quantity for level in ask_levels if level.price <= target)
    eta = None
    if daily_volume and daily_volume > 0:
        eta = (queue_ahead + requested_qty) / daily_volume
    if ask_levels and daily_volume and daily_volume > 0:
        confidence = "high"
    elif ask_levels:
        confidence = "medium"
    else:
        confidence = "low"
    return ListingPriceEstimate(
        recommended_price=target,
        gross_proceeds=breakdown.buyer_pays * requested_qty,
        fees=breakdown.total_fee * requested_qty,
        seller_proceeds=breakdown.seller_proceeds * requested_qty,
        queue_ahead=queue_ahead,
        eta_estimate=eta,
        confidence=confidence,
        fee_policy_version=fee_policy.version,
    )
