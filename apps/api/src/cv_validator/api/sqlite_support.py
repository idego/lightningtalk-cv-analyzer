"""Shared SQLite helpers for the API stores.

Every store opens its connections here so hardening settings such as
``secure_delete`` and the stored retention deadline are defined once.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


@contextmanager
def open_connection(db_path: Path, *, foreign_keys: bool = True) -> Iterator[sqlite3.Connection]:
    """Open a row-factory connection that commits on success and zeroes deleted pages."""
    conn = sqlite3.connect(db_path)
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
