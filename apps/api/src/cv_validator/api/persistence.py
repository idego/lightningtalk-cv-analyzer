from __future__ import annotations

import json
import sqlite3
import hashlib
import hmac
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from cv_validator.analysis import validate_analysis_report
from cv_validator.api.feedback import init_feedback_schema
from cv_validator.errors import AnalysisNotFoundPersistenceError, PersistenceError
from cv_validator.serialization import deserialize_analysis_payload
from cv_validator.usage import USD_PLN_FX_RATE, USD_PLN_FX_VERSION, usd_to_pln


@dataclass
class PersistenceConfig:
    db_path: Path
    retention_days: int = 90
    research_cache_ttl_days: int = 30


class PersistenceStore:
    def __init__(self, config: PersistenceConfig) -> None:
        self.config = config
        self._event_write_lock = threading.Lock()
        self._purge_listener: Callable[[tuple[str, ...]], None] | None = None
        self.config.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.config.retention_days = self.get_retention_days()

    def set_purge_listener(
        self,
        listener: Callable[[tuple[str, ...]], None] | None,
    ) -> None:
        self._purge_listener = listener

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.config.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _require_report_parent(conn: sqlite3.Connection, analysis_id: str) -> None:
        """Require the report parent in the same transaction as a child write.

        Foreign-key enforcement closes the check/write race if deletion wins
        between this query and the INSERT.
        """
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute(
            "SELECT 1 FROM reports WHERE analysis_id = ?",
            (analysis_id,),
        ).fetchone() is None:
            raise AnalysisNotFoundPersistenceError("analysis not found")

    def _init_db(self) -> None:
        with self._connect() as conn:
            _require_current_report_schema(conn)
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    input_hash TEXT NOT NULL,
                    contract_version TEXT NOT NULL,
                    strategy_name TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    analysis_id TEXT NOT NULL,
                    access_token_hash TEXT,
                    source_filename TEXT
                );
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    input_hash TEXT NOT NULL,
                    contract_version TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    analysis_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS company_research (
                    analysis_id TEXT NOT NULL,
                    research_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    configured_model TEXT NOT NULL,
                    response_model TEXT,
                    accessed_at TEXT NOT NULL,
                    usage_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (analysis_id, research_version),
                    FOREIGN KEY (analysis_id) REFERENCES reports(analysis_id)
                );
                CREATE TABLE IF NOT EXISTS education_research (
                    analysis_id TEXT NOT NULL, research_version TEXT NOT NULL,
                    status TEXT NOT NULL, prompt_version TEXT NOT NULL,
                    schema_version TEXT NOT NULL, configured_model TEXT NOT NULL,
                    response_model TEXT, accessed_at TEXT NOT NULL,
                    usage_json TEXT NOT NULL, result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (analysis_id, research_version),
                    FOREIGN KEY (analysis_id) REFERENCES reports(analysis_id)
                );
                CREATE TABLE IF NOT EXISTS linkedin_discovery (
                    analysis_id TEXT NOT NULL, research_version TEXT NOT NULL,
                    status TEXT NOT NULL, prompt_version TEXT NOT NULL, schema_version TEXT NOT NULL,
                    configured_model TEXT NOT NULL, response_model TEXT, accessed_at TEXT NOT NULL,
                    usage_json TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY (analysis_id, research_version), FOREIGN KEY (analysis_id) REFERENCES reports(analysis_id)
                );
                CREATE TABLE IF NOT EXISTS linkedin_confirmation (
                    analysis_id TEXT PRIMARY KEY, profile_url TEXT NOT NULL, discovery_version TEXT NOT NULL,
                    confirmed_at TEXT NOT NULL, audit_json TEXT NOT NULL,
                    FOREIGN KEY (analysis_id) REFERENCES reports(analysis_id)
                );
                CREATE TABLE IF NOT EXISTS linkedin_comparison (
                    analysis_id TEXT NOT NULL, research_version TEXT NOT NULL, profile_url TEXT NOT NULL,
                    status TEXT NOT NULL, prompt_version TEXT NOT NULL, schema_version TEXT NOT NULL,
                    configured_model TEXT NOT NULL, response_model TEXT, accessed_at TEXT NOT NULL,
                    usage_json TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY (analysis_id, research_version), FOREIGN KEY (analysis_id) REFERENCES reports(analysis_id)
                );
                CREATE TABLE IF NOT EXISTS reusable_research_cache (
                    cache_key TEXT PRIMARY KEY, cache_format_version TEXT NOT NULL,
                    category TEXT NOT NULL, normalized_subjects_json TEXT NOT NULL,
                    research_version TEXT NOT NULL, prompt_version TEXT NOT NULL,
                    schema_version TEXT NOT NULL, model_version TEXT NOT NULL,
                    search_policy_version TEXT NOT NULL, payload_json TEXT NOT NULL,
                    source_accessed_at TEXT NOT NULL, created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL, invalidated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS research_cache_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, analysis_id TEXT NOT NULL,
                    category TEXT NOT NULL, cache_key TEXT NOT NULL, outcome TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (analysis_id) REFERENCES reports(analysis_id)
                );
                CREATE TABLE IF NOT EXISTS source_documents (
                    analysis_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    content BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (analysis_id) REFERENCES reports(analysis_id)
                );
                CREATE TABLE IF NOT EXISTS analysis_share_tokens (
                    analysis_id TEXT NOT NULL,
                    token_hash TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (analysis_id) REFERENCES reports(analysis_id)
                );
                CREATE TABLE IF NOT EXISTS runtime_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    analysis_id TEXT PRIMARY KEY,
                    correlation_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    access_token_hash TEXT NOT NULL,
                    error_code TEXT
                );
                CREATE TABLE IF NOT EXISTS diagnostic_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ai_usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT,
                    event_key TEXT,
                    analysis_id TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    category TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    configured_model TEXT NOT NULL,
                    response_model TEXT,
                    reasoning_effort TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    outcome TEXT NOT NULL,
                    error_code TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    cached_input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    reasoning_output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL,
                    estimated_cost_usd TEXT,
                    estimated_cost_pln TEXT,
                    pricing_version TEXT NOT NULL,
                    pricing_reason TEXT,
                    fx_rate TEXT,
                    fx_version TEXT,
                    billing_status TEXT,
                    cache_outcome TEXT,
                    saved_input_tokens INTEGER NOT NULL DEFAULT 0,
                    saved_cached_input_tokens INTEGER NOT NULL DEFAULT 0,
                    saved_output_tokens INTEGER NOT NULL DEFAULT 0,
                    saved_total_tokens INTEGER NOT NULL DEFAULT 0,
                    saved_cost_usd TEXT
                );
                CREATE TABLE IF NOT EXISTS processed_report_events (
                    event_id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL UNIQUE,
                    completed_at TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status = 'completed')
                );
                """
            )
            _ensure_ai_usage_schema(conn)
            conn.execute(
                """INSERT OR IGNORE INTO processed_report_events
                   (event_id, analysis_id, completed_at, status)
                   SELECT 'legacy-report-' || analysis_id, analysis_id, created_at, 'completed'
                   FROM reports WHERE status IN ('completed', 'partial')"""
            )
            init_feedback_schema(conn)
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS reports_analysis_id ON reports(analysis_id)"
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS audit_log_analysis_id ON audit_log(analysis_id)"
            )

    def create_analysis_run(
        self,
        analysis_id: str,
        correlation_id: str,
        access_token: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO analysis_runs
                   (analysis_id, correlation_id, status, created_at, access_token_hash)
                   VALUES (?, ?, 'running', ?, ?)""",
                (analysis_id, correlation_id, _utc_now(), _token_hash(access_token)),
            )

    def complete_analysis_run(
        self,
        analysis_id: str,
        status: str,
        error_code: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """UPDATE analysis_runs SET status = ?, completed_at = ?, error_code = ?
                   WHERE analysis_id = ?""",
                (status, _utc_now(), error_code, analysis_id),
            )

    def record_diagnostic_event(self, payload: dict[str, Any]) -> None:
        safe = dict(payload)
        with self._event_write_lock:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO diagnostic_events
                       (analysis_id, correlation_id, event, payload_json, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        safe.pop("analysis_id"),
                        safe.pop("correlation_id"),
                        safe.pop("event"),
                        json.dumps(safe, sort_keys=True, separators=(",", ":")),
                        _utc_now(),
                    ),
                )

    def record_ai_usage_event(self, event: dict[str, Any]) -> None:
        columns = (
            "event_id", "event_key", "analysis_id", "correlation_id", "operation", "category", "provider",
            "configured_model", "response_model", "reasoning_effort", "attempt",
            "outcome", "error_code", "started_at", "completed_at", "latency_ms",
            "input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens",
            "estimated_cost_usd", "estimated_cost_pln", "pricing_version", "pricing_reason",
            "fx_rate", "fx_version", "billing_status", "cache_outcome",
            "saved_input_tokens", "saved_cached_input_tokens", "saved_output_tokens",
            "saved_total_tokens", "saved_cost_usd",
        )
        with self._event_write_lock:
            with self._connect() as conn:
                conn.execute(
                    f"INSERT INTO ai_usage_events ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)}) ON CONFLICT(event_key) DO NOTHING",
                    tuple(event.get(column) for column in columns),
                )

    def get_usage_summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM ai_usage_events ORDER BY id").fetchall()
            reports_processed = int(conn.execute(
                "SELECT COUNT(*) FROM processed_report_events"
            ).fetchone()[0])
        usage = [dict(row) for row in rows]
        summary = _summarize_usage(usage)
        summary["reports_processed"] = reports_processed
        summary["average_tokens_per_report"] = (
            round(summary["total_tokens"] / reports_processed, 1)
            if reports_processed else 0.0
        )
        summary["average_estimated_cost_usd"] = _average_decimal(
            summary["estimated_cost_usd"], reports_processed
        )
        summary["average_estimated_cost_pln"] = _average_decimal(
            summary["estimated_cost_pln"], reports_processed
        )
        summary["operations"] = _group_usage(
            usage,
            lambda item: item["operation"],
        )
        return summary

    def get_analysis_usage_summary(self, analysis_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM ai_usage_events WHERE analysis_id = ? ORDER BY id",
                (analysis_id,),
            ).fetchall()
        return _summarize_usage([dict(row) for row in rows])

    def get_analysis_diagnostics(self, analysis_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            run = conn.execute(
                "SELECT analysis_id, correlation_id, status, created_at, completed_at, error_code FROM analysis_runs WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()
            if run is None:
                return None
            diagnostic_rows = conn.execute(
                "SELECT event, payload_json, created_at FROM diagnostic_events WHERE analysis_id = ? ORDER BY id",
                (analysis_id,),
            ).fetchall()
            usage_rows = conn.execute(
                "SELECT * FROM ai_usage_events WHERE analysis_id = ? ORDER BY id",
                (analysis_id,),
            ).fetchall()
        diagnostics = [
            {"event": row["event"], "created_at": row["created_at"], **json.loads(row["payload_json"])}
            for row in diagnostic_rows
        ]
        usage = [{key: row[key] for key in row.keys() if key != "id"} for row in usage_rows]
        aggregate: dict[str, Any] = {
            "attempts": len(usage), "input_tokens": 0, "cached_input_tokens": 0,
            "output_tokens": 0, "total_tokens": 0, "estimated_cost_usd": "0.000000000",
        }
        cost = Decimal("0")
        cost_known = True
        for item in usage:
            for key in ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens"):
                aggregate[key] += item[key]
            if item["estimated_cost_usd"] is None:
                cost_known = False
            else:
                cost += Decimal(item["estimated_cost_usd"])
        aggregate["estimated_cost_usd"] = f"{cost:.9f}" if cost_known else None
        return {
            "analysis": dict(run),
            "diagnostics": diagnostics,
            "usage_events": usage,
            "aggregate": aggregate,
            "aggregates": {
                "by_operation": _group_usage(usage, lambda item: item["operation"]),
                "by_model": _group_usage(
                    usage,
                    lambda item: item["response_model"] or item["configured_model"],
                ),
                "by_day": _group_usage(usage, lambda item: item["completed_at"][:10]),
                "by_cache": _group_usage(
                    usage,
                    lambda item: item["cache_outcome"] or "live",
                ),
            },
        }

    def analysis_correlation_id(self, analysis_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT correlation_id FROM analysis_runs WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()
        return None if row is None else str(row["correlation_id"])

    def persist_report(
        self,
        input_hash: str,
        report_payload: dict[str, Any],
        *,
        analysis_id: str | None = None,
        access_token: str | None = None,
        source_filename: str | None = None,
    ) -> str:
        selected_analysis_id = analysis_id or str(uuid4())
        payload = validate_analysis_report(report_payload)
        stored_payload = dict(payload)
        stored_payload.pop("analysis_access_token", None)
        strategy = payload["strategy"]
        status = payload["base_analysis"]["status"]
        now = _utc_now()
        try:
            self.purge_expired()
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO reports (
                        input_hash, contract_version, strategy_name,
                        strategy_version, status, created_at, analysis_id,
                        access_token_hash, source_filename
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        input_hash,
                        payload["contract_version"],
                        strategy["name"],
                        strategy["version"],
                        status,
                        now,
                        selected_analysis_id,
                        _token_hash(access_token) if access_token else None,
                        source_filename,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO audit_log (
                        input_hash, contract_version, output_json, created_at,
                        analysis_id
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        input_hash,
                        payload["contract_version"],
                        json.dumps(stored_payload),
                        now,
                        selected_analysis_id,
                    ),
                )
                if status in {"completed", "partial"}:
                    conn.execute(
                        """INSERT INTO processed_report_events
                           (event_id, analysis_id, completed_at, status)
                           VALUES (?, ?, ?, 'completed')
                           ON CONFLICT(analysis_id) DO NOTHING""",
                        (str(uuid4()), selected_analysis_id, now),
                    )
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("report persistence failed") from exc
        return selected_analysis_id

    def persist_source_document(
        self,
        analysis_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> None:
        try:
            with self._connect() as conn:
                self._require_report_parent(conn, analysis_id)
                conn.execute(
                    """INSERT INTO source_documents
                       (analysis_id, filename, content_type, content, created_at)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(analysis_id) DO UPDATE SET
                         filename = excluded.filename,
                         content_type = excluded.content_type,
                         content = excluded.content,
                         created_at = excluded.created_at""",
                    (analysis_id, filename, content_type, sqlite3.Binary(content), _utc_now()),
                )
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("source document persistence failed") from exc

    def get_source_document(self, analysis_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT filename, content_type, content FROM source_documents WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "filename": row["filename"],
            "content_type": row["content_type"],
            "content": bytes(row["content"]),
        }

    def get_audit_entries(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def get_analysis_payload(self, analysis_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT output_json FROM audit_log WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()
        return None if row is None else deserialize_analysis_payload(
            json.loads(row["output_json"])
        )

    def list_analyses(self, access_token: str | None) -> list[dict[str, Any]]:
        if not access_token:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT reports.analysis_id, reports.source_filename,
                          reports.status, reports.created_at, audit_log.output_json,
                          EXISTS (
                            SELECT 1 FROM source_documents
                            WHERE source_documents.analysis_id = reports.analysis_id
                          ) AS has_document
                   FROM reports
                   JOIN audit_log USING (analysis_id)
                   WHERE reports.access_token_hash = ?
                   ORDER BY reports.created_at DESC""",
                (_token_hash(access_token),),
            ).fetchall()
        history: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["output_json"])
            history.append(
                {
                    "analysis_id": row["analysis_id"],
                    "filename": row["source_filename"] or "CV",
                    "candidate_name": _candidate_name(payload),
                    "status": row["status"],
                    "strategy": payload.get("strategy", {}).get("name"),
                    "created_at": row["created_at"],
                    "has_document": bool(row["has_document"]),
                }
            )
        return history

    def analysis_access_allowed(self, analysis_id: str, access_token: str | None) -> bool:
        if not access_token:
            return False
        with self._connect() as conn:
            row = conn.execute(
                """SELECT access_token_hash FROM reports WHERE analysis_id = ?
                   UNION ALL SELECT access_token_hash FROM analysis_runs WHERE analysis_id = ? LIMIT 1""",
                (analysis_id, analysis_id),
            ).fetchone()
        return row is not None and isinstance(row["access_token_hash"], str) and hmac.compare_digest(row["access_token_hash"], _token_hash(access_token))

    def persist_analysis_share_token(
        self,
        analysis_id: str,
        access_token: str | None,
        share_token: str,
    ) -> bool:
        if not self.analysis_access_allowed(analysis_id, access_token):
            return False
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO analysis_share_tokens (analysis_id, token_hash, created_at)
                   VALUES (?, ?, ?)""",
                (analysis_id, _token_hash(share_token), _utc_now()),
            )
        return True

    def analysis_share_access_allowed(self, analysis_id: str, share_token: str | None) -> bool:
        if not share_token:
            return False
        token_hash = _token_hash(share_token)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT token_hash FROM analysis_share_tokens WHERE analysis_id = ? AND token_hash = ?",
                (analysis_id, token_hash),
            ).fetchone()
        return row is not None and hmac.compare_digest(str(row["token_hash"]), token_hash)

    def get_analysis_view(self, analysis_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT reports.source_filename, audit_log.output_json,
                          EXISTS (
                            SELECT 1 FROM source_documents
                            WHERE source_documents.analysis_id = reports.analysis_id
                          ) AS has_document
                   FROM reports
                   JOIN audit_log USING (analysis_id)
                   WHERE reports.analysis_id = ?""",
                (analysis_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "filename": row["source_filename"] or "CV",
            "has_document": bool(row["has_document"]),
            "report": deserialize_analysis_payload(json.loads(row["output_json"])),
        }

    def delete_analysis(self, analysis_id: str, access_token: str | None) -> bool:
        if not self.analysis_access_allowed(analysis_id, access_token):
            return False
        self._delete_analysis_ids([analysis_id])
        return True

    def delete_all_analyses(self, access_token: str | None) -> int:
        if not access_token:
            return 0
        with self._connect() as conn:
            analysis_ids = [
                row[0]
                for row in conn.execute(
                    "SELECT analysis_id FROM reports WHERE access_token_hash = ?",
                    (_token_hash(access_token),),
                ).fetchall()
            ]
        self._delete_analysis_ids(analysis_ids)
        return len(analysis_ids)

    def _delete_analysis_ids(self, analysis_ids: list[str]) -> None:
        if not analysis_ids:
            return
        placeholders = ",".join("?" for _ in analysis_ids)
        with self._connect() as conn:
            for table in (
                "diagnostic_events",
                "research_cache_audit",
                "company_research",
                "education_research",
                "linkedin_discovery",
                "linkedin_comparison",
                "linkedin_confirmation",
                "analysis_share_tokens",
                "source_documents",
                "audit_log",
            ):
                conn.execute(
                    f"DELETE FROM {table} WHERE analysis_id IN ({placeholders})",
                    analysis_ids,
                )
            conn.execute(
                f"DELETE FROM reports WHERE analysis_id IN ({placeholders})",
                analysis_ids,
            )
            conn.execute(
                f"DELETE FROM analysis_runs WHERE analysis_id IN ({placeholders})",
                analysis_ids,
            )

    def get_retention_days(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM runtime_settings WHERE key = 'retention_days'"
            ).fetchone()
        if row is None:
            return self.config.retention_days
        try:
            value = int(row["value"])
        except (TypeError, ValueError):
            return self.config.retention_days
        return value if 1 <= value <= 3650 else self.config.retention_days

    def set_retention_days(self, days: int) -> dict[str, int | tuple[str, ...]]:
        if not 1 <= days <= 3650:
            raise ValueError("retention_days_out_of_range")
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO runtime_settings (key, value, updated_at)
                   VALUES ('retention_days', ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                     value = excluded.value,
                     updated_at = excluded.updated_at""",
                (str(days), _utc_now()),
            )
        self.config.retention_days = days
        return self.purge_expired()

    def get_company_research(self, analysis_id: str) -> dict[str, Any] | None:
        from cv_validator.research.company import RESEARCH_VERSION
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM company_research WHERE analysis_id = ? AND research_version = ?",
                (analysis_id, RESEARCH_VERSION),
            ).fetchone()
        return None if row is None else dict(row)

    def persist_company_research(self, analysis_id: str, result: dict[str, Any]) -> None:
        versions = result["versions"]
        model = result["model"]
        now = _utc_now()
        try:
            with self._connect() as conn:
                self._require_report_parent(conn, analysis_id)
                conn.execute(
                    """
                    INSERT INTO company_research (
                        analysis_id, research_version, status, prompt_version,
                        schema_version, configured_model, response_model,
                        accessed_at, usage_json, result_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(analysis_id, research_version) DO UPDATE SET
                        status=excluded.status, prompt_version=excluded.prompt_version,
                        schema_version=excluded.schema_version,
                        configured_model=excluded.configured_model,
                        response_model=excluded.response_model,
                        accessed_at=excluded.accessed_at,
                        usage_json=excluded.usage_json,
                        result_json=excluded.result_json,
                        created_at=excluded.created_at
                    """,
                    (analysis_id, versions["research"], result["status"],
                     versions["prompt"], versions["schema"], model["configured"],
                     model["response"], result["accessed_at"],
                     json.dumps(result["usage"]), json.dumps(result), now),
                )
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("company research persistence failed") from exc

    def get_education_research(self, analysis_id: str) -> dict[str, Any] | None:
        from cv_validator.research.education import RESEARCH_VERSION
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM education_research WHERE analysis_id = ? AND research_version = ?",
                (analysis_id, RESEARCH_VERSION),
            ).fetchone()
        return None if row is None else dict(row)

    def persist_education_research(self, analysis_id: str, result: dict[str, Any]) -> None:
        versions, model, now = result["versions"], result["model"], _utc_now()
        try:
            with self._connect() as conn:
                self._require_report_parent(conn, analysis_id)
                conn.execute(
                    """INSERT INTO education_research (
                        analysis_id, research_version, status, prompt_version,
                        schema_version, configured_model, response_model,
                        accessed_at, usage_json, result_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(analysis_id, research_version) DO UPDATE SET
                        status=excluded.status, prompt_version=excluded.prompt_version,
                        schema_version=excluded.schema_version,
                        configured_model=excluded.configured_model,
                        response_model=excluded.response_model,
                        accessed_at=excluded.accessed_at,
                        usage_json=excluded.usage_json,
                        result_json=excluded.result_json,
                        created_at=excluded.created_at""",
                    (analysis_id, versions["research"], result["status"], versions["prompt"],
                     versions["schema"], model["configured"], model["response"], result["accessed_at"],
                     json.dumps(result["usage"]), json.dumps(result), now),
                )
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("education research persistence failed") from exc

    def get_reusable_research(self, descriptor: Any) -> dict[str, Any] | None:
        now = _utc_now()
        with self._connect() as conn:
            row = conn.execute(
                """SELECT payload_json FROM reusable_research_cache
                   WHERE cache_key = ? AND category = ? AND cache_format_version = ?
                     AND research_version = ? AND prompt_version = ? AND schema_version = ?
                     AND model_version = ? AND search_policy_version = ?
                     AND invalidated_at IS NULL AND expires_at > ?""",
                (descriptor.cache_key, descriptor.category, descriptor.cache_format_version,
                 descriptor.research_version, descriptor.prompt_version, descriptor.schema_version,
                 descriptor.model_version, descriptor.search_policy_version, now),
            ).fetchone()
        return None if row is None else json.loads(row["payload_json"])

    def persist_reusable_research(self, descriptor: Any, payload: dict[str, Any]) -> None:
        now_dt = datetime.now(timezone.utc)
        expires_at = now_dt + timedelta(days=self.config.research_cache_ttl_days)
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO reusable_research_cache (
                    cache_key, cache_format_version, category, normalized_subjects_json,
                    research_version, prompt_version, schema_version, model_version,
                    search_policy_version, payload_json, source_accessed_at, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET payload_json=excluded.payload_json,
                    source_accessed_at=excluded.source_accessed_at, created_at=excluded.created_at,
                    expires_at=excluded.expires_at, invalidated_at=NULL""",
                (descriptor.cache_key, descriptor.cache_format_version, descriptor.category,
                 json.dumps(descriptor.normalized_subjects), descriptor.research_version,
                 descriptor.prompt_version, descriptor.schema_version, descriptor.model_version,
                 descriptor.search_policy_version, json.dumps(payload), payload["accessed_at"],
                 now_dt.isoformat(), expires_at.isoformat()),
            )

    def record_cache_use(self, analysis_id: str, category: str, cache_key: str, outcome: str) -> None:
        try:
            with self._connect() as conn:
                self._require_report_parent(conn, analysis_id)
                conn.execute("INSERT INTO research_cache_audit (analysis_id, category, cache_key, outcome, created_at) VALUES (?, ?, ?, ?, ?)",
                             (analysis_id, category, cache_key, outcome, _utc_now()))
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("research cache audit persistence failed") from exc

    def get_cache_audit(self, analysis_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT analysis_id, category, cache_key, outcome, created_at FROM research_cache_audit WHERE analysis_id = ? ORDER BY id", (analysis_id,)).fetchall()
        return [dict(row) for row in rows]

    def invalidate_reusable_research(self, cache_key: str | None = None) -> int:
        with self._connect() as conn:
            if cache_key is None:
                cursor = conn.execute("UPDATE reusable_research_cache SET invalidated_at = ? WHERE invalidated_at IS NULL", (_utc_now(),))
            else:
                cursor = conn.execute("UPDATE reusable_research_cache SET invalidated_at = ? WHERE cache_key = ? AND invalidated_at IS NULL", (_utc_now(), cache_key))
        return cursor.rowcount

    def get_linkedin_discovery(self, analysis_id: str) -> dict[str, Any] | None:
        from cv_validator.research.linkedin import DISCOVERY_VERSION
        return self._get_research_row("linkedin_discovery", analysis_id, DISCOVERY_VERSION)

    def persist_linkedin_discovery(self, analysis_id: str, result: dict[str, Any]) -> None:
        self._persist_linkedin_result("linkedin_discovery", analysis_id, result)

    def confirm_linkedin_profile(self, analysis_id: str, profile_url: str, discovery_version: str) -> dict[str, Any]:
        confirmed_at = _utc_now()
        audit = {"action": "recruiter_confirmed_possible_profile", "analysis_id": analysis_id,
                 "profile_url": profile_url, "discovery_version": discovery_version, "confirmed_at": confirmed_at,
                 "caveat": "Confirmation authorizes comparison only; it does not establish identity."}
        try:
            with self._connect() as conn:
                self._require_report_parent(conn, analysis_id)
                cursor = conn.execute(
                    """INSERT INTO linkedin_confirmation
                    (analysis_id, profile_url, discovery_version, confirmed_at, audit_json)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(analysis_id) DO UPDATE SET
                        profile_url = excluded.profile_url,
                        discovery_version = excluded.discovery_version,
                        confirmed_at = excluded.confirmed_at,
                        audit_json = excluded.audit_json
                    WHERE linkedin_confirmation.discovery_version <> excluded.discovery_version""",
                    (analysis_id, profile_url, discovery_version, confirmed_at, json.dumps(audit)),
                )
                if cursor.rowcount:
                    conn.execute(
                        "DELETE FROM linkedin_comparison WHERE analysis_id = ?",
                        (analysis_id,),
                    )
                row = conn.execute(
                    "SELECT profile_url, audit_json FROM linkedin_confirmation WHERE analysis_id = ?",
                    (analysis_id,),
                ).fetchone()
                if row is None or row["profile_url"] != profile_url:
                    raise ValueError("different_profile_already_confirmed")
                audit = json.loads(row["audit_json"])
        except (OSError, sqlite3.Error) as exc: raise PersistenceError("linkedin confirmation persistence failed") from exc
        return audit

    def get_linkedin_confirmation(self, analysis_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM linkedin_confirmation WHERE analysis_id = ?", (analysis_id,)).fetchone()
        return None if row is None else dict(row)

    def get_linkedin_comparison(self, analysis_id: str) -> dict[str, Any] | None:
        from cv_validator.research.linkedin import COMPARISON_VERSION
        return self._get_research_row("linkedin_comparison", analysis_id, COMPARISON_VERSION)

    def persist_linkedin_comparison(self, analysis_id: str, profile_url: str, result: dict[str, Any]) -> None:
        self._persist_linkedin_result("linkedin_comparison", analysis_id, result, profile_url=profile_url)

    def _get_research_row(self, table: str, analysis_id: str, version: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(f"SELECT * FROM {table} WHERE analysis_id = ? AND research_version = ?", (analysis_id, version)).fetchone()
        return None if row is None else dict(row)

    def _persist_linkedin_result(self, table: str, analysis_id: str, result: dict[str, Any], *, profile_url: str | None = None) -> None:
        versions, model, now = result["versions"], result["model"], _utc_now()
        columns = "analysis_id, research_version, status, prompt_version, schema_version, configured_model, response_model, accessed_at, usage_json, result_json, created_at"
        values: tuple[Any, ...] = (analysis_id, versions["research"], result["status"], versions["prompt"], versions["schema"], model["configured"], model["response"], result["accessed_at"], json.dumps(result["usage"]), json.dumps(result), now)
        if profile_url is not None:
            columns = "analysis_id, research_version, profile_url, status, prompt_version, schema_version, configured_model, response_model, accessed_at, usage_json, result_json, created_at"
            values = (analysis_id, versions["research"], profile_url, result["status"], versions["prompt"], versions["schema"], model["configured"], model["response"], result["accessed_at"], json.dumps(result["usage"]), json.dumps(result), now)
        placeholders = ", ".join("?" for _ in values)
        try:
            with self._connect() as conn:
                self._require_report_parent(conn, analysis_id)
                conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) ON CONFLICT(analysis_id, research_version) DO NOTHING", values)
        except (OSError, sqlite3.Error) as exc: raise PersistenceError("linkedin research persistence failed") from exc

    def persist_analysis_payload_for_test(self, payload: dict[str, Any]) -> None:
        """Seed an anonymous stored payload without constructing an uploaded CV."""
        now = _utc_now()
        analysis_id = payload["analysis_id"]
        validated = validate_analysis_report(payload)
        strategy = validated["strategy"]
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO reports (
                    input_hash, contract_version, strategy_name,
                    strategy_version, status, created_at, analysis_id,
                    access_token_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    validated["source"]["sha256"],
                    validated["contract_version"],
                    strategy["name"],
                    strategy["version"],
                    validated["base_analysis"]["status"],
                    now,
                    analysis_id,
                    _token_hash("test-access-token"),
                ),
            )
            conn.execute(
                "INSERT INTO audit_log (input_hash, contract_version, output_json, created_at, analysis_id) VALUES (?, ?, ?, ?, ?)",
                (
                    validated["source"]["sha256"],
                    validated["contract_version"],
                    json.dumps(validated),
                    now,
                    analysis_id,
                ),
            )

    def purge_expired(self) -> dict[str, int | tuple[str, ...]]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.retention_days)
        cutoff_iso = cutoff.isoformat()
        deleted: dict[str, int | tuple[str, ...]] = {}
        with self._connect() as conn:
            expired_ids_set: set[str] = set()
            for table, column in (
                ("reports", "created_at"),
                ("research_cache_audit", "created_at"),
                ("company_research", "created_at"),
                ("education_research", "created_at"),
                ("linkedin_discovery", "created_at"),
                ("linkedin_comparison", "created_at"),
                ("linkedin_confirmation", "confirmed_at"),
                ("source_documents", "created_at"),
                ("audit_log", "created_at"),
                ("analysis_runs", "created_at"),
            ):
                expired_ids_set.update(
                    row[0]
                    for row in conn.execute(
                        f"SELECT analysis_id FROM {table} WHERE {column} < ?",
                        (cutoff_iso,),
                    ).fetchall()
                    if isinstance(row[0], str)
                )
            expired_ids = sorted(expired_ids_set)
            if expired_ids:
                placeholders = ",".join("?" for _ in expired_ids)
                for table in ("research_cache_audit", "company_research", "education_research",
                              "linkedin_discovery", "linkedin_comparison", "linkedin_confirmation",
                              "analysis_share_tokens", "source_documents", "audit_log", "diagnostic_events"):
                    deleted[table] = conn.execute(f"DELETE FROM {table} WHERE analysis_id IN ({placeholders})", expired_ids).rowcount
                deleted["reports"] = conn.execute(f"DELETE FROM reports WHERE analysis_id IN ({placeholders})", expired_ids).rowcount
                deleted["analysis_runs"] = conn.execute(f"DELETE FROM analysis_runs WHERE analysis_id IN ({placeholders})", expired_ids).rowcount
            deleted["reusable_research_cache"] = conn.execute("DELETE FROM reusable_research_cache WHERE expires_at <= ?", (_utc_now(),)).rowcount
            deleted["analysis_ids"] = tuple(expired_ids)
            if expired_ids and self._purge_listener is not None:
                self._purge_listener(tuple(expired_ids))
        return deleted


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _group_usage(
    usage: list[dict[str, Any]],
    key_for: Callable[[dict[str, Any]], str],
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for item in usage:
        key = key_for(item)
        group = groups.setdefault(key, {
            "key": key,
            "attempts": 0,
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": Decimal("0"),
            "estimated_cost_pln": Decimal("0"),
            "usd_cost_available": True,
            "pln_cost_available": True,
        })
        group["attempts"] += 1
        for token in ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens"):
            group[token] += item[token]
        if item["estimated_cost_usd"] is None and item["total_tokens"] > 0:
            group["usd_cost_available"] = False
        else:
            group["estimated_cost_usd"] += Decimal(item["estimated_cost_usd"] or "0")
        if item.get("estimated_cost_pln") is None and item["total_tokens"] > 0:
            group["pln_cost_available"] = False
        else:
            group["estimated_cost_pln"] += Decimal(item.get("estimated_cost_pln") or "0")
    output: list[dict[str, Any]] = []
    for key in sorted(groups):
        group = groups[key]
        usd_available = group.pop("usd_cost_available")
        pln_available = group.pop("pln_cost_available")
        usd_cost = group["estimated_cost_usd"]
        pln_cost = group["estimated_cost_pln"]
        group["estimated_cost_usd"] = f"{usd_cost:.9f}" if usd_available else None
        group["estimated_cost_pln"] = f"{pln_cost:.9f}" if pln_available else None
        output.append(group)
    return output


def _summarize_usage(usage: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "requests": len(usage),
        "paid_requests": 0,
        "unpriced_requests": 0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    usd_cost = Decimal("0")
    pln_cost = Decimal("0")
    usd_available = True
    pln_available = True
    for item in usage:
        if item.get("billing_status") == "paid":
            summary["paid_requests"] += 1
        for key in ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens"):
            summary[key] += int(item.get(key) or 0)
        token_usage = int(item.get("total_tokens") or 0)
        item_usd = item.get("estimated_cost_usd")
        item_pln = item.get("estimated_cost_pln")
        if item_usd is None and token_usage > 0:
            usd_available = False
            summary["unpriced_requests"] += 1
        else:
            usd_cost += Decimal(item_usd or "0")
        if item_pln is None and token_usage > 0:
            pln_available = False
        else:
            pln_cost += Decimal(item_pln or "0")
    summary["estimated_cost_usd"] = f"{usd_cost:.9f}" if usd_available else None
    summary["estimated_cost_pln"] = f"{pln_cost:.9f}" if pln_available else None
    summary["fx_rate"] = str(USD_PLN_FX_RATE)
    summary["fx_version"] = USD_PLN_FX_VERSION
    return summary


def _average_decimal(value: str | None, divisor: int) -> str | None:
    if value is None:
        return None
    if divisor <= 0:
        return "0.000000000"
    return f"{(Decimal(value) / Decimal(divisor)):.9f}"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _candidate_name(payload: dict[str, Any]) -> str | None:
    profile = payload.get("base_analysis", {}).get("profile")
    if not isinstance(profile, dict):
        return None
    candidate_name = profile.get("candidate_name")
    if not isinstance(candidate_name, dict):
        return None
    if candidate_name.get("status") != "supported":
        return None
    value = candidate_name.get("value")
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _require_current_report_schema(conn: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(reports)").fetchall()
    }
    required = {
        "input_hash",
        "contract_version",
        "strategy_name",
        "strategy_version",
        "status",
        "created_at",
        "analysis_id",
        "access_token_hash",
        "source_filename",
    }
    if columns and not required.issubset(columns):
        raise PersistenceError("legacy_database_reset_required")


def _ensure_ai_usage_schema(conn: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(ai_usage_events)").fetchall()
    }
    additions = {
        "event_id": "TEXT",
        "event_key": "TEXT",
        "estimated_cost_pln": "TEXT",
        "fx_rate": "TEXT",
        "fx_version": "TEXT",
        "billing_status": "TEXT",
        "reasoning_output_tokens": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, definition in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE ai_usage_events ADD COLUMN {name} {definition}")
    rows = conn.execute(
        """SELECT id, event_id, event_key, estimated_cost_usd, estimated_cost_pln,
                  total_tokens, outcome, cache_outcome, fx_rate, fx_version, billing_status
           FROM ai_usage_events
           WHERE event_id IS NULL OR event_key IS NULL OR fx_rate IS NULL
              OR fx_version IS NULL OR billing_status IS NULL"""
    ).fetchall()
    for row in rows:
        event_id = row["event_id"] or f"legacy-usage-{row['id']}"
        event_key = row["event_key"] or f"legacy-usage-{row['id']}"
        cost_pln = row["estimated_cost_pln"] or usd_to_pln(row["estimated_cost_usd"])
        total_tokens = int(row["total_tokens"] or 0)
        billing_status = row["billing_status"]
        if not billing_status:
            if row["cache_outcome"] == "hit" and total_tokens == 0:
                billing_status = "cache_hit"
            elif total_tokens > 0:
                billing_status = "paid"
            elif row["outcome"] == "failed":
                billing_status = "usage_unavailable"
            else:
                billing_status = "no_usage"
        conn.execute(
            """UPDATE ai_usage_events
               SET event_id = ?, event_key = ?, estimated_cost_pln = ?, fx_rate = ?,
                   fx_version = ?, billing_status = ?
               WHERE id = ?""",
            (
                event_id,
                event_key,
                cost_pln,
                row["fx_rate"] or str(USD_PLN_FX_RATE),
                row["fx_version"] or f"legacy-backfill-{USD_PLN_FX_VERSION}",
                billing_status,
                row["id"],
            ),
        )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ai_usage_events_event_id ON ai_usage_events(event_id)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ai_usage_events_event_key ON ai_usage_events(event_key)"
    )
