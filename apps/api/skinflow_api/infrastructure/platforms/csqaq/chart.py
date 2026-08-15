from __future__ import annotations


def parse_chart(data: dict, *, key: str = "sell_price") -> tuple[dict[str, int | str | None], ...]:
    """Normalize CSQAQ's parallel timestamp/value arrays into cent-based points."""
    payload = data.get("data") or {}
    timestamps = payload.get("timestamp") or []
    values = payload.get("main_data") or []
    quantities = payload.get("num_data") or []
    numeric_values: list[float] = []
    for value in values:
        try:
            numeric_values.append(float(value))
        except (TypeError, ValueError):
            continue
    # CSQAQ has returned both yuan decimals and fen integers across endpoints.
    # Treat small series as yuan and preserve larger series as fen.
    price_multiplier = (
        100 if numeric_values and max(abs(value) for value in numeric_values) < 1000 else 1
    )
    points: list[dict[str, int | str | None]] = []
    for index, (timestamp, value) in enumerate(zip(timestamps, values, strict=False)):
        try:
            observed_at = int(timestamp)
            price = int(round(float(value) * price_multiplier))
        except (TypeError, ValueError):
            continue
        if observed_at <= 0 or price < 0:
            continue
        quantity: int | None = None
        if index < len(quantities):
            try:
                quantity = max(0, int(float(quantities[index])))
            except (TypeError, ValueError):
                quantity = None
        points.append(
            {"observed_at": observed_at, "value": price, "quantity": quantity, "key": key}
        )
    return tuple(points)
