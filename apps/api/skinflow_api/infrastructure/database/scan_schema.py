import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS scan_job (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  source_mode TEXT NOT NULL,
  candidate_limit INTEGER NOT NULL,
  depth_limit_per_candidate INTEGER NOT NULL,
  operation_mode TEXT NOT NULL DEFAULT 'listing',
  acquisition_platforms TEXT NOT NULL DEFAULT '["buff"]',
  min_price INTEGER,
  max_price INTEGER,
  min_daily_volume INTEGER NOT NULL DEFAULT 0,
  result_count INTEGER NOT NULL DEFAULT 0,
  next_sequence INTEGER NOT NULL DEFAULT 1,
  failure_code TEXT,
  version INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS market_snapshot (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  market_hash_name TEXT NOT NULL,
  currency TEXT NOT NULL,
  appid INTEGER NOT NULL,
  csqaq_observed_at INTEGER,
  buff_observed_at INTEGER,
  youpin_observed_at INTEGER,
  steam_observed_at INTEGER,
  daily_volume_observed_at INTEGER,
  daily_volume INTEGER,
  steam_median_price INTEGER,
  fee_policy_version TEXT NOT NULL,
  UNIQUE(id, job_id, market_hash_name),
  FOREIGN KEY(job_id) REFERENCES scan_job(id)
);
CREATE TABLE IF NOT EXISTS market_tier (
  snapshot_id TEXT NOT NULL,
  side TEXT NOT NULL,
  position INTEGER NOT NULL,
  price INTEGER NOT NULL,
  quantity INTEGER NOT NULL,
  PRIMARY KEY(snapshot_id, side, position),
  FOREIGN KEY(snapshot_id) REFERENCES market_snapshot(id)
);
CREATE TABLE IF NOT EXISTS scan_result (
  job_id TEXT NOT NULL,
  market_hash_name TEXT NOT NULL,
  name TEXT NOT NULL DEFAULT '',
  image_url TEXT NOT NULL DEFAULT '',
  snapshot_id TEXT NOT NULL,
  PRIMARY KEY(job_id, market_hash_name),
  FOREIGN KEY(snapshot_id, job_id, market_hash_name)
    REFERENCES market_snapshot(id, job_id, market_hash_name)
);
CREATE TABLE IF NOT EXISTS price_curve_point (
  snapshot_id TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  cost_total INTEGER NOT NULL,
  immediate_ratio_ppm INTEGER,
  recommended_ratio_ppm INTEGER,
  market_ask_ratio_ppm INTEGER,
  PRIMARY KEY(snapshot_id, quantity),
  FOREIGN KEY(snapshot_id) REFERENCES market_snapshot(id)
);
CREATE TABLE IF NOT EXISTS scan_event (
  job_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  type TEXT NOT NULL,
  payload TEXT NOT NULL,
  PRIMARY KEY(job_id, sequence),
  FOREIGN KEY(job_id) REFERENCES scan_job(id)
);
"""


def ensure_scan_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    result_columns = _columns(connection, "scan_result")
    job_columns = _columns(connection, "scan_job")
    snapshot_columns = _columns(connection, "market_snapshot")
    with connection:
        _add_missing(
            connection,
            "scan_result",
            result_columns,
            {
                "name": "TEXT NOT NULL DEFAULT ''",
                "image_url": "TEXT NOT NULL DEFAULT ''",
            },
        )
        _add_missing(
            connection,
            "scan_job",
            job_columns,
            {
                "operation_mode": "TEXT NOT NULL DEFAULT 'listing'",
                "acquisition_platforms": "TEXT NOT NULL DEFAULT '[\"buff\"]'",
                "min_price": "INTEGER",
                "max_price": "INTEGER",
                "min_daily_volume": "INTEGER NOT NULL DEFAULT 0",
            },
        )
        _add_missing(
            connection,
            "market_snapshot",
            snapshot_columns,
            {
                "youpin_observed_at": "INTEGER",
                "daily_volume": "INTEGER",
                "steam_median_price": "INTEGER",
            },
        )


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_missing(
    connection: sqlite3.Connection,
    table: str,
    columns: set[str],
    definitions: dict[str, str],
) -> None:
    for column, definition in definitions.items():
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
