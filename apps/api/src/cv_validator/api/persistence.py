from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cv_validator.domain import Report
from cv_validator.ingestion import RedactedDocumentIdentity


@dataclass
class PersistenceConfig:
    db_path: Path
    retention_days: int = 90


class PersistenceStore:
    def __init__(self, config: PersistenceConfig) -> None:
        self.config = config
        self.config.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.config.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    input_hash TEXT NOT NULL,
                    ruleset_version TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    band TEXT NOT NULL,
                    findings_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    input_hash TEXT NOT NULL,
                    ruleset_version TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def persist_report(
        self,
        identity: RedactedDocumentIdentity,
        report: Report,
    ) -> None:
        self._purge_expired()
        input_hash = identity.digest
        findings = _sanitize_findings(report.to_dict())
        now = _utc_now()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reports (input_hash, ruleset_version, score, band, findings_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    input_hash,
                    report.ruleset_version.version,
                    report.score,
                    report.band.value,
                    json.dumps(findings["findings"]),
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO audit_log (input_hash, ruleset_version, output_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (input_hash, report.ruleset_version.version, json.dumps(findings), now),
            )

    def get_audit_entries(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def _purge_expired(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.retention_days)
        cutoff_iso = cutoff.isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM reports WHERE created_at < ?", (cutoff_iso,))
            conn.execute("DELETE FROM audit_log WHERE created_at < ?", (cutoff_iso,))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_findings(report_dict: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(report_dict)
    for finding in sanitized.get("findings", []):
        if finding.get("signal") == "national_id":
            finding["observed"] = finding["observed"].split(":")[0] + ":REDACTED"
    return sanitized
