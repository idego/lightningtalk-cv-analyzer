"""Shared SQLite helpers for the API stores.

Every store opens its connections here so hardening settings such as
``secure_delete``, WAL journaling, the busy timeout, and the stored retention
deadline are defined once.

Analyses run on several threads at once (``CV_VALIDATOR_ANALYSIS_CONCURRENCY``),
so writers overlap. WAL lets readers proceed during a write and the busy
timeout makes a second writer wait instead of failing with "database is
locked".
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

BUSY_TIMEOUT_ENV = "CV_VALIDATOR_SQLITE_BUSY_TIMEOUT_MS"
DEFAULT_BUSY_TIMEOUT_MS = 10_000


def busy_timeout_ms() -> int:
    """How long a connection waits for a lock, from the environment (positive ms)."""
    value = int(os.environ.get(BUSY_TIMEOUT_ENV, str(DEFAULT_BUSY_TIMEOUT_MS)))
    if value < 1:
        raise ValueError(f"{BUSY_TIMEOUT_ENV} must be a positive integer")
    return value


def connect(db_path: Path) -> sqlite3.Connection:
    """A raw connection with the shared lock-wait and journaling settings applied."""
    timeout_ms = busy_timeout_ms()
    conn = sqlite3.connect(db_path, timeout=timeout_ms / 1000)
    conn.execute(f"PRAGMA busy_timeout = {timeout_ms}")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def checkpoint(conn: sqlite3.Connection) -> None:
    """Fold the WAL back into the main file and truncate it so it cannot grow unbounded."""
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")


@contextmanager
def open_connection(db_path: Path, *, foreign_keys: bool = True) -> Iterator[sqlite3.Connection]:
    """Open a row-factory connection that commits on success and zeroes deleted pages."""
    conn = connect(db_path)
    if foreign_keys:
        conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA secure_delete = ON")
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def retention_deadline(retention_days: int, now: datetime | None = None) -> str:
    """ISO deadline for a row written now under the given retention window."""
    return ((now or datetime.now(timezone.utc)) + timedelta(days=retention_days)).isoformat()


def ensure_expires_at_column(
    conn: sqlite3.Connection, table: str, since_column: str, retention_days: int
) -> None:
    """Add a stored retention deadline and backfill it from the row's own timestamp.

    Rows keep the deadline they were stored with; later retention changes only
    apply to rows written afterwards.
    """
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if not columns:
        return
    if "expires_at" not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN expires_at TEXT")
    for row in conn.execute(
        f"SELECT rowid AS row_id, {since_column} AS since FROM {table} WHERE expires_at IS NULL"
    ).fetchall():
        try:
            since = datetime.fromisoformat(str(row["since"]))
        except ValueError:
            since = datetime.now(timezone.utc)
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        conn.execute(
            f"UPDATE {table} SET expires_at = ? WHERE rowid = ?",
            (retention_deadline(retention_days, since), row["row_id"]),
        )
    conn.execute(f"CREATE INDEX IF NOT EXISTS {table}_expires_at ON {table}(expires_at)")
