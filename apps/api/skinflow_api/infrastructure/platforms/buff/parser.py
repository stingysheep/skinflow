from collections import Counter
from collections.abc import Iterable

from skinflow_api.domain.pricing.tiers import Tier


def parse_sell_orders(rows: Iterable[dict]) -> tuple[Tier, ...]:
    prices: list[int] = []
    for row in rows:
        try:
            price = round(float(row["price"]) * 100)
        except (KeyError, TypeError, ValueError):
            continue
        if price > 0:
            prices.append(price)
    return tuple(Tier(price, quantity) for price, quantity in sorted(Counter(prices).items()))
