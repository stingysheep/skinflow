from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from threading import RLock
from uuid import uuid4

from skinflow_api.application.inventory.models import InventoryAsset
from skinflow_api.application.listing.models import (
    ListingContext,
    ListingGatewayResult,
    ListingGroupSelection,
    ListingSelection,
)
from skinflow_api.domain.listing import ListingDecision
from skinflow_api.domain.market.snapshot import MarketSnapshot
from skinflow_api.domain.market.tiers import MarketSide, MarketTier

from .item_metadata import ensure_item_metadata_schema
from .market_trend import ensure_market_trend_schema, read_market_trend, replace_market_trend

SCHEMA = """
CREATE TABLE IF NOT EXISTS listing_preview (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS listing_preview_item (
  id TEXT PRIMARY KEY,
  preview_id TEXT NOT NULL REFERENCES listing_preview(id),
  platform TEXT NOT NULL,
  appid INTEGER NOT NULL,
  contextid TEXT NOT NULL,
  assetid TEXT NOT NULL,
  market_hash_name TEXT NOT NULL,
  market_snapshot_id TEXT NOT NULL,
  market_snapshot_job_id TEXT NOT NULL,
  buyer_pays INTEGER NOT NULL,
  steam_fee INTEGER NOT NULL,
  publisher_fee INTEGER NOT NULL,
  seller_proceeds INTEGER NOT NULL,
  cost_each INTEGER,
  ratio_ppm INTEGER,
  fee_policy_version TEXT NOT NULL,
  UNIQUE(preview_id, platform, appid, contextid, assetid),
  FOREIGN KEY(platform,appid,contextid,assetid)
    REFERENCES inventory_asset(platform,appid,contextid,assetid),
  FOREIGN KEY(market_snapshot_id,market_snapshot_job_id,market_hash_name)
    REFERENCES market_snapshot(id,job_id,market_hash_name)
);
CREATE TABLE IF NOT EXISTS listing_request (
  id TEXT PRIMARY KEY,
  preview_id TEXT NOT NULL REFERENCES listing_preview(id),
  idempotency_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  completed_at INTEGER
);
CREATE TABLE IF NOT EXISTS listing_item (
  id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL REFERENCES listing_request(id),
  preview_item_id TEXT NOT NULL REFERENCES listing_preview_item(id),
  platform TEXT NOT NULL,
  appid INTEGER NOT NULL,
  contextid TEXT NOT NULL,
  assetid TEXT NOT NULL,
  status TEXT NOT NULL,
  steam_listing_id TEXT,
  message TEXT,
  last_checked_at INTEGER,
  sold_at INTEGER,
  sold_receive_total INTEGER,
  sale_fill_id TEXT,
  reconcile_error TEXT,
  UNIQUE(request_id,platform,appid,contextid,assetid)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_listing_per_asset
  ON listing_item(platform,appid,contextid,assetid)
  WHERE status IN (
    'submitting','submitted','pending_confirmation','active','pending_reconciliation'
  );
"""


class SqliteListingRepository:
    def __init__(self, path: str | Path) -> None:
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.executescript(SCHEMA)
        self._ensure_listing_schema()
        ensure_item_metadata_schema(self._connection)
        ensure_market_trend_schema(self._connection)
        self._connection.commit()
        self._lock = RLock()

    def _ensure_listing_schema(self) -> None:
        columns = {
            row[1]
            for row in self._connection.execute(
                "PRAGMA table_info(listing_preview_item)"
            ).fetchall()
        }
        if "market_snapshot_job_id" not in columns:
            self._connection.execute(
                "ALTER TABLE listing_preview_item ADD COLUMN "
                "market_snapshot_job_id TEXT NOT NULL DEFAULT ''"
            )
        item_columns = {
            row[1] for row in self._connection.execute("PRAGMA table_info(listing_item)").fetchall()
        }
        for name, definition in {
            "last_checked_at": "INTEGER",
            "sold_at": "INTEGER",
            "sold_receive_total": "INTEGER",
            "sale_fill_id": "TEXT",
            "reconcile_error": "TEXT",
        }.items():
            if name not in item_columns:
                self._connection.execute(f"ALTER TABLE listing_item ADD COLUMN {name} {definition}")
        self._connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS listing_item_sale_fill "
            "ON listing_item(sale_fill_id) WHERE sale_fill_id IS NOT NULL"
        )
        self._connection.commit()

    def save_listing_snapshot(self, snapshot: MarketSnapshot) -> tuple[str, str]:
        """Persist a public Steam snapshot under a completed listing context job."""
        snapshot_id = str(uuid4())
        job_id = str(uuid4())
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO scan_job("
                "id,status,source_mode,candidate_limit,depth_limit_per_candidate,"
                "operation_mode,acquisition_platforms,min_price,max_price,min_daily_volume,"
                "result_count,next_sequence) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    job_id,
                    "succeeded",
                    "listing_preview",
                    1,
                    10,
                    "listing",
                    "[]",
                    None,
                    None,
                    0,
                    0,
                    1,
                ),
            )
            self._connection.execute(
                "INSERT INTO market_snapshot("
                "id,job_id,market_hash_name,currency,appid,csqaq_observed_at,buff_observed_at,"
                "youpin_observed_at,steam_observed_at,daily_volume_observed_at,daily_volume,"
                "steam_median_price,fee_policy_version) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    snapshot_id,
                    job_id,
                    snapshot.market_hash_name,
                    snapshot.currency,
                    snapshot.appid,
                    snapshot.csqaq_observed_at,
                    snapshot.buff_observed_at,
                    snapshot.youpin_observed_at,
                    snapshot.steam_observed_at,
                    snapshot.daily_volume_observed_at,
                    snapshot.daily_volume,
                    snapshot.steam_median_price,
                    snapshot.fee_policy_version,
                ),
            )
            self._connection.executemany(
                "INSERT INTO market_tier VALUES(?,?,?,?,?)",
                [
                    (snapshot_id, tier.side, position, tier.price, tier.quantity)
                    for position, tier in enumerate(snapshot.tiers)
                ],
            )
        return snapshot_id, job_id

    def save_market_trend(
        self,
        market_hash_name: str,
        good_id: int,
        points: tuple[dict[str, int | None], ...],
        *,
        key: str = "sell_price",
        platform: int = 3,
    ) -> None:
        with self._lock, self._connection:
            replace_market_trend(
                self._connection,
                market_hash_name=market_hash_name,
                good_id=good_id,
                platform=platform,
                data_key=key,
                points=points,
            )

    def read_market_trend(
        self,
        market_hash_name: str,
        *,
        key: str = "sell_price",
        platform: int = 3,
    ) -> list[dict[str, int | str | None]]:
        with self._lock:
            return read_market_trend(
                self._connection,
                market_hash_name,
                platform=platform,
                data_key=key,
            )

    def read_csqaq_good_id(self, market_hash_name: str) -> int | None:
        """Reuse the CSQAQ identity captured in a persisted scan event."""
        import json

        with self._lock:
            rows = self._connection.execute(
                "SELECT payload FROM scan_event WHERE type IN "
                "('result.created','candidate.discovered') "
                "AND json_extract(payload,'$.market_hash_name')=? "
                "ORDER BY rowid DESC LIMIT 5",
                (market_hash_name,),
            ).fetchall()
        for row in rows:
            try:
                good_id = int(json.loads(row[0]).get("good_id") or 0)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if good_id > 0:
                return good_id
        return None

    def read_localized_name(self, market_hash_name: str) -> str | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT display_name_zh FROM item_metadata WHERE market_hash_name=? "
                "ORDER BY updated_at DESC LIMIT 1",
                (market_hash_name,),
            ).fetchone()
        value = str(row[0]).strip() if row and row[0] else ""
        return value or None

    def context_for(self, selection: ListingSelection) -> ListingContext | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM inventory_asset WHERE platform=? AND appid=? "
                "AND contextid=? AND assetid=? AND status='available'",
                (selection.platform, selection.appid, selection.contextid, selection.assetid),
            ).fetchone()
            if row is None:
                return None
            snapshot = self._connection.execute(
                "SELECT id,job_id FROM market_snapshot WHERE market_hash_name=? "
                "AND appid=730 AND currency='CNY' ORDER BY rowid DESC LIMIT 1",
                (row["market_hash_name"],),
            ).fetchone()
            asks = self._asks(snapshot["id"]) if snapshot else ()
            cost_each = self._open_cost_each(row["market_hash_name"])
            active = self._connection.execute(
                "SELECT 1 FROM listing_item WHERE platform=? AND appid=? AND contextid=? "
                "AND assetid=? AND status IN ('submitting','submitted','pending_confirmation',"
                "'active','pending_reconciliation') LIMIT 1",
                (selection.platform, selection.appid, selection.contextid, selection.assetid),
            ).fetchone()
        asset = InventoryAsset(
            row["platform"],
            row["appid"],
            row["contextid"],
            row["assetid"],
            row["market_hash_name"],
            row["display_name"],
            row["image_url"],
            row["classid"],
            row["instanceid"],
            bool(row["marketable"]),
            bool(row["tradable"]),
            row["hold_text"],
            row["wear_text"],
        )
        return ListingContext(
            asset,
            snapshot["id"] if snapshot else None,
            snapshot["job_id"] if snapshot else None,
            asks,
            cost_each,
            bool(active),
        )

    def contexts_for_group(self, selection: ListingGroupSelection) -> tuple[ListingContext, ...]:
        """Resolve identical inventory into deterministic, oldest-first assets."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT platform,appid,contextid,assetid FROM inventory_asset "
                "WHERE platform='steam' AND appid=730 AND market_hash_name=? "
                "AND status='available' AND marketable=1 AND tradable=1 "
                "ORDER BY first_seen_at,rowid",
                (selection.market_hash_name,),
            ).fetchall()
        contexts: list[ListingContext] = []
        for row in rows:
            context = self.context_for(
                ListingSelection(row["platform"], row["appid"], row["contextid"], row["assetid"])
            )
            if context is not None and not context.active_listing:
                contexts.append(context)
        return tuple(contexts)

    def average_cost_for_group(self, market_hash_name: str) -> int | None:
        """Return the integer fen moving average for open ledger inventory."""
        with self._lock:
            row = self._connection.execute(
                "WITH sold AS (SELECT purchase_lot_id,SUM(quantity) quantity "
                "FROM sale_fill GROUP BY purchase_lot_id), "
                "open_lots AS (SELECT l.quantity-COALESCE(s.quantity,0) open_quantity, "
                "l.cost_each FROM purchase_lot l LEFT JOIN sold s "
                "ON s.purchase_lot_id=l.id WHERE l.market_hash_name=? AND l.game='cs2' "
                "AND l.quantity>COALESCE(s.quantity,0)) "
                "SELECT SUM(open_quantity*cost_each) invested,SUM(open_quantity) quantity "
                "FROM open_lots",
                (market_hash_name,),
            ).fetchone()
        if row is None or not row["quantity"]:
            return None
        return int(row["invested"]) // int(row["quantity"])

    def create_preview(self, decisions: tuple[ListingDecision, ...], expires_at: int) -> dict:
        preview_id = str(uuid4())
        created_at = int(time.time() * 1000)
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO listing_preview VALUES(?,?,?,?)",
                (preview_id, "ready", created_at, expires_at),
            )
            for item in decisions:
                self._connection.execute(
                    "INSERT INTO listing_preview_item("
                    "id,preview_id,platform,appid,contextid,assetid,market_hash_name,"
                    "market_snapshot_id,market_snapshot_job_id,buyer_pays,steam_fee,"
                    "publisher_fee,seller_proceeds,cost_each,ratio_ppm,fee_policy_version) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        str(uuid4()),
                        preview_id,
                        item.platform,
                        item.appid,
                        item.contextid,
                        item.assetid,
                        item.market_hash_name,
                        item.snapshot_id,
                        item.snapshot_job_id,
                        item.buyer_pays,
                        item.steam_fee,
                        item.publisher_fee,
                        item.seller_proceeds,
                        item.cost_each,
                        item.ratio_ppm,
                        item.fee_policy_version,
                    ),
                )
        return self.get_preview(preview_id) or {}

    def get_preview(self, preview_id: str) -> dict | None:
        with self._lock:
            preview = self._connection.execute(
                "SELECT * FROM listing_preview WHERE id=?", (preview_id,)
            ).fetchone()
            if preview is None:
                return None
            items = self._connection.execute(
                "SELECT p.*,COALESCE(NULLIF(m.display_name_zh,''),'中文名称待同步') "
                "display_name,i.image_url FROM listing_preview_item p "
                "JOIN inventory_asset i ON i.platform=p.platform AND i.appid=p.appid "
                "AND i.contextid=p.contextid AND i.assetid=p.assetid "
                "LEFT JOIN item_metadata m ON m.market_hash_name=p.market_hash_name "
                "WHERE p.preview_id=? ORDER BY p.rowid",
                (preview_id,),
            ).fetchall()
        output: list[dict] = []
        for item in items:
            payload = dict(item)
            payload["ask_levels"] = self._tiers(item["market_snapshot_id"], MarketSide.STEAM_ASK)
            payload["bid_levels"] = self._tiers(item["market_snapshot_id"], MarketSide.STEAM_BID)
            payload["trend"] = self._trend(item["market_hash_name"])
            output.append(payload)
        return {**dict(preview), "items": output}

    def update_preview_items(self, preview_id: str, updates: tuple[dict, ...]) -> None:
        with self._lock, self._connection:
            for item in updates:
                self._connection.execute(
                    "UPDATE listing_preview_item SET buyer_pays=?,steam_fee=?,"
                    "publisher_fee=?,seller_proceeds=?,ratio_ppm=? "
                    "WHERE preview_id=? AND assetid=?",
                    (
                        item["buyer_pays"],
                        item["steam_fee"],
                        item["publisher_fee"],
                        item["seller_proceeds"],
                        item["ratio_ppm"],
                        preview_id,
                        item["assetid"],
                    ),
                )

    def create_request(self, preview_id: str, idempotency_key: str) -> dict:
        with self._lock, self._connection:
            existing = self._connection.execute(
                "SELECT id FROM listing_request WHERE idempotency_key=?", (idempotency_key,)
            ).fetchone()
            if existing:
                return {**(self.get_request(existing["id"]) or {}), "replayed": True}
            request_id = str(uuid4())
            self._connection.execute(
                "INSERT INTO listing_request VALUES(?,?,?,?,?,NULL)",
                (request_id, preview_id, idempotency_key, "submitting", int(time.time() * 1000)),
            )
            items = self._connection.execute(
                "SELECT id,platform,appid,contextid,assetid FROM listing_preview_item "
                "WHERE preview_id=?",
                (preview_id,),
            ).fetchall()
            for item in items:
                self._connection.execute(
                    "INSERT INTO listing_item("
                    "id,request_id,preview_item_id,platform,appid,contextid,assetid,status,"
                    "steam_listing_id,message,last_checked_at,sold_at,sold_receive_total,"
                    "sale_fill_id,reconcile_error) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        str(uuid4()),
                        request_id,
                        item["id"],
                        item["platform"],
                        item["appid"],
                        item["contextid"],
                        item["assetid"],
                        "submitting",
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                    ),
                )
        return self.get_request(request_id) or {}

    def record_result(self, request_id: str, decision: dict, result: ListingGatewayResult) -> None:
        if result.accepted:
            status = "pending_confirmation" if result.needs_confirmation else "active"
        elif result.message and result.message.startswith("uncertain:"):
            status = "pending_reconciliation"
        else:
            status = "failed"
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE listing_item SET status=?,steam_listing_id=?,message=? "
                "WHERE request_id=? AND platform=? AND appid=? AND contextid=? AND assetid=?",
                (
                    status,
                    result.listing_id,
                    result.message,
                    request_id,
                    decision["platform"],
                    decision["appid"],
                    decision["contextid"],
                    decision["assetid"],
                ),
            )

    def complete_request(self, request_id: str) -> dict:
        with self._lock, self._connection:
            statuses = [
                row[0]
                for row in self._connection.execute(
                    "SELECT status FROM listing_item WHERE request_id=?", (request_id,)
                ).fetchall()
            ]
            if "pending_reconciliation" in statuses:
                status = "pending_reconciliation"
            elif all(item == "failed" for item in statuses):
                status = "failed"
            elif any(item == "failed" for item in statuses):
                status = "partially_submitted"
            else:
                status = "submitted"
            self._connection.execute(
                "UPDATE listing_request SET status=?,completed_at=? WHERE id=?",
                (status, int(time.time() * 1000), request_id),
            )
        return self.get_request(request_id) or {}

    def get_request(self, request_id: str) -> dict | None:
        with self._lock:
            request = self._connection.execute(
                "SELECT * FROM listing_request WHERE id=?", (request_id,)
            ).fetchone()
            if request is None:
                return None
            items = self._connection.execute(
                "SELECT i.*,p.market_hash_name,p.buyer_pays,p.seller_proceeds "
                "FROM listing_item i JOIN listing_preview_item p ON p.id=i.preview_item_id "
                "WHERE i.request_id=? ORDER BY i.rowid",
                (request_id,),
            ).fetchall()
        return {**dict(request), "items": [dict(item) for item in items]}

    def list_reconciliation_items(self) -> list[dict]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT i.*,p.market_hash_name,p.buyer_pays,p.seller_proceeds "
                "FROM listing_item i JOIN listing_preview_item p ON p.id=i.preview_item_id "
                "WHERE i.status IN ('active','pending_confirmation','pending_reconciliation') "
                "ORDER BY i.rowid"
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_checked(self, item_id: str, checked_at: int, error: str | None = None) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE listing_item SET last_checked_at=?,reconcile_error=? WHERE id=?",
                (checked_at, error, item_id),
            )

    def mark_sold(
        self,
        item_id: str,
        sale_fill_id: str,
        sold_at: int,
        receive_total: int,
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE listing_item SET status='sold',sale_fill_id=?,sold_at=?,"
                "sold_receive_total=?,last_checked_at=?,reconcile_error=NULL WHERE id=?",
                (sale_fill_id, sold_at, receive_total, int(time.time() * 1000), item_id),
            )
            self._refresh_request_status(item_id)

    def mark_cancelled(self, item_id: str, checked_at: int) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE listing_item SET status='cancelled',last_checked_at=?,"
                "reconcile_error=NULL WHERE id=?",
                (checked_at, item_id),
            )
            self._refresh_request_status(item_id)

    def mark_active(self, item_id: str, checked_at: int) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE listing_item SET status='active',last_checked_at=?,"
                "reconcile_error=NULL WHERE id=? AND status='pending_confirmation'",
                (checked_at, item_id),
            )

    def _refresh_request_status(self, item_id: str) -> None:
        row = self._connection.execute(
            "SELECT request_id FROM listing_item WHERE id=?", (item_id,)
        ).fetchone()
        if row is None:
            return
        statuses = [
            value[0]
            for value in self._connection.execute(
                "SELECT status FROM listing_item WHERE request_id=?", (row["request_id"],)
            ).fetchall()
        ]
        if statuses and all(status in {"sold", "cancelled", "failed"} for status in statuses):
            request_status = "completed"
        elif any(status == "sold" for status in statuses):
            request_status = "partially_sold"
        else:
            return
        self._connection.execute(
            "UPDATE listing_request SET status=?,completed_at=? WHERE id=?",
            (request_status, int(time.time() * 1000), row["request_id"]),
        )

    def list_requests(self) -> list[dict]:
        with self._lock:
            requests = self._connection.execute(
                "SELECT id,preview_id,idempotency_key,status,created_at,completed_at "
                "FROM listing_request ORDER BY created_at DESC"
            ).fetchall()
            output: list[dict] = []
            for request in requests:
                items = self._connection.execute(
                    "SELECT i.id,i.status,i.assetid,i.steam_listing_id,i.message,i.last_checked_at,"
                    "i.sold_at,i.sold_receive_total,p.market_hash_name,p.buyer_pays,p.seller_proceeds,"
                    "p.cost_each,COALESCE(NULLIF(m.display_name_zh,''),"
                    "'中文名称待同步') display_name,"
                    "COALESCE(m.image_url,'') image_url,COALESCE(a.wear_text,'') wear_text "
                    "FROM listing_item i JOIN listing_preview_item p ON p.id=i.preview_item_id "
                    "LEFT JOIN item_metadata m ON m.market_hash_name=p.market_hash_name "
                    "LEFT JOIN inventory_asset a ON a.platform=i.platform AND a.appid=i.appid "
                    "AND a.contextid=i.contextid AND a.assetid=i.assetid "
                    "WHERE i.request_id=? ORDER BY i.rowid",
                    (request["id"],),
                ).fetchall()
                output.append({**dict(request), "items": [dict(item) for item in items]})
        return output

    def list_cancellable_items(self, item_ids: tuple[str, ...]) -> list[dict]:
        placeholders = ",".join("?" for _ in item_ids)
        with self._lock:
            rows = self._connection.execute(
                "SELECT id,steam_listing_id,status FROM listing_item "
                f"WHERE id IN ({placeholders}) AND status IN ('pending_confirmation','active')",
                item_ids,
            ).fetchall()
        return [dict(row) for row in rows]

    def _asks(self, snapshot_id: str) -> tuple[MarketTier, ...]:
        rows = self._connection.execute(
            "SELECT price,quantity FROM market_tier WHERE snapshot_id=? AND side=? "
            "ORDER BY position",
            (snapshot_id, MarketSide.STEAM_ASK),
        ).fetchall()
        return tuple(
            MarketTier(MarketSide.STEAM_ASK, row["price"], row["quantity"]) for row in rows
        )

    def _tiers(self, snapshot_id: str, side: MarketSide) -> list[dict]:
        rows = self._connection.execute(
            "SELECT price,quantity FROM market_tier WHERE snapshot_id=? AND side=? "
            "ORDER BY position LIMIT 10",
            (snapshot_id, side),
        ).fetchall()
        return [{"price": int(row["price"]), "quantity": int(row["quantity"])} for row in rows]

    def _trend(self, market_hash_name: str) -> list[dict]:
        trend = read_market_trend(self._connection, market_hash_name)
        if trend:
            return trend
        rows = self._connection.execute(
            "SELECT id,csqaq_observed_at,steam_median_price FROM market_snapshot "
            "WHERE market_hash_name=? AND appid=730 AND currency='CNY' "
            "AND steam_median_price IS NOT NULL "
            "ORDER BY COALESCE(csqaq_observed_at,0) DESC LIMIT 30",
            (market_hash_name,),
        ).fetchall()
        return [
            {
                "observed_at": row["csqaq_observed_at"],
                "median_price": row["steam_median_price"],
                "lowest_ask": self._market_price(row["id"], MarketSide.STEAM_ASK, "MIN"),
                "highest_bid": self._market_price(row["id"], MarketSide.STEAM_BID, "MAX"),
                "source": "legacy_snapshot",
            }
            for row in reversed(rows)
        ]

    def _market_price(self, snapshot_id: str, side: str, aggregate: str) -> int | None:
        row = self._connection.execute(
            f"SELECT {aggregate}(price) price FROM market_tier WHERE snapshot_id=? AND side=?",
            (snapshot_id, side),
        ).fetchone()
        return int(row["price"]) if row and row["price"] is not None else None

    def _open_cost_each(self, name: str) -> int | None:
        return self.average_cost_for_group(name)
