from __future__ import annotations

import json
import sqlite3
import hashlib
import hmac
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from cv_validator.domain import Report
from cv_validator.errors import PersistenceError
from cv_validator.ingestion import RedactedDocumentIdentity
from cv_validator.ingestion.redaction import MASK_CHARACTER
from cv_validator.serialization import serialize_report_payload


_SAFE_NATIONAL_ID_TYPES = frozenset(
    {"LABELED_NATIONAL_ID", "PL_PESEL", "UK_NINO", "US_SSN"}
)


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
                    created_at TEXT NOT NULL,
                    analysis_id TEXT,
                    access_token_hash TEXT
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
                """
            )
            _ensure_column(conn, "reports", "analysis_id", "TEXT")
            _ensure_column(conn, "reports", "access_token_hash", "TEXT")
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
            self._purge_expired()
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO reports (
                        input_hash, ruleset_version, score, band, findings_json,
                        created_at, analysis_id, access_token_hash
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
        return None if row is None else json.loads(row["output_json"])

    def analysis_access_allowed(self, analysis_id: str, access_token: str | None) -> bool:
        if not access_token:
            return False
        with self._connect() as conn:
            row = conn.execute("SELECT access_token_hash FROM reports WHERE analysis_id = ?", (analysis_id,)).fetchone()
        return row is not None and isinstance(row["access_token_hash"], str) and hmac.compare_digest(row["access_token_hash"], _token_hash(access_token))

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
                conn.execute("""INSERT INTO linkedin_confirmation (analysis_id, profile_url, discovery_version, confirmed_at, audit_json)
                    VALUES (?, ?, ?, ?, ?) ON CONFLICT(analysis_id) DO NOTHING""",
                    (analysis_id, profile_url, discovery_version, confirmed_at, json.dumps(audit)))
                row = conn.execute("SELECT profile_url, audit_json FROM linkedin_confirmation WHERE analysis_id = ?", (analysis_id,)).fetchone()
                if row is None or row["profile_url"] != profile_url: raise ValueError("different_profile_already_confirmed")
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

    def _purge_expired(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.retention_days)
        cutoff_iso = cutoff.isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM reports WHERE created_at < ?", (cutoff_iso,))
            conn.execute("DELETE FROM audit_log WHERE created_at < ?", (cutoff_iso,))
            conn.execute("DELETE FROM ai_analyses WHERE created_at < ?", (cutoff_iso,))
            conn.execute("DELETE FROM company_research WHERE created_at < ?", (cutoff_iso,))
            conn.execute("DELETE FROM education_research WHERE created_at < ?", (cutoff_iso,))
            conn.execute("DELETE FROM linkedin_discovery WHERE created_at < ?", (cutoff_iso,))
            conn.execute("DELETE FROM linkedin_comparison WHERE created_at < ?", (cutoff_iso,))
            conn.execute("DELETE FROM linkedin_confirmation WHERE confirmed_at < ?", (cutoff_iso,))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
    sanitized = deepcopy(report_dict)
    for finding in sanitized["findings"]:
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
    return sanitized


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
