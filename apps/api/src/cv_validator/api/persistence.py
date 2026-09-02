from __future__ import annotations

import json
import sqlite3
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from cv_validator.analysis import validate_analysis_report
from cv_validator.api.feedback import init_feedback_schema
from cv_validator.errors import AnalysisNotFoundPersistenceError, PersistenceError
from cv_validator.serialization import deserialize_analysis_payload


@dataclass
class PersistenceConfig:
    db_path: Path
    retention_days: int = 90
    research_cache_ttl_days: int = 30


class PersistenceStore:
    def __init__(self, config: PersistenceConfig) -> None:
        self.config = config
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
                CREATE TABLE IF NOT EXISTS runtime_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            init_feedback_schema(conn)
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS reports_analysis_id ON reports(analysis_id)"
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS audit_log_analysis_id ON audit_log(analysis_id)"
            )

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
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("report persistence failed") from exc
        return selected_analysis_id

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
                          reports.status, reports.created_at, audit_log.output_json
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
                }
            )
        return history

    def analysis_access_allowed(self, analysis_id: str, access_token: str | None) -> bool:
        if not access_token:
            return False
        with self._connect() as conn:
            row = conn.execute("SELECT access_token_hash FROM reports WHERE analysis_id = ?", (analysis_id,)).fetchone()
        return row is not None and isinstance(row["access_token_hash"], str) and hmac.compare_digest(row["access_token_hash"], _token_hash(access_token))

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
                "research_cache_audit",
                "company_research",
                "education_research",
                "linkedin_discovery",
                "linkedin_comparison",
                "linkedin_confirmation",
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
                ("audit_log", "created_at"),
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
                              "linkedin_discovery", "linkedin_comparison", "linkedin_confirmation", "audit_log"):
                    deleted[table] = conn.execute(f"DELETE FROM {table} WHERE analysis_id IN ({placeholders})", expired_ids).rowcount
                deleted["reports"] = conn.execute(f"DELETE FROM reports WHERE analysis_id IN ({placeholders})", expired_ids).rowcount
            deleted["reusable_research_cache"] = conn.execute("DELETE FROM reusable_research_cache WHERE expires_at <= ?", (_utc_now(),)).rowcount
            deleted["analysis_ids"] = tuple(expired_ids)
            if expired_ids and self._purge_listener is not None:
                self._purge_listener(tuple(expired_ids))
        return deleted


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
