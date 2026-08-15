from __future__ import annotations

import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS item_metadata (
  market_hash_name TEXT PRIMARY KEY,
  display_name_zh TEXT NOT NULL DEFAULT '',
  image_url TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);
"""


def ensure_item_metadata_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)


def upsert_item_metadata(
    connection: sqlite3.Connection,
    *,
    market_hash_name: str,
    display_name_zh: str,
    image_url: str,
    source: str,
    updated_at: int | None = None,
) -> None:
    has_chinese = any("\u4e00" <= char <= "\u9fff" for char in display_name_zh)
    localized_name = display_name_zh if has_chinese else ""
    connection.execute(
        "INSERT INTO item_metadata VALUES(?,?,?,?,?) "
        "ON CONFLICT(market_hash_name) DO UPDATE SET "
        "display_name_zh=CASE WHEN excluded.display_name_zh<>'' "
        "THEN excluded.display_name_zh ELSE item_metadata.display_name_zh END,"
        "image_url=CASE WHEN excluded.image_url<>'' "
        "THEN excluded.image_url ELSE item_metadata.image_url END,"
        "source=excluded.source,updated_at=excluded.updated_at",
        (
            market_hash_name,
            localized_name,
            image_url,
            source,
            updated_at or int(time.time() * 1000),
        ),
    )


def import_legacy_item_metadata(source: str | Path, target: str | Path) -> dict[str, int]:
    source_connection = sqlite3.connect(source)
    source_connection.row_factory = sqlite3.Row
    target_connection = sqlite3.connect(target)
    target_connection.row_factory = sqlite3.Row
    ensure_item_metadata_schema(target_connection)

    names = {
        str(row["market_hash"]): (str(row["name"]), int(row["updated_at"]))
        for row in source_connection.execute("SELECT market_hash,name,updated_at FROM zh_names")
    }
    images = {
        str(row["market_hash"]): (str(row["img"]), int(row["updated_at"]))
        for row in source_connection.execute("SELECT market_hash,img,updated_at FROM images")
    }
    keys = names.keys() | images.keys()
    with target_connection:
        for market_hash_name in keys:
            name, name_updated_at = names.get(market_hash_name, ("", 0))
            image_url, image_updated_at = images.get(market_hash_name, ("", 0))
            upsert_item_metadata(
                target_connection,
                market_hash_name=market_hash_name,
                display_name_zh=name,
                image_url=image_url,
                source="legacy_cache",
                updated_at=max(name_updated_at, image_updated_at) * 1000,
            )
    source_connection.close()
    target_connection.close()
    return {"names": len(names), "images": len(images), "items": len(keys)}
