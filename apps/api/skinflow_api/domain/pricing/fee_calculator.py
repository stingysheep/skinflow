from dataclasses import dataclass

from .errors import NegativeProceeds
from .fee_policy import FeePolicy

PPM = 1_000_000


@dataclass(frozen=True, slots=True)
class FeeBreakdown:
    buyer_pays: int
    steam_fee: int
    publisher_fee: int
    seller_proceeds: int

    @property
    def total_fee(self) -> int:
        return self.steam_fee + self.publisher_fee


def _to_valid_market_price(amount: int, floor: int, policy: FeePolicy) -> int:
    increment = policy.market_price_increment
    if amount <= floor:
        return floor
    if amount <= increment:
        return increment
    if increment > 1:
        return round(amount / increment) * increment
    return amount


def calculate_fee(gross: int, rate_ppm: int, minimum: int, policy: FeePolicy | None = None) -> int:
    if gross < 1:
        raise ValueError("gross must be at least one fen")
    raw = max(minimum, (gross * rate_ppm) // PPM)
    return _to_valid_market_price(raw, minimum, policy) if policy is not None else raw


def receive_to_pays(receive: int, policy: FeePolicy) -> FeeBreakdown:
    base = _to_valid_market_price(receive, max(policy.min_steam_fee, policy.min_publisher_fee), policy)
    steam_fee = calculate_fee(base, policy.steam_rate_ppm, policy.min_steam_fee, policy)
    publisher_fee = calculate_fee(base, policy.publisher_rate_ppm, policy.min_publisher_fee, policy)
    buyer_pays = base + steam_fee + publisher_fee
    return FeeBreakdown(buyer_pays, steam_fee, publisher_fee, base)


def calculate_net(buyer_pays: int, policy: FeePolicy) -> FeeBreakdown:
    if buyer_pays < 1:
        raise ValueError("buyer_pays must be at least one fen")
    low, high = 1, buyer_pays
    while low <= high:
        receive = (low + high) // 2
        breakdown = receive_to_pays(receive, policy)
        if breakdown.buyer_pays == buyer_pays:
            return breakdown
        if breakdown.buyer_pays < buyer_pays:
            low = receive + 1
        else:
            high = receive - 1
    raise NegativeProceeds(f"buyer-paid price {buyer_pays} is unreachable")
