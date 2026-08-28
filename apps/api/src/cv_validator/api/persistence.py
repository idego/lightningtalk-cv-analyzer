from __future__ import annotations

import json
import sqlite3
import hashlib
import hmac
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from cv_validator.domain import (
    LinkAssociation,
    LinkReasonCode,
    LinkRole,
    LinkSource,
    Report,
)
from cv_validator.errors import PersistenceError
from cv_validator.file_links.normalization import URLNormalizationError, normalize_url
from cv_validator.ingestion import RedactedDocumentIdentity
from cv_validator.ingestion.redaction import MASK_CHARACTER
from cv_validator.serialization import deserialize_analysis_payload, serialize_report_payload


_SAFE_NATIONAL_ID_TYPES = frozenset(
    {"LABELED_NATIONAL_ID", "PL_PESEL", "UK_NINO", "US_SSN"}
)
_URL_TOKEN_RE = re.compile(r"(?i)(?:https?://|www\.)[^\s<>\"']+")


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
                    created_at TEXT NOT NULL,
                    analysis_id TEXT,
                    access_token_hash TEXT,
                    source_filename TEXT,
                    file_details_json TEXT,
                    link_inspection_json TEXT
                );
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    input_hash TEXT NOT NULL,
                    ruleset_version TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    analysis_id TEXT
                );
                CREATE TABLE IF NOT EXISTS ai_analyses (
                    analysis_id TEXT PRIMARY KEY,
                    input_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    authority TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    input_contract_version TEXT NOT NULL,
                    deterministic_observations_version TEXT NOT NULL,
                    configured_model TEXT NOT NULL,
                    response_model TEXT,
                    usage_json TEXT,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
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
            _ensure_column(conn, "reports", "analysis_id", "TEXT")
            _ensure_column(conn, "reports", "access_token_hash", "TEXT")
            _ensure_column(conn, "reports", "source_filename", "TEXT")
            _ensure_column(conn, "reports", "file_details_json", "TEXT")
            _ensure_column(conn, "reports", "link_inspection_json", "TEXT")
            _ensure_column(conn, "audit_log", "analysis_id", "TEXT")
            conn.execute(
                "UPDATE reports SET analysis_id = 'legacy-' || id WHERE analysis_id IS NULL"
            )
            conn.execute(
                "UPDATE audit_log SET analysis_id = 'legacy-' || id WHERE analysis_id IS NULL"
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS reports_analysis_id ON reports(analysis_id)"
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS audit_log_analysis_id ON audit_log(analysis_id)"
            )

    def persist_report(
        self,
        identity: RedactedDocumentIdentity,
        report: Report,
        *,
        report_payload: dict[str, Any] | None = None,
        analysis_id: str | None = None,
        ai_analysis: dict[str, Any] | None = None,
        access_token: str | None = None,
        source_filename: str | None = None,
    ) -> str:
        selected_analysis_id = analysis_id or str(uuid4())
        payload = (
            serialize_report_payload(report)
            if report_payload is None
            else report_payload
        )
        findings = _sanitize_findings(payload)
        input_hash = identity.digest
        now = _utc_now()
        try:
            self.purge_expired()
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO reports (
                        input_hash, ruleset_version, score, band, findings_json,
                        created_at, analysis_id, access_token_hash, source_filename,
                        file_details_json, link_inspection_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        input_hash,
                        report.ruleset_version.audit_identity,
                        report.score,
                        report.band.value,
                        json.dumps(findings["findings"]),
                        now,
                        selected_analysis_id,
                        _token_hash(access_token) if access_token else None,
                        source_filename,
                        _json_or_none(findings.get("file_details")),
                        _json_or_none(findings.get("link_inspection")),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO audit_log (
                        input_hash, ruleset_version, output_json, created_at,
                        analysis_id
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        input_hash,
                        report.ruleset_version.audit_identity,
                        json.dumps(findings),
                        now,
                        selected_analysis_id,
                    ),
                )
                if ai_analysis is not None:
                    _insert_ai_analysis(
                        conn,
                        analysis_id=selected_analysis_id,
                        input_hash=input_hash,
                        ai_analysis=ai_analysis,
                        created_at=now,
                    )
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("report persistence failed") from exc
        return selected_analysis_id

    def get_audit_entries(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def get_ai_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM ai_analyses WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()
        return None if row is None else dict(row)

    def get_analysis_payload(self, analysis_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT output_json FROM audit_log WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()
        return None if row is None else deserialize_analysis_payload(
            json.loads(row["output_json"])
        )

    def replace_ai_analysis(
        self,
        analysis_id: str,
        payload: dict[str, Any],
    ) -> None:
        ai_analysis = payload["ai_analysis"]
        now = _utc_now()
        try:
            with self._connect() as conn:
                report = conn.execute(
                    "SELECT input_hash FROM reports WHERE analysis_id = ?",
                    (analysis_id,),
                ).fetchone()
                if report is None:
                    raise PersistenceError("analysis not found")
                existing_row = conn.execute(
                    "SELECT output_json FROM audit_log WHERE analysis_id = ?",
                    (analysis_id,),
                ).fetchone()
                if existing_row is not None:
                    existing_payload = json.loads(existing_row["output_json"])
                    payload = deepcopy(payload)
                    payload["structural_audits"] = existing_payload.get(
                        "structural_audits"
                    )
                conn.execute(
                    "UPDATE audit_log SET output_json = ? WHERE analysis_id = ?",
                    (json.dumps(_sanitize_findings(payload)), analysis_id),
                )
                sanitized = _sanitize_findings(payload)
                conn.execute(
                    "UPDATE reports SET file_details_json = ?, link_inspection_json = ? WHERE analysis_id = ?",
                    (
                        _json_or_none(sanitized.get("file_details")),
                        _json_or_none(sanitized.get("link_inspection")),
                        analysis_id,
                    ),
                )
                conn.execute("DELETE FROM ai_analyses WHERE analysis_id = ?", (analysis_id,))
                _insert_ai_analysis(
                    conn,
                    analysis_id=analysis_id,
                    input_hash=report["input_hash"],
                    ai_analysis=ai_analysis,
                    created_at=now,
                )
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("AI analysis persistence failed") from exc

    def list_analyses(self, access_token: str | None) -> list[dict[str, Any]]:
        if not access_token:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT reports.analysis_id, reports.source_filename,
                          reports.band, reports.created_at, audit_log.output_json
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
                    "band": row["band"],
                    "summary": payload.get("summary", ""),
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
                "ai_analyses",
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
                conn.execute(
                    """
                    INSERT INTO company_research (
                        analysis_id, research_version, status, prompt_version,
                        schema_version, configured_model, response_model,
                        accessed_at, usage_json, result_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(analysis_id, research_version) DO NOTHING
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
                conn.execute(
                    """INSERT INTO education_research (
                        analysis_id, research_version, status, prompt_version,
                        schema_version, configured_model, response_model,
                        accessed_at, usage_json, result_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(analysis_id, research_version) DO NOTHING""",
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
        with self._connect() as conn:
            conn.execute("INSERT INTO research_cache_audit (analysis_id, category, cache_key, outcome, created_at) VALUES (?, ?, ?, ?, ?)",
                         (analysis_id, category, cache_key, outcome, _utc_now()))

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
                conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) ON CONFLICT(analysis_id, research_version) DO NOTHING", values)
        except (OSError, sqlite3.Error) as exc: raise PersistenceError("linkedin research persistence failed") from exc

    def persist_analysis_payload_for_test(self, payload: dict[str, Any]) -> None:
        """Seed an anonymous stored payload without constructing an uploaded CV."""
        now = _utc_now()
        analysis_id = payload["analysis_id"]
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO reports (input_hash, ruleset_version, score, band, findings_json, created_at, analysis_id, access_token_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("test-redacted-hash", "test-rules", payload["score"], payload["band"], "[]", now, analysis_id, _token_hash("test-access-token")),
            )
            conn.execute(
                "INSERT INTO audit_log (input_hash, ruleset_version, output_json, created_at, analysis_id) VALUES (?, ?, ?, ?, ?)",
                ("test-redacted-hash", "test-rules", json.dumps(payload), now, analysis_id),
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
                ("ai_analyses", "created_at"),
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
                for table in ("research_cache_audit", "ai_analyses", "company_research", "education_research",
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
    contact = payload.get("ai_analysis", {}).get("facts", {}).get("contact", [])
    for fact in contact:
        if fact.get("kind") == "candidate_name" and isinstance(fact.get("value"), str):
            value = fact["value"].strip()
            if value:
                return value
    return None


def _ensure_column(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    declaration: str,
) -> None:
    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")


def _insert_ai_analysis(
    conn: sqlite3.Connection,
    *,
    analysis_id: str,
    input_hash: str,
    ai_analysis: dict[str, Any],
    created_at: str,
) -> None:
    versions = ai_analysis["versions"]
    model = ai_analysis["model"]
    conn.execute(
        """
        INSERT INTO ai_analyses (
            analysis_id, input_hash, status, authority, prompt_version,
            schema_version, input_contract_version,
            deterministic_observations_version, configured_model,
            response_model, usage_json, result_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            analysis_id,
            input_hash,
            ai_analysis["status"],
            ai_analysis["authority"],
            versions["prompt"],
            versions["schema"],
            versions["input_contract"],
            versions["deterministic_observations"],
            model["configured"],
            model["response"],
            json.dumps(ai_analysis["usage"]),
            json.dumps(ai_analysis),
            created_at,
        ),
    )


def _sanitize_findings(report_dict: dict[str, Any]) -> dict[str, Any]:
    from cv_validator.structural.sanitize import sanitize_structural_audits

    sanitized = deepcopy(report_dict)
    sanitized["structural_audits"] = sanitize_structural_audits(
        sanitized.get("structural_audits")
    )
    for finding in sanitized.get("findings", []):
        if not isinstance(finding, dict):
            continue
        if finding.get("signal") == "national_id":
            if not _is_safe_national_id_metadata(finding.get("observed")):
                finding["observed"] = "present:REDACTED"
            finding["claimed"] = None
            for evidence in finding.get("evidence", []):
                excerpt = evidence.get("excerpt")
                if not _is_masked_excerpt(excerpt):
                    evidence["excerpt"] = (
                        MASK_CHARACTER * len(excerpt)
                        if isinstance(excerpt, str)
                        else ""
                    )
    if "file_details" in sanitized:
        sanitized["file_details"] = _sanitize_file_details(sanitized["file_details"])
    if "link_inspection" in sanitized:
        sanitized["link_inspection"] = _sanitize_link_inspection(
            sanitized["link_inspection"]
        )
    return sanitized


def _sanitize_file_details(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        return None
    allowed_fields = {
        "author",
        "creator",
        "producer",
        "title",
        "subject",
        "creation_time",
        "modification_time",
        "created",
        "modified",
        "last_modifier",
        "revision",
    }
    fields = value.get("fields")
    if not isinstance(fields, dict):
        return None
    clean_fields: dict[str, Any] = {}
    for field_name, field in fields.items():
        if field_name not in allowed_fields or not isinstance(field, dict):
            continue
        status = field.get("status")
        raw_value = field.get("value")
        if status == "available" and isinstance(raw_value, str):
            clean_value = _safe_text(raw_value, limit=1024)
            if clean_value:
                clean_fields[field_name] = {
                    "value": clean_value,
                    "status": "available",
                    "source_format": _safe_text(field.get("source_format"), limit=32),
                    "extractor_version": _safe_version(field.get("extractor_version")),
                }
                continue
        clean_fields[field_name] = {
            "value": None,
            "status": "unavailable",
            "source_format": _safe_text(field.get("source_format"), limit=32),
            "extractor_version": _safe_version(field.get("extractor_version")),
        }
    return {
        "contract_version": "file-details-v1",
        "source_format": _safe_text(value.get("source_format"), limit=16),
        "extractor_version": _safe_version(value.get("extractor_version")),
        "fields": clean_fields,
    }


def _sanitize_link_inspection(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        return None
    links = value.get("links", [])
    if not isinstance(links, list):
        return None
    clean_links: list[dict[str, Any]] = []
    for index, link in enumerate(links):
        if not isinstance(link, dict):
            continue
        link_id = _safe_text(link.get("link_id"), limit=256)
        if not link_id:
            link_id = f"link:invalid:{index:04d}"
        sanitized_target = _sanitize_url(link.get("sanitized_target"))
        displayed_value = _sanitize_display_value(link.get("displayed_value"))
        source_evidence = []
        for evidence in link.get("source_evidence", []):
            if not isinstance(evidence, dict):
                continue
            excerpt = _sanitize_evidence_excerpt(evidence.get("excerpt"))
            start_offset = _safe_int(evidence.get("start_offset"))
            end_offset = _safe_int(evidence.get("end_offset"))
            if start_offset is None or end_offset is None or end_offset < start_offset:
                continue
            source_evidence.append(
                {
                    "page_id": _safe_text(evidence.get("page_id"), limit=128),
                    "page_number": _safe_int(evidence.get("page_number")),
                    "start_offset": start_offset,
                    "end_offset": end_offset,
                    "excerpt": excerpt,
                }
            )
        status = link.get("status")
        reason_code = link.get("reason_code")
        if status not in {"REACHABLE", "SUSPICIOUS", "UNAVAILABLE", "NOT_CHECKED"}:
            status = "UNAVAILABLE"
        if reason_code not in {reason.value for reason in LinkReasonCode}:
            reason_code = "invalid_link_target"
        source = link.get("source")
        if source not in {item.value for item in LinkSource}:
            source = LinkSource.EMBEDDED_HYPERLINK.value
        association = link.get("association")
        if association not in {item.value for item in LinkAssociation}:
            association = LinkAssociation.UNKNOWN.value
        role = link.get("role")
        if role not in {item.value for item in LinkRole}:
            role = LinkRole.GENERIC.value
        clean_links.append(
            {
                "link_id": link_id,
                "status": status,
                "displayed_value": displayed_value,
                "sanitized_target": sanitized_target,
                "source": source,
                "association": association,
                "role": role,
                "source_page": _safe_int(link.get("source_page")),
                "source_location": _safe_text(link.get("source_location"), limit=32),
                "source_evidence": source_evidence,
                "reason_code": reason_code,
                "terminal_status": _safe_http_status(link.get("terminal_status")),
                "terminal_registrable_domain": _safe_domain(
                    link.get("terminal_registrable_domain")
                ),
                "checked_at": _safe_text(link.get("checked_at"), limit=64),
                "configuration_version": _safe_text(
                    link.get("configuration_version"), limit=64
                ),
                "title": _safe_text(link.get("title"), limit=256),
            }
        )
    return {
        "contract_version": "link-inspection-v1",
        "checked_at": _safe_text(value.get("checked_at"), limit=64),
        "configuration_version": _safe_text(
            value.get("configuration_version"), limit=64
        ),
        "links": clean_links,
    }


def _sanitize_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return normalize_url(value, allowed_ports=tuple(range(1, 65536))).sanitized_url
    except URLNormalizationError:
        return None


def _sanitize_display_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    if any(ord(character) < 32 for character in value):
        return None
    stripped = value.strip()
    if stripped.lower().startswith(("http://", "https://")):
        return _sanitize_url(stripped)
    if stripped.lower().startswith("www."):
        sanitized = _sanitize_url(stripped)
        return sanitized.removeprefix("https://") if sanitized else None
    return _sanitize_url_tokens(value, limit=2048)


def _sanitize_evidence_excerpt(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    stripped = value.strip()
    if stripped.lower().startswith(("http://", "https://")):
        return _sanitize_url(stripped) or ""
    if stripped.lower().startswith("www."):
        sanitized = _sanitize_url(stripped)
        return sanitized.removeprefix("https://") if sanitized else ""
    return _sanitize_url_tokens(value, limit=512)


def _sanitize_url_tokens(value: str, *, limit: int) -> str:
    """Remove query/fragment data from URLs embedded in reviewer evidence."""

    def replace_token(match: re.Match[str]) -> str:
        token = match.group(0)
        trailing = ""
        while token and token[-1] in ".,;:!?)]}":
            trailing = token[-1] + trailing
            token = token[:-1]
        sanitized = _sanitize_url(token)
        if sanitized is None:
            return "[invalid-link]" + trailing
        if token.lower().startswith("www."):
            sanitized = sanitized.removeprefix("https://")
        return sanitized + trailing

    return _safe_text(_URL_TOKEN_RE.sub(replace_token, value), limit=limit)


def _safe_version(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    name = _safe_text(value.get("name"), limit=64)
    version = _safe_text(value.get("version"), limit=64)
    if not name or not version:
        return None
    return {"name": name, "version": version}


def _safe_text(value: Any, *, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    if any(ord(character) < 32 for character in value):
        return ""
    return value.strip()[:limit]


def _safe_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _safe_http_status(value: Any) -> int | None:
    return value if isinstance(value, int) and 100 <= value <= 599 else None


def _safe_domain(value: Any) -> str | None:
    if not isinstance(value, str) or any(ord(character) < 33 for character in value):
        return None
    domain = value.strip().lower().rstrip(".")
    if not domain or any(character in domain for character in "/?#@[]:"):
        return None
    try:
        return normalize_url(f"https://{domain}").registrable_domain
    except URLNormalizationError:
        return None


def _json_or_none(value: Any) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False)


def _is_safe_national_id_metadata(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("present:"):
        return False
    type_names = value.removeprefix("present:").split("+")
    return (
        bool(type_names)
        and type_names == sorted(set(type_names))
        and set(type_names) <= _SAFE_NATIONAL_ID_TYPES
    )


def _is_masked_excerpt(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and set(value) == {MASK_CHARACTER}
    )
