from skinflow_api.domain.market.tiers import MarketSide, MarketTier


def _parse_graph(graph: list) -> tuple[MarketTier, ...]:
    tiers: list[MarketTier] = []
    previous = 0
    for entry in graph:
        try:
            price = round(float(entry[0]) * 100)
            cumulative = int(entry[1])
        except (IndexError, TypeError, ValueError):
            continue
        quantity = cumulative - previous
        previous = cumulative
        if quantity > 0:
            tiers.append(MarketTier(MarketSide.STEAM_BID, price, quantity))
    return tuple(tiers)


def parse_histogram(data: dict) -> tuple[MarketTier, ...]:
    buys = _parse_graph(data.get("buy_order_graph") or [])
    sells = _parse_graph(data.get("sell_order_graph") or [])
    sells = tuple(MarketTier(MarketSide.STEAM_ASK, tier.price, tier.quantity) for tier in sells)
    return buys + sells
