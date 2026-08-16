from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import time
from pathlib import Path
from threading import RLock
from uuid import uuid4

from .item_metadata import ensure_item_metadata_schema

LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS migration_run (
  id TEXT PRIMARY KEY,
  source_sha256 TEXT NOT NULL,
  migrator_version TEXT NOT NULL,
  source_schema_fingerprint TEXT NOT NULL,
  status TEXT NOT NULL,
  report_json TEXT NOT NULL DEFAULT '{}',
  started_at INTEGER NOT NULL,
  completed_at INTEGER,
  UNIQUE(source_sha256, migrator_version)
);
CREATE TABLE IF NOT EXISTS purchase_lot (
  id TEXT PRIMARY KEY,
  source_legacy_id INTEGER UNIQUE,
  market_hash_name TEXT NOT NULL,
  game TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK(quantity > 0),
  cost_each INTEGER NOT NULL CHECK(cost_each > 0),
  bought_at INTEGER NOT NULL,
  venue TEXT,
  floor_at_buy INTEGER
);
CREATE TABLE IF NOT EXISTS sale_fill (
  id TEXT PRIMARY KEY,
  source_legacy_id INTEGER UNIQUE,
  purchase_lot_id TEXT NOT NULL REFERENCES purchase_lot(id),
  quantity INTEGER NOT NULL CHECK(quantity > 0),
  receive_total INTEGER NOT NULL CHECK(receive_total >= 0),
  sold_at INTEGER NOT NULL,
  listing_item_id TEXT,
  external_ref TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS pending_purchase (
  id TEXT PRIMARY KEY,
  market_hash_name TEXT NOT NULL,
  game TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK(quantity > 0),
  cost_each INTEGER NOT NULL CHECK(cost_each > 0),
  purchased_at INTEGER NOT NULL,
  venue TEXT,
  status TEXT NOT NULL DEFAULT 'pending'
);
CREATE INDEX IF NOT EXISTS idx_purchase_lot_market ON purchase_lot(market_hash_name);
CREATE INDEX IF NOT EXISTS idx_sale_fill_lot ON sale_fill(purchase_lot_id);
"""


class LedgerRepository:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self._path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._lock = RLock()
        self._connection.executescript(LEDGER_SCHEMA)
        self._ensure_sale_fill_schema()
        ensure_item_metadata_schema(self._connection)
        self._connection.commit()

    def _ensure_sale_fill_schema(self) -> None:
        columns = {
            row[1]
            for row in self._connection.execute("PRAGMA table_info(sale_fill)").fetchall()
        }
        for name, definition in {
            "listing_item_id": "TEXT",
            "external_ref": "TEXT",
        }.items():
            if name not in columns:
                self._connection.execute(f"ALTER TABLE sale_fill ADD COLUMN {name} {definition}")
        self._connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS sale_fill_listing_item "
            "ON sale_fill(listing_item_id) WHERE listing_item_id IS NOT NULL"
        )
        self._connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS sale_fill_external_ref "
            "ON sale_fill(external_ref) WHERE external_ref IS NOT NULL"
        )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def list_holdings(self) -> list[dict]:
        with self._lock:
            wear_select, wear_join, wear_group = self._wear_sql()
            rows = self._connection.execute(
                "WITH fill_totals AS (SELECT purchase_lot_id,SUM(quantity) quantity "
                "FROM sale_fill GROUP BY purchase_lot_id) "
                "SELECT l.market_hash_name,l.game,m.display_name_zh,m.image_url,"
                "SUM(l.quantity) quantity,"
                "SUM(l.quantity*l.cost_each) invested,"
                "SUM(COALESCE(f.quantity,0)) sold,"
                "SUM((l.quantity-COALESCE(f.quantity,0))*l.cost_each) open_cost,"
                f"COUNT(l.id) lots,{wear_select} wear_text FROM purchase_lot l "
                "LEFT JOIN fill_totals f ON f.purchase_lot_id=l.id "
                "LEFT JOIN item_metadata m ON m.market_hash_name=l.market_hash_name "
                f"{wear_join}"
                f"GROUP BY l.market_hash_name,l.game,m.display_name_zh,m.image_url{wear_group} "
                "ORDER BY COALESCE(NULLIF(m.display_name_zh,''),l.market_hash_name)"
            ).fetchall()
        return [self._holding(row) for row in rows if row["quantity"] - row["sold"] > 0]

    def list_history(self) -> list[dict]:
        with self._lock:
            wear_select, wear_join, _ = self._wear_sql()
            rows = self._connection.execute(
                "SELECT f.id,f.purchase_lot_id,f.quantity,f.receive_total,f.sold_at,"
                "f.listing_item_id,f.external_ref,l.market_hash_name,"
                "COALESCE(NULLIF(m.display_name_zh,''),'中文名称待同步') display_name,"
                "COALESCE(m.image_url,'') image_url,"
                f"l.cost_each,f.quantity*l.cost_each cost_total,{wear_select} "
                "wear_text,CASE WHEN f.listing_item_id IS NULL THEN 'manual' "
                "ELSE 'automatic' END source FROM sale_fill f "
                "JOIN purchase_lot l ON l.id=f.purchase_lot_id "
                "LEFT JOIN item_metadata m ON m.market_hash_name=l.market_hash_name "
                f"{wear_join}"
                "ORDER BY f.sold_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def _wear_sql(self) -> tuple[str, str, str]:
        exists = self._connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='inventory_asset'"
        ).fetchone()
        if not exists:
            return "NULL", "", ""
        columns = {
            row[1]
            for row in self._connection.execute("PRAGMA table_info(inventory_asset)").fetchall()
        }
        if "wear_text" not in columns:
            return "NULL", "", ""
        join = (
            "LEFT JOIN (SELECT market_hash_name, "
            "CASE WHEN COUNT(DISTINCT NULLIF(wear_text,''))=1 THEN MAX(wear_text) "
            "WHEN COUNT(DISTINCT NULLIF(wear_text,''))>1 THEN '多种磨损' END wear_text "
            "FROM inventory_asset GROUP BY market_hash_name) w "
            "ON w.market_hash_name=l.market_hash_name "
        )
        return "w.wear_text", join, ",w.wear_text"

    def migration_status(self) -> list[dict]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id,source_sha256,migrator_version,status,report_json,"
                "started_at,completed_at "
                "FROM migration_run ORDER BY started_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def list_pending_purchases(self) -> list[dict]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT p.id,p.market_hash_name,p.game,p.quantity,p.cost_each,p.purchased_at,"
                "p.venue,p.status,"
                "COALESCE(NULLIF(m.display_name_zh,''),'中文名称待同步') display_name,"
                "COALESCE(m.image_url,'') image_url FROM pending_purchase p "
                "LEFT JOIN item_metadata m ON m.market_hash_name=p.market_hash_name "
                "WHERE p.status='pending' ORDER BY p.purchased_at"
            ).fetchall()
        return [dict(row) for row in rows]

    def search_catalog(self, query: str, limit: int = 20) -> list[dict]:
        normalized = query.strip()
        like = f"%{normalized}%"
        with self._lock:
            rows = self._connection.execute(
                "SELECT m.market_hash_name,m.display_name_zh display_name,m.image_url,"
                "COALESCE(h.open_quantity,0) open_quantity "
                "FROM item_metadata m LEFT JOIN ("
                "SELECT l.market_hash_name,SUM(l.quantity-COALESCE(f.quantity,0)) open_quantity "
                "FROM purchase_lot l LEFT JOIN (SELECT purchase_lot_id,SUM(quantity) quantity "
                "FROM sale_fill GROUP BY purchase_lot_id) f ON f.purchase_lot_id=l.id "
                "GROUP BY l.market_hash_name) h ON h.market_hash_name=m.market_hash_name "
                "WHERE (?='' OR m.market_hash_name LIKE ? OR m.display_name_zh LIKE ?) "
                "ORDER BY CASE WHEN m.display_name_zh LIKE ? THEN 0 ELSE 1 END,display_name "
                "LIMIT ?",
                (normalized, like, like, like, max(1, min(limit, 50))),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_purchase(
        self,
        market_hash_name: str,
        quantity: int,
        cost_each: int,
        purchased_at: int,
        venue: str | None,
        pending_delivery: bool,
    ) -> dict:
        self._validate_purchase(market_hash_name, quantity, cost_each, purchased_at)
        identifier = str(uuid4())
        with self._lock, self._connection:
            if pending_delivery:
                self._connection.execute(
                    "INSERT INTO pending_purchase VALUES(?,?,?,?,?,?,?,?)",
                    (
                        identifier,
                        market_hash_name,
                        "cs2",
                        quantity,
                        cost_each,
                        purchased_at,
                        venue,
                        "pending",
                    ),
                )
                return {"id": identifier, "status": "pending_delivery"}
            self._connection.execute(
                "INSERT INTO purchase_lot VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    None,
                    market_hash_name,
                    "cs2",
                    quantity,
                    cost_each,
                    purchased_at,
                    venue,
                    None,
                ),
            )
        return {"id": identifier, "status": "received"}

    def receive_pending_purchase(self, pending_id: str, quantity: int, received_at: int) -> dict:
        if quantity < 1:
            raise ValueError("received quantity must be positive")
        with self._lock, self._connection:
            pending = self._connection.execute(
                "SELECT * FROM pending_purchase WHERE id=? AND status='pending'", (pending_id,)
            ).fetchone()
            if pending is None:
                raise LookupError("pending purchase not found")
            if quantity > pending["quantity"]:
                raise ValueError("received quantity exceeds pending purchase quantity")
            lot_id = str(uuid4())
            self._connection.execute(
                "INSERT INTO purchase_lot VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    lot_id,
                    None,
                    pending["market_hash_name"],
                    pending["game"],
                    quantity,
                    pending["cost_each"],
                    received_at,
                    pending["venue"],
                    None,
                ),
            )
            remaining = int(pending["quantity"]) - quantity
            if remaining:
                self._connection.execute(
                    "UPDATE pending_purchase SET quantity=? WHERE id=?", (remaining, pending_id)
                )
            else:
                self._connection.execute(
                    "UPDATE pending_purchase SET status='received' WHERE id=?", (pending_id,)
                )
        return {"lot_id": lot_id, "remaining_quantity": remaining}

    def record_sale(
        self,
        market_hash_name: str,
        quantity: int,
        receive_total: int,
        sold_at: int,
    ) -> dict:
        if not market_hash_name or quantity < 1 or receive_total < 0 or sold_at < 1:
            raise ValueError("invalid sale input")
        with self._lock, self._connection:
            lots = self._connection.execute(
                "WITH fill_totals AS (SELECT purchase_lot_id,SUM(quantity) quantity "
                "FROM sale_fill GROUP BY purchase_lot_id) "
                "SELECT l.id,l.quantity,l.cost_each,COALESCE(f.quantity,0) sold_quantity "
                "FROM purchase_lot l LEFT JOIN fill_totals f ON f.purchase_lot_id=l.id "
                "WHERE l.market_hash_name=? AND l.game='cs2' "
                "ORDER BY l.bought_at,l.id",
                (market_hash_name,),
            ).fetchall()
            available = sum(int(lot["quantity"]) - int(lot["sold_quantity"]) for lot in lots)
            if quantity > available:
                raise ValueError(f"insufficient inventory: {available} available")
            planned: list[tuple[str, int]] = []
            remaining = quantity
            for lot in lots:
                take = min(remaining, int(lot["quantity"]) - int(lot["sold_quantity"]))
                if take:
                    planned.append((str(lot["id"]), take))
                    remaining -= take
                if not remaining:
                    break
            fills: list[dict] = []
            allocated = 0
            for index, (lot_id, fill_quantity) in enumerate(planned):
                part = (
                    receive_total - allocated
                    if index == len(planned) - 1
                    else (receive_total * fill_quantity) // quantity
                )
                allocated += part
                fill_id = str(uuid4())
                self._connection.execute(
                    "INSERT INTO sale_fill(" 
                    "id,source_legacy_id,purchase_lot_id,quantity,receive_total,sold_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (fill_id, None, lot_id, fill_quantity, part, sold_at),
                )
                fills.append(
                    {
                        "id": fill_id,
                        "purchase_lot_id": lot_id,
                        "quantity": fill_quantity,
                        "receive_total": part,
                    }
                )
        return {"quantity": quantity, "receive_total": receive_total, "fills": fills}

    def record_external_sale(
        self,
        *,
        market_hash_name: str,
        quantity: int,
        receive_total: int,
        sold_at: int,
        listing_item_id: str,
        external_ref: str,
    ) -> dict:
        """Record a Steam fill once; retries return the original allocation."""
        with self._lock:
            existing = self._connection.execute(
                "SELECT id,quantity,receive_total FROM sale_fill "
                "WHERE listing_item_id=? OR external_ref=? LIMIT 1",
                (listing_item_id, external_ref),
            ).fetchone()
            if existing is not None:
                return {
                    "idempotent": True,
                    "fill_id": existing["id"],
                    "quantity": existing["quantity"],
                    "receive_total": existing["receive_total"],
                }
            result = self._record_sale_allocations(
                market_hash_name, quantity, receive_total, sold_at,
                listing_item_id, external_ref,
            )
        return result

    def _record_sale_allocations(
        self,
        market_hash_name: str,
        quantity: int,
        receive_total: int,
        sold_at: int,
        listing_item_id: str,
        external_ref: str,
    ) -> dict:
        if not market_hash_name or quantity < 1 or receive_total < 0 or sold_at < 1:
            raise ValueError("invalid sale input")
        with self._connection:
            lots = self._connection.execute(
                "WITH fill_totals AS (SELECT purchase_lot_id,SUM(quantity) quantity "
                "FROM sale_fill GROUP BY purchase_lot_id) "
                "SELECT l.id,l.quantity,l.cost_each,COALESCE(f.quantity,0) sold_quantity "
                "FROM purchase_lot l LEFT JOIN fill_totals f ON f.purchase_lot_id=l.id "
                "WHERE l.market_hash_name=? AND l.game='cs2' ORDER BY l.bought_at,l.id",
                (market_hash_name,),
            ).fetchall()
            available = sum(int(lot["quantity"]) - int(lot["sold_quantity"]) for lot in lots)
            if quantity > available:
                raise ValueError(f"insufficient inventory: {available} available")
            planned: list[tuple[str, int]] = []
            remaining = quantity
            for lot in lots:
                take = min(remaining, int(lot["quantity"]) - int(lot["sold_quantity"]))
                if take:
                    planned.append((str(lot["id"]), take))
                    remaining -= take
                if not remaining:
                    break
            fills: list[dict] = []
            allocated = 0
            for index, (lot_id, fill_quantity) in enumerate(planned):
                part = (
                    receive_total - allocated
                    if index == len(planned) - 1
                    else (receive_total * fill_quantity) // quantity
                )
                allocated += part
                fill_id = str(uuid4())
                self._connection.execute(
                    "INSERT INTO sale_fill(" 
                    "id,source_legacy_id,purchase_lot_id,quantity,receive_total,sold_at,"
                    "listing_item_id,external_ref) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        fill_id, None, lot_id, fill_quantity, part, sold_at,
                        listing_item_id, external_ref,
                    ),
                )
                fills.append(
                    {
                        "id": fill_id,
                        "purchase_lot_id": lot_id,
                        "quantity": fill_quantity,
                        "receive_total": part,
                    }
                )
        return {
            "idempotent": False,
            "quantity": quantity,
            "receive_total": receive_total,
            "fills": fills,
            "fill_id": fills[0]["id"],
        }

    @staticmethod
    def _validate_purchase(name: str, quantity: int, cost_each: int, timestamp: int) -> None:
        if not name.strip() or quantity < 1 or cost_each < 1 or timestamp < 1:
            raise ValueError("invalid purchase input")

    @staticmethod
    def _holding(row: sqlite3.Row) -> dict:
        quantity = int(row["quantity"])
        sold = int(row["sold"])
        open_quantity = quantity - sold
        return {
            "market_hash_name": row["market_hash_name"],
            "display_name": row["display_name_zh"] or "中文名称待同步",
            "image_url": row["image_url"] or "",
            "game": row["game"],
            "quantity": quantity,
            "sold_quantity": sold,
            "open_quantity": open_quantity,
            "invested": int(row["invested"]),
            "open_cost": int(row["open_cost"]),
            "lots": int(row["lots"]),
            "wear_text": row["wear_text"],
        }


def migrate_legacy_ledger(source: str | Path, target: str | Path, version: str = "v1") -> dict:
    source_path = Path(source)
    target_path = Path(target)
    source_bytes = source_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    source_connection = sqlite3.connect(source_path)
    source_connection.row_factory = sqlite3.Row
    tables = tuple(row[0] for row in source_connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ))
    fingerprint = hashlib.sha256("|".join(tables).encode()).hexdigest()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(LEDGER_SCHEMA)
    existing = connection.execute(
        "SELECT status FROM migration_run WHERE source_sha256=? AND migrator_version=?",
        (source_sha256, version),
    ).fetchone()
    if existing and existing[0] == "completed":
        source_connection.close()
        connection.close()
        return {"status": "already_completed", "source_sha256": source_sha256}
    run_id = str(uuid4())
    started_at = int(time.time())
    connection.execute(
        "INSERT INTO migration_run VALUES(?,?,?,?,?,?,?,NULL)",
        (run_id, source_sha256, version, fingerprint, "running", "{}", started_at),
    )
    connection.commit()
    backup = source_path.with_name(f"{source_path.name}.bak-migration-{source_sha256[:12]}")
    if not backup.exists():
        shutil.copy2(source_path, backup)
    try:
        lots = source_connection.execute("SELECT * FROM lots ORDER BY id").fetchall()
        fills = source_connection.execute("SELECT * FROM fills ORDER BY id").fetchall()
        for lot in lots:
            connection.execute(
                "INSERT INTO purchase_lot VALUES(?,?,?,?,?,?,?,?,?)",
                (f"legacy-lot-{lot['id']}", lot["id"], lot["market_hash"], lot["game"],
                 lot["qty"], lot["cost_each"], lot["bought_at"], lot["venue"], lot["floor_at_buy"]),
            )
        for fill in fills:
            connection.execute(
                "INSERT INTO sale_fill(" 
                "id,source_legacy_id,purchase_lot_id,quantity,receive_total,sold_at) "
                "VALUES(?,?,?,?,?,?)",
                (f"legacy-fill-{fill['id']}", fill["id"], f"legacy-lot-{fill['lot_id']}",
                 fill["qty"], fill["receive_total"], fill["sold_at"]),
            )
        report = {"lots": len(lots), "fills": len(fills), "backup": str(backup)}
        connection.execute(
            "UPDATE migration_run SET status='completed',report_json=?,completed_at=? WHERE id=?",
            (json.dumps(report, ensure_ascii=False), int(time.time()), run_id),
        )
        connection.commit()
        return {"status": "completed", "source_sha256": source_sha256, **report}
    except Exception as error:
        connection.rollback()
        connection.execute(
            "UPDATE migration_run SET status='failed',report_json=?,completed_at=? WHERE id=?",
            (json.dumps({"error": type(error).__name__}), int(time.time()), run_id),
        )
        connection.commit()
        raise
    finally:
        source_connection.close()
        connection.close()
