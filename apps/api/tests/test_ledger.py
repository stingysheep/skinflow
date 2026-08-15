import sqlite3
from pathlib import Path

import pytest

from skinflow_api.infrastructure.database.item_metadata import (
    import_legacy_item_metadata,
    upsert_item_metadata,
)
from skinflow_api.infrastructure.database.ledger import LedgerRepository, migrate_legacy_ledger


def test_legacy_ledger_migration_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "legacy.db"
    connection = sqlite3.connect(source)
    connection.executescript("""
    CREATE TABLE lots (id INTEGER PRIMARY KEY, market_hash TEXT, game TEXT,
      qty INTEGER, cost_each INTEGER, bought_at INTEGER, venue TEXT, floor_at_buy INTEGER);
    CREATE TABLE fills (id INTEGER PRIMARY KEY, lot_id INTEGER, qty INTEGER,
      receive_total INTEGER, sold_at INTEGER);
    CREATE TABLE listings (id INTEGER PRIMARY KEY, lot_id INTEGER, assetid TEXT,
      market_hash TEXT, receive_cents INTEGER, status TEXT, message TEXT,
      listing_id TEXT, created_at INTEGER);
    CREATE TABLE pending_buys (id INTEGER PRIMARY KEY, market_hash TEXT, game TEXT,
      cost_each INTEGER, qty_at_open INTEGER, opened_at INTEGER, venue TEXT, floor_at_buy INTEGER);
    INSERT INTO lots VALUES(1,'AK-47 | Slate','cs2',3,100,1000,'BUFF',NULL);
    INSERT INTO fills VALUES(1,1,1,140,1100);
    """)
    connection.commit()
    connection.close()
    target = tmp_path / "new.db"
    first = migrate_legacy_ledger(source, target)
    second = migrate_legacy_ledger(source, target)
    repository = LedgerRepository(target)
    holdings = repository.list_holdings()
    history = repository.list_history()
    repository.close()
    assert first["status"] == "completed"
    assert second["status"] == "already_completed"
    assert holdings[0]["open_quantity"] == 2
    assert history[0]["receive_total"] == 140


def test_purchase_and_fifo_sale(tmp_path: Path) -> None:
    repository = LedgerRepository(tmp_path / "ledger.db")
    repository.create_purchase("AK-47 | Slate", 2, 100, 1000, "BUFF", False)
    repository.create_purchase("AK-47 | Slate", 2, 120, 1100, "BUFF", False)
    result = repository.record_sale("AK-47 | Slate", 3, 500, 1200)
    assert [fill["quantity"] for fill in result["fills"]] == [2, 1]
    assert repository.list_holdings()[0]["open_quantity"] == 1


def test_sale_rejects_oversell_without_writing(tmp_path: Path) -> None:
    repository = LedgerRepository(tmp_path / "ledger.db")
    repository.create_purchase("AK-47 | Slate", 1, 100, 1000, None, False)
    with pytest.raises(ValueError, match="insufficient"):
        repository.record_sale("AK-47 | Slate", 2, 200, 1100)
    assert repository.list_history() == []


def test_pending_purchase_can_be_listed_and_received(tmp_path: Path) -> None:
    repository = LedgerRepository(tmp_path / "ledger.db")
    pending = repository.create_purchase("AK-47 | Slate", 2, 100, 1000, "BUFF", True)
    assert repository.list_pending_purchases()[0]["quantity"] == 2
    received = repository.receive_pending_purchase(pending["id"], 1, 1100)
    assert received["remaining_quantity"] == 1
    assert repository.list_holdings()[0]["open_quantity"] == 1


def test_holdings_include_localized_name_and_thumbnail(tmp_path: Path) -> None:
    database = tmp_path / "ledger.db"
    repository = LedgerRepository(database)
    repository.create_purchase("AK-47 | Slate", 1, 100, 1000, "BUFF", False)
    metadata_connection = sqlite3.connect(database)
    with metadata_connection:
        upsert_item_metadata(
            metadata_connection,
            market_hash_name="AK-47 | Slate",
            display_name_zh="AK-47 | 板岩",
            image_url="https://example.test/slate.png",
            source="test",
        )
    metadata_connection.close()

    holding = repository.list_holdings()[0]
    assert holding["display_name"] == "AK-47 | 板岩"
    assert holding["image_url"] == "https://example.test/slate.png"


def test_legacy_item_metadata_import_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "cache.db"
    connection = sqlite3.connect(source)
    connection.executescript("""
    CREATE TABLE zh_names (market_hash TEXT PRIMARY KEY, name TEXT, updated_at INTEGER);
    CREATE TABLE images (market_hash TEXT PRIMARY KEY, img TEXT, updated_at INTEGER);
    INSERT INTO zh_names VALUES('AK-47 | Slate','AK-47 | 板岩',10);
    INSERT INTO images VALUES('AK-47 | Slate','image',11);
    """)
    connection.commit()
    connection.close()
    target = tmp_path / "skinflow.db"

    first = import_legacy_item_metadata(source, target)
    second = import_legacy_item_metadata(source, target)
    connection = sqlite3.connect(target)
    rows = connection.execute("SELECT display_name_zh,image_url FROM item_metadata").fetchall()
    connection.close()

    assert first == second == {"names": 1, "images": 1, "items": 1}
    assert rows == [("AK-47 | 板岩", "image")]
