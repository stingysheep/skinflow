import json
import sqlite3
from pathlib import Path
from threading import RLock
from uuid import uuid4

from skinflow_api.application.scan.models import (
    AcquisitionPlatform,
    ScanJob,
    ScanMode,
    ScanStatus,
)
from skinflow_api.domain.market.snapshot import MarketSnapshot
from skinflow_api.domain.pricing.curves import CurvePoint

from .item_metadata import ensure_item_metadata_schema, upsert_item_metadata
from .scan_schema import ensure_scan_schema


class SqliteScanUnitOfWork:
    def __init__(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._lock = RLock()
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA busy_timeout = 5000")
        ensure_scan_schema(self._connection)
        ensure_item_metadata_schema(self._connection)
        self._drop_legacy_active_index()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def has_active_job(self) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM scan_job WHERE status IN ('queued','running','cancelling') LIMIT 1"
            ).fetchone()
        return row is not None

    def recover_interrupted_jobs(self) -> int:
        with self._lock, self._connection:
            rows = self._connection.execute(
                "SELECT id,status,next_sequence FROM scan_job "
                "WHERE status IN ('queued','running','cancelling') ORDER BY rowid"
            ).fetchall()
            for row in rows:
                failed = row["status"] in {"queued", "running"}
                status = "failed" if failed else "cancelled"
                failure_code = "APP_RESTARTED" if failed else None
                event_type = "job.failed" if failed else "job.cancelled"
                sequence = row["next_sequence"]
                self._connection.execute(
                    "UPDATE scan_job SET status=?,failure_code=?,next_sequence=?,version=version+1 "
                    "WHERE id=?",
                    (status, failure_code, sequence + 1, row["id"]),
                )
                self._write_event(
                    row["id"], sequence, event_type, {"reason_code": "APP_RESTARTED"}
                )
        return len(rows)

    def enforce_single_active_job(self) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS one_active_scan "
                "ON scan_job((1)) WHERE status IN ('queued','running','cancelling')"
            )

    def create_job(self, job: ScanJob) -> None:
        try:
            with self._lock, self._connection:
                self._connection.execute(
                    "INSERT INTO scan_job("
                    "id,status,source_mode,candidate_limit,depth_limit_per_candidate,"
                    "operation_mode,acquisition_platforms,min_price,max_price,min_daily_volume"
                    ") VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        job.id,
                        job.status,
                        job.request.source_mode,
                        job.request.candidate_limit,
                        10,
                        job.request.operation_mode,
                        json.dumps(job.request.acquisition_platforms),
                        job.request.min_price,
                        job.request.max_price,
                        job.request.min_daily_volume,
                    ),
                )
                self._write_event(job.id, 1, "job.created", {})
                self._connection.execute(
                    "UPDATE scan_job SET next_sequence=2 WHERE id=?",
                    (job.id,),
                )
                job.next_sequence = 2
        except sqlite3.IntegrityError as error:
            raise ValueError("an active scan already exists") from error

    def persist_result_and_event(
        self,
        job: ScanJob,
        snapshot: MarketSnapshot | None = None,
        curves: tuple[CurvePoint, ...] = (),
        event_type: str = "result.created",
        payload: dict | None = None,
    ) -> None:
        with self._lock, self._connection:
            next_sequence = self._next_sequence(job.id)
            snapshot_id = None
            if snapshot is not None:
                snapshot_id = str(uuid4())
                self._insert_snapshot(snapshot_id, job.id, snapshot)
                self._insert_curves(snapshot_id, curves)
                result = payload or {}
                upsert_item_metadata(
                    self._connection,
                    market_hash_name=snapshot.market_hash_name,
                    display_name_zh=str(result.get("name") or snapshot.market_hash_name),
                    image_url=str(result.get("image_url") or ""),
                    source="csqaq_scan",
                )
                self._connection.execute(
                    "INSERT INTO scan_result("
                    "job_id,market_hash_name,name,image_url,snapshot_id"
                    ") VALUES(?,?,?,?,?)",
                    (
                        job.id,
                        snapshot.market_hash_name,
                        str(result.get("name") or snapshot.market_hash_name),
                        str(result.get("image_url") or ""),
                        snapshot_id,
                    ),
                )
            job.next_sequence = next_sequence + 1
            self._update_job(job)
            self._write_event(job.id, next_sequence, event_type, payload or {})

    def append_event(self, job: ScanJob, event_type: str, payload: dict | None = None) -> None:
        with self._lock, self._connection:
            sequence = self._next_sequence(job.id)
            job.next_sequence = sequence + 1
            self._update_job(job)
            self._write_event(job.id, sequence, event_type, payload or {})

    def get_job(self, job_id: str):
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM scan_job WHERE id = ?", (job_id,)
            ).fetchone()
        if row is None:
            return None
        from skinflow_api.application.scan.models import ScanRequest

        return ScanJob(
            request=ScanRequest(
                row["source_mode"],
                row["candidate_limit"],
                depth_limit_per_candidate=row["depth_limit_per_candidate"],
                operation_mode=ScanMode(row["operation_mode"]),
                acquisition_platforms=tuple(
                    AcquisitionPlatform(value)
                    for value in json.loads(row["acquisition_platforms"])
                ),
                min_price=row["min_price"],
                max_price=row["max_price"],
                min_daily_volume=row["min_daily_volume"],
            ),
            id=row["id"],
            status=ScanStatus(row["status"]),
            next_sequence=row["next_sequence"],
            result_count=row["result_count"],
            failure_code=row["failure_code"],
        )

    def list_events(self, job_id: str, after: int = 0) -> list[dict]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT sequence,type,payload FROM scan_event "
                "WHERE job_id=? AND sequence>? ORDER BY sequence",
                (job_id, after),
            ).fetchall()
        return [
            {
                "schema_version": 1,
                "job_id": job_id,
                "sequence": row[0],
                "type": row[1],
                "payload": json.loads(row[2]),
            }
            for row in rows
        ]

    def list_results(self, job_id: str) -> list[dict]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT r.market_hash_name,r.name,r.image_url,r.snapshot_id,"
                "s.buff_observed_at,s.youpin_observed_at,s.steam_observed_at,"
                "s.daily_volume,s.steam_median_price "
                "FROM scan_result r JOIN market_snapshot s ON s.id=r.snapshot_id "
                "WHERE r.job_id=? ORDER BY r.rowid",
                (job_id,),
            ).fetchall()
            return [self._merge_result_event(job_id, self._load_result(row)) for row in rows]

    def _merge_result_event(self, job_id: str, result: dict) -> dict:
        rows = self._connection.execute(
            "SELECT payload FROM scan_event WHERE job_id=? AND type='result.created' "
            "ORDER BY sequence DESC",
            (job_id,),
        ).fetchall()
        for row in rows:
            payload = json.loads(row[0])
            if payload.get("market_hash_name") == result["market_hash_name"]:
                return {**result, **payload}
        return result

    def _load_result(self, row: sqlite3.Row) -> dict:
        tiers = self._connection.execute(
            "SELECT side,price,quantity FROM market_tier WHERE snapshot_id=? ORDER BY position",
            (row["snapshot_id"],),
        ).fetchall()
        lowest = {}
        for tier in tiers:
            lowest.setdefault(tier["side"], tier["price"])
        curves = self._connection.execute(
            "SELECT quantity,cost_total,immediate_ratio_ppm,recommended_ratio_ppm,"
            "market_ask_ratio_ppm FROM price_curve_point "
            "WHERE snapshot_id=? ORDER BY quantity",
            (row["snapshot_id"],),
        ).fetchall()
        return {
            "market_hash_name": row["market_hash_name"],
            "name": row["name"],
            "image_url": row["image_url"],
            "buff_lowest_ask": lowest.get("buff_ask"),
            "youpin_lowest_ask": lowest.get("youpin_ask"),
            "steam_highest_bid": lowest.get("steam_bid"),
            "steam_lowest_ask": lowest.get("steam_ask"),
            "buff_observed_at": row["buff_observed_at"],
            "youpin_observed_at": row["youpin_observed_at"],
            "steam_observed_at": row["steam_observed_at"],
            "daily_volume": row["daily_volume"],
            "steam_median_price": row["steam_median_price"],
            "steam_transaction_price": row["steam_median_price"],
            "curves": [dict(curve) for curve in curves],
        }

    def _drop_legacy_active_index(self) -> None:
        row = self._connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='one_active_scan'"
        ).fetchone()
        if row is not None and "scan_job(status)" in (row[0] or "").replace(" ", ""):
            with self._connection:
                self._connection.execute("DROP INDEX one_active_scan")

    def _next_sequence(self, job_id: str) -> int:
        row = self._connection.execute(
            "SELECT next_sequence FROM scan_job WHERE id=?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise LookupError(job_id)
        return int(row[0])

    def _update_job(self, job: ScanJob) -> None:
        self._connection.execute(
            "UPDATE scan_job SET status=?,result_count=?,failure_code=?,"
            "next_sequence=?,version=version+1 WHERE id=?",
            (job.status, job.result_count, job.failure_code, job.next_sequence, job.id),
        )

    def _write_event(self, job_id: str, sequence: int, event_type: str, payload: dict) -> None:
        self._connection.execute(
            "INSERT INTO scan_event(job_id,sequence,type,payload) VALUES(?,?,?,?)",
            (job_id, sequence, event_type, json.dumps(payload, ensure_ascii=False)),
        )

    def _insert_snapshot(self, snapshot_id: str, job_id: str, snapshot: MarketSnapshot) -> None:
        self._connection.execute(
            "INSERT INTO market_snapshot("
            "id,job_id,market_hash_name,currency,appid,csqaq_observed_at,buff_observed_at,"
            "youpin_observed_at,steam_observed_at,daily_volume_observed_at,daily_volume,"
            "steam_median_price,fee_policy_version"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
        for position, tier in enumerate(snapshot.tiers):
            self._connection.execute(
                "INSERT INTO market_tier VALUES(?,?,?,?,?)",
                (snapshot_id, tier.side, position, tier.price, tier.quantity),
            )

    def _insert_curves(self, snapshot_id: str, curves: tuple[CurvePoint, ...]) -> None:
        self._connection.executemany(
            "INSERT INTO price_curve_point VALUES(?,?,?,?,?,?)",
            [(snapshot_id, point.quantity, point.cost_total, point.immediate_ratio_ppm,
              point.recommended_ratio_ppm, point.market_ask_ratio_ppm) for point in curves],
        )
