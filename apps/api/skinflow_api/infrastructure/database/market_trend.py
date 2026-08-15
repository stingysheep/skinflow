from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS market_trend_point (
  market_hash_name TEXT NOT NULL,
  good_id INTEGER NOT NULL,
  platform INTEGER NOT NULL,
  data_key TEXT NOT NULL,
  observed_at INTEGER NOT NULL,
  value INTEGER NOT NULL,
  quantity INTEGER,
  fetched_at INTEGER NOT NULL,
  PRIMARY KEY(market_hash_name, platform, data_key, observed_at)
);
CREATE INDEX IF NOT EXISTS idx_market_trend_name
  ON market_trend_point(market_hash_name, platform, data_key, observed_at);
"""


def ensure_market_trend_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)


def replace_market_trend(
    connection: sqlite3.Connection,
    *,
    market_hash_name: str,
    good_id: int,
    platform: int,
    data_key: str,
    points: Iterable[dict[str, int | str | None]],
) -> None:
    fetched_at = int(time.time() * 1000)
    normalized = [
        (
            market_hash_name,
            good_id,
            platform,
            data_key,
            point["observed_at"],
            point["value"],
            point.get("quantity"),
            fetched_at,
        )
        for point in points
        if point.get("observed_at") is not None and point.get("value") is not None
    ]
    connection.execute(
        "DELETE FROM market_trend_point WHERE market_hash_name=? AND platform=? AND data_key=?",
        (market_hash_name, platform, data_key),
    )
    connection.executemany(
        "INSERT OR REPLACE INTO market_trend_point(" 
        "market_hash_name,good_id,platform,data_key,observed_at,value,quantity,fetched_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        normalized,
    )


def read_market_trend(
    connection: sqlite3.Connection,
    market_hash_name: str,
    *,
    platform: int = 3,
    data_key: str = "sell_price",
) -> list[dict[str, int | str | None]]:
    rows = connection.execute(
        "SELECT observed_at,value,quantity FROM market_trend_point "
        "WHERE market_hash_name=? AND platform=? AND data_key=? "
        "ORDER BY observed_at",
        (market_hash_name, platform, data_key),
    ).fetchall()
    return [
        {
            "observed_at": int(row["observed_at"]),
            "median_price": int(row["value"]),
            "lowest_ask": int(row["value"]),
            "highest_bid": None,
            "quantity": int(row["quantity"]) if row["quantity"] is not None else None,
            "source": "csqaq",
        }
        for row in rows
    ]
