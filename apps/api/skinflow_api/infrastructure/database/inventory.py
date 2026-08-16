from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from threading import RLock
from uuid import uuid4

from skinflow_api.application.inventory.models import InventoryAsset, InventoryRefreshResult

from .item_metadata import ensure_item_metadata_schema, upsert_item_metadata
from .market_trend import ensure_market_trend_schema, read_market_trend

SCHEMA = """
CREATE TABLE IF NOT EXISTS inventory_sync_run (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  observed_at INTEGER NOT NULL,
  asset_count INTEGER NOT NULL DEFAULT 0,
  failure_code TEXT
);
CREATE TABLE IF NOT EXISTS inventory_asset (
  platform TEXT NOT NULL,
  appid INTEGER NOT NULL,
  contextid TEXT NOT NULL,
  assetid TEXT NOT NULL,
  market_hash_name TEXT NOT NULL,
  display_name TEXT NOT NULL,
  image_url TEXT NOT NULL,
  classid TEXT NOT NULL,
  instanceid TEXT NOT NULL,
  marketable INTEGER NOT NULL,
  tradable INTEGER NOT NULL,
  hold_text TEXT,
  wear_text TEXT,
  tradable_after INTEGER,
  status TEXT NOT NULL,
  first_seen_at INTEGER NOT NULL,
  last_seen_at INTEGER NOT NULL,
  PRIMARY KEY(platform, appid, contextid, assetid)
);
CREATE INDEX IF NOT EXISTS idx_inventory_asset_name ON inventory_asset(market_hash_name);
"""


class SqliteInventoryRepository:
    def __init__(self, path: str | Path) -> None:
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.executescript(SCHEMA)
        self._ensure_inventory_schema()
        ensure_item_metadata_schema(self._connection)
        ensure_market_trend_schema(self._connection)
        self._connection.commit()
        self._lock = RLock()

    def _ensure_inventory_schema(self) -> None:
        columns = {
            row[1]
            for row in self._connection.execute("PRAGMA table_info(inventory_asset)").fetchall()
        }
        if "wear_text" not in columns:
            self._connection.execute("ALTER TABLE inventory_asset ADD COLUMN wear_text TEXT")
        if "tradable_after" not in columns:
            self._connection.execute(
                "ALTER TABLE inventory_asset ADD COLUMN tradable_after INTEGER"
            )

    def sync(self, assets: tuple[InventoryAsset, ...]) -> InventoryRefreshResult:
        now = int(time.time() * 1000)
        run_id = str(uuid4())
        keys = {(item.platform, item.appid, item.contextid, item.assetid) for item in assets}
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO inventory_sync_run(id,status,observed_at) VALUES(?,?,?)",
                (run_id, "running", now),
            )
            for item in assets:
                upsert_item_metadata(
                    self._connection,
                    market_hash_name=item.market_hash_name,
                    display_name_zh=item.display_name,
                    image_url=item.image_url,
                    source="steam_inventory",
                    updated_at=now,
                )
                self._connection.execute(
                    "INSERT INTO inventory_asset(" 
                    "platform,appid,contextid,assetid,market_hash_name,display_name,image_url," 
                    "classid,instanceid,marketable,tradable,hold_text,wear_text,"
                    "tradable_after,status,first_seen_at,last_seen_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(platform,appid,contextid,assetid) DO UPDATE SET "
                    "market_hash_name=excluded.market_hash_name,display_name=excluded.display_name,"
                    "image_url=excluded.image_url,classid=excluded.classid,instanceid=excluded.instanceid,"
                    "marketable=excluded.marketable,tradable=excluded.tradable,hold_text=excluded.hold_text,"
                    "wear_text=excluded.wear_text,tradable_after=excluded.tradable_after,"
                    "status=CASE WHEN inventory_asset.status='listed' THEN 'listed' "
                    "ELSE 'available' END,last_seen_at=excluded.last_seen_at",
                    (
                        item.platform,
                        item.appid,
                        item.contextid,
                        item.assetid,
                        item.market_hash_name,
                        item.display_name,
                        item.image_url,
                        item.classid,
                        item.instanceid,
                        int(item.marketable),
                        int(item.tradable),
                        item.hold_text,
                        item.wear_text,
                        item.tradable_after,
                        "available",
                        now,
                        now,
                    ),
                )
            previous = self._connection.execute(
                "SELECT platform,appid,contextid,assetid FROM inventory_asset "
                "WHERE status='available'"
            ).fetchall()
            missing = [tuple(row) for row in previous if tuple(row) not in keys]
            if missing:
                self._connection.executemany(
                    "UPDATE inventory_asset SET status='missing' WHERE platform=? AND appid=? "
                    "AND contextid=? AND assetid=?",
                    missing,
                )
            self._connection.execute(
                "UPDATE inventory_sync_run SET status='succeeded',asset_count=? WHERE id=?",
                (len(assets), run_id),
            )
        return InventoryRefreshResult(run_id, len(assets), now)

    def record_failure(self, failure_code: str) -> None:
        now = int(time.time() * 1000)
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO inventory_sync_run(id,status,observed_at,failure_code) "
                "VALUES(?,?,?,?)",
                (str(uuid4()), "failed", now, failure_code),
            )

    def list_assets(self) -> list[dict]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT a.*,COALESCE(NULLIF(m.display_name_zh,''),'中文名称待同步') "
                "localized_name FROM inventory_asset a LEFT JOIN item_metadata m "
                "ON m.market_hash_name=a.market_hash_name "
                "ORDER BY a.status,localized_name,a.assetid"
            ).fetchall()
        return [
            {
                **dict(row),
                "display_name": row["localized_name"],
                "marketable": bool(row["marketable"]),
                "tradable": bool(row["tradable"]),
            }
            for row in rows
        ]

    def list_grouped_assets(self) -> list[dict]:
        with self._lock:
            rows = self._connection.execute(
                "WITH sold AS (SELECT purchase_lot_id,SUM(quantity) quantity "
                "FROM sale_fill GROUP BY purchase_lot_id), "
                "costs AS (SELECT l.market_hash_name, "
                "SUM((l.quantity-COALESCE(s.quantity,0))*l.cost_each) invested, "
                "SUM(l.quantity-COALESCE(s.quantity,0)) quantity "
                "FROM purchase_lot l LEFT JOIN sold s ON s.purchase_lot_id=l.id "
                "WHERE l.quantity>COALESCE(s.quantity,0) GROUP BY l.market_hash_name), "
                "inventory_current AS (SELECT * FROM inventory_asset WHERE "
                "status IN ('available','listed') AND NOT (status='available' AND "
                "COALESCE(hold_text,'') LIKE '%已在 Steam 社区市场挂售%')), "
                "asset_groups AS (SELECT market_hash_name,"
                "SUM(CASE WHEN status IN ('available','listed') THEN 1 ELSE 0 END) total_quantity, "
                "SUM(CASE WHEN status='available' THEN 1 ELSE 0 END) available_quantity, "
                "SUM(CASE WHEN status='listed' THEN 1 ELSE 0 END) listed_quantity, "
                "SUM(CASE WHEN status='available' AND marketable=1 "
                "THEN 1 ELSE 0 END) marketable_quantity, "
                "SUM(CASE WHEN status='available' AND marketable=1 "
                "AND tradable=1 THEN 1 ELSE 0 END) tradable_quantity, "
                "CASE WHEN COUNT(DISTINCT NULLIF(wear_text,''))=1 THEN MAX(wear_text) "
                "WHEN COUNT(DISTINCT NULLIF(wear_text,''))>1 THEN '多种磨损' END wear_text "
                "FROM inventory_current GROUP BY market_hash_name), "
                "names AS (SELECT market_hash_name FROM asset_groups "
                "UNION SELECT market_hash_name FROM costs) "
                "SELECT n.market_hash_name, "
                "COALESCE(NULLIF(m.display_name_zh,''),'中文名称待同步') localized_name, "
                "COALESCE(m.image_url,'') image_url,COALESCE(a.total_quantity,0) total_quantity, "
                "COALESCE(a.available_quantity,0) available_quantity, "
                "COALESCE(a.listed_quantity,0) listed_quantity, "
                "COALESCE(a.marketable_quantity,0) marketable_quantity, "
                "COALESCE(a.tradable_quantity,0) tradable_quantity, "
                "CASE WHEN c.quantity>0 THEN c.invested / c.quantity END average_cost, "
                "COALESCE(c.quantity,0) held_quantity, a.wear_text "
                "FROM names n LEFT JOIN asset_groups a ON a.market_hash_name=n.market_hash_name "
                "LEFT JOIN item_metadata m ON m.market_hash_name=n.market_hash_name "
                "LEFT JOIN costs c ON c.market_hash_name=n.market_hash_name "
                "WHERE COALESCE(a.total_quantity,0)>0 OR COALESCE(c.quantity,0)>0 "
                "ORDER BY localized_name,n.market_hash_name"
            ).fetchall()
            batch_rows = self._connection.execute(
                "SELECT market_hash_name,tradable_after,hold_text,COUNT(*) quantity "
                "FROM inventory_asset WHERE status='available' AND tradable=0 "
                "AND COALESCE(hold_text,'') NOT LIKE '%已在 Steam 社区市场挂售%' "
                "GROUP BY market_hash_name,tradable_after,hold_text "
                "ORDER BY market_hash_name,tradable_after IS NULL,tradable_after"
            ).fetchall()
        batches: dict[str, list[dict]] = {}
        for row in batch_rows:
            batches.setdefault(row["market_hash_name"], []).append(
                {
                    "tradable_after": (
                        int(row["tradable_after"])
                        if row["tradable_after"] is not None
                        else None
                    ),
                    "quantity": int(row["quantity"]),
                    "hold_text": row["hold_text"],
                }
            )
        return [
            {
                **dict(row),
                "display_name": row["localized_name"],
                "total_quantity": int(row["total_quantity"]),
                "available_quantity": int(row["available_quantity"]),
                "listed_quantity": int(row["listed_quantity"]),
                "marketable_quantity": int(row["marketable_quantity"]),
                "tradable_quantity": int(row["tradable_quantity"]),
                "average_cost": (
                    int(row["average_cost"]) if row["average_cost"] is not None else None
                ),
                "held_quantity": int(row["held_quantity"] or 0),
                "wear_text": row["wear_text"],
                "cooldown_batches": batches.get(row["market_hash_name"], []),
            }
            for row in rows
        ]

    def get_group_details(self, market_hash_name: str) -> dict | None:
        """Return the latest Steam book and recent stored market observations."""
        with self._lock:
            try:
                group = self._connection.execute(
                    "SELECT a.market_hash_name,"
                    "COALESCE(NULLIF(m.display_name_zh,''),'中文名称待同步') localized_name,"
                    "COALESCE(m.image_url,'') image_url "
                    "FROM (SELECT market_hash_name FROM inventory_asset UNION "
                    "SELECT market_hash_name FROM purchase_lot) a LEFT JOIN item_metadata m "
                    "ON m.market_hash_name=a.market_hash_name "
                    "WHERE a.market_hash_name=? "
                    "GROUP BY a.market_hash_name,localized_name,m.image_url",
                    (market_hash_name,),
                ).fetchone()
            except sqlite3.OperationalError as error:
                if "purchase_lot" not in str(error):
                    raise
                group = self._connection.execute(
                    "SELECT a.market_hash_name,"
                    "COALESCE(NULLIF(m.display_name_zh,''),'中文名称待同步') localized_name,"
                    "COALESCE(m.image_url,'') image_url FROM inventory_asset a "
                    "LEFT JOIN item_metadata m ON m.market_hash_name=a.market_hash_name "
                    "WHERE a.market_hash_name=? "
                    "GROUP BY a.market_hash_name,localized_name,m.image_url",
                    (market_hash_name,),
                ).fetchone()
            if group is None:
                return None
            try:
                snapshots = self._connection.execute(
                    "SELECT id,csqaq_observed_at,steam_observed_at,steam_median_price "
                    "FROM market_snapshot WHERE market_hash_name=? AND appid=730 "
                    "AND currency='CNY' "
                    "ORDER BY COALESCE(csqaq_observed_at,steam_observed_at,0) DESC LIMIT 30",
                    (market_hash_name,),
                ).fetchall()
            except sqlite3.OperationalError:
                snapshots = []
            current = snapshots[0] if snapshots else None
            asks = self._market_levels(current["id"] if current else None, "steam_ask")
            bids = self._market_levels(current["id"] if current else None, "steam_bid")
            trend = read_market_trend(self._connection, market_hash_name)
            if not trend:
                # Keep legacy snapshots readable for migrations, but the UI
                # labels these separately and never presents them as CSQAQ data.
                trend = [
                    {
                        "observed_at": row["csqaq_observed_at"] or row["steam_observed_at"],
                        "median_price": row["steam_median_price"],
                        "lowest_ask": self._market_price(row["id"], "steam_ask", "MIN"),
                        "highest_bid": self._market_price(row["id"], "steam_bid", "MAX"),
                        "source": "legacy_snapshot",
                    }
                    for row in reversed(snapshots)
                ]
            average = self._average_cost_for_group_locked(market_hash_name)
        return {
            "market_hash_name": group["market_hash_name"],
            "display_name": group["localized_name"],
            "image_url": group["image_url"],
            "average_cost": average,
            "current": {
                "observed_at": current["steam_observed_at"] if current else None,
                "lowest_ask": asks[0]["price"] if asks else None,
                "highest_bid": bids[0]["price"] if bids else None,
                "ask_levels": asks,
                "bid_levels": bids,
            },
            "trend": trend,
        }

    def _market_levels(self, snapshot_id: str | None, side: str) -> list[dict]:
        if snapshot_id is None:
            return []
        try:
            rows = self._connection.execute(
                "SELECT price,quantity FROM market_tier WHERE snapshot_id=? AND side=? "
                "ORDER BY position LIMIT 10",
                (snapshot_id, side),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [{"price": int(row["price"]), "quantity": int(row["quantity"])} for row in rows]

    def _market_price(self, snapshot_id: str, side: str, aggregate: str) -> int | None:
        try:
            row = self._connection.execute(
                f"SELECT {aggregate}(price) price FROM market_tier WHERE snapshot_id=? AND side=?",
                (snapshot_id, side),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        return int(row["price"]) if row and row["price"] is not None else None

    def _average_cost_for_group_locked(self, market_hash_name: str) -> int | None:
        try:
            row = self._connection.execute(
                "WITH sold AS (SELECT purchase_lot_id,SUM(quantity) quantity "
                "FROM sale_fill GROUP BY purchase_lot_id), open_lots AS ("
                "SELECT l.quantity-COALESCE(s.quantity,0) open_quantity,l.cost_each "
                "FROM purchase_lot l LEFT JOIN sold s ON s.purchase_lot_id=l.id "
                "WHERE l.market_hash_name=? AND l.game='cs2' "
                "AND l.quantity>COALESCE(s.quantity,0)) "
                "SELECT SUM(open_quantity*cost_each) invested,SUM(open_quantity) quantity "
                "FROM open_lots",
                (market_hash_name,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        if row is None or not row["quantity"]:
            return None
        return int(row["invested"]) // int(row["quantity"])
