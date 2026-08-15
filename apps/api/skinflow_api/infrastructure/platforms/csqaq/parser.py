from collections.abc import Iterable

from skinflow_api.application.scan.ports import Candidate


def parse_candidates(rows: Iterable[dict]) -> tuple[Candidate, ...]:
    candidates: list[Candidate] = []
    for row in rows:
        try:
            name = str(row["market_hash_name"])
            good_id = int(row["id"])
            buff_id = int(row.get("buff_id") or 0)
            youpin_id = int(row.get("yyyp_id") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if not name or (buff_id < 1 and youpin_id < 1):
            continue
        candidates.append(
            Candidate(
                market_hash_name=name,
                name=str(row.get("name") or name),
                image_url=str(row.get("img") or ""),
                buff_goods_id=buff_id,
                good_id=good_id,
                youpin_goods_id=youpin_id,
                buff_summary_ask=_money(row.get("buff_sell_price")),
                youpin_summary_ask=_money(row.get("yyyp_sell_price")),
                daily_volume=_integer(row.get("turnover_number")),
                steam_transaction_price=_money(row.get("steam_sell_price")),
                steam_summary_bid=_money(row.get("steam_buy_price")),
                csqaq_url=(
                    str(row.get("url") or row.get("detail_url") or row.get("market_url") or "")
                    or None
                ),
            )
        )
    return tuple(candidates)


def _money(value: object) -> int | None:
    try:
        price = round(float(value) * 100)
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def _integer(value: object) -> int | None:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None
