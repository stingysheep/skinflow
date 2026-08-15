from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from skinflow_api.domain.market.tiers import MarketSide, MarketTier

PRICE_KEYS = (
    "price",
    "commodityprice",
    "saleprice",
    "sellingprice",
    "sellprice",
)


def parse_on_sale_response(payload: dict, limit: int = 10) -> tuple[MarketTier, ...]:
    """Extract the first public listings without depending on response envelope casing."""
    best: list[int] = []
    for rows in _dict_lists(payload):
        prices = [price for row in rows if (price := _find_price(row)) is not None]
        if len(prices) > len(best):
            best = prices
    selected = best[:limit]
    return tuple(
        MarketTier(MarketSide.YOUPIN_ASK, price, quantity)
        for price, quantity in sorted(Counter(selected).items())
    )


def _dict_lists(value: Any) -> Iterable[list[dict]]:
    if isinstance(value, dict):
        for child in value.values():
            yield from _dict_lists(child)
    elif isinstance(value, list):
        if value and all(isinstance(child, dict) for child in value):
            yield value
        for child in value:
            yield from _dict_lists(child)


def _find_price(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    normalized = {str(key).replace("_", "").lower(): child for key, child in value.items()}
    for key in PRICE_KEYS:
        if key in normalized:
            price = _to_cents(normalized[key])
            if price is not None:
                return price
    for child in value.values():
        if isinstance(child, dict) and (price := _find_price(child)) is not None:
            return price
    return None


def _to_cents(value: Any) -> int | None:
    if isinstance(value, dict):
        for key in ("value", "amount", "price"):
            if key in value:
                return _to_cents(value[key])
        return None
    try:
        cents = round(float(str(value).replace(",", "")) * 100)
    except (TypeError, ValueError):
        return None
    return cents if cents > 0 else None
