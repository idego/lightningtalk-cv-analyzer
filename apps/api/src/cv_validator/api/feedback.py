from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TARGET_NAMESPACE = UUID("b1541b7f-e1ec-44b2-bac8-e30bf2445772")
CONTACT_RE = re.compile(r"(?i)(?:https?://|www\.)\S+|[\w.+-]+@[\w.-]+\.[a-z]{2,}|(?:\+?\d[\d ()-]{7,}\d)")


class TargetKind(StrEnum):
    REVIEW_FINDING = "review_finding"
    STRUCTURED_FACT = "structured_fact"
    STRUCTURAL_OBSERVATION = "structural_observation"
    FILE_DETAIL = "file_detail"
    LINK_RESULT = "link_result"
    COMPANY_RESEARCH_RESULT = "company_research_result"
    EDUCATION_RESEARCH_RESULT = "education_research_result"
    LINKEDIN_RESEARCH_RESULT = "linkedin_research_result"
    OPERATION_FAILURE = "operation_failure"
    REPORT_OVERALL = "report_overall"


class Rating(StrEnum):
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"


class Reason(StrEnum):
    INACCURATE = "inaccurate"
    MISSING_CONTEXT = "missing_context"
    MISLEADING_IMPORTANCE = "misleading_importance"
    DUPLICATE = "duplicate"
    UNCLEAR = "unclear"
    STALE_RESEARCH = "stale_research"
    WRONG_SOURCE = "wrong_source"
    OTHER = "other"
    OPERATION_FAILED = "operation_failed"


class TriageStatus(StrEnum):
    NEW = "new"
    REVIEWING = "reviewing"
    PLANNED = "planned"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"


class FeedbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: Rating | None = None
    reason: Reason | None = None
    comment: str | None = Field(default=None, max_length=180)
    context_label: str | None = Field(default=None, max_length=200)
    context_text: str | None = Field(default=None, max_length=12000)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if CONTACT_RE.search(normalized):
            raise ValueError("comment_contains_contact_data")
        return normalized or None

    @field_validator("context_label", "context_text")
    @classmethod
    def normalize_context(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def validate_combination(self) -> "FeedbackInput":
        if self.rating == Rating.HELPFUL and self.reason is not None:
            raise ValueError("helpful_reason_not_allowed")
        if self.rating != Rating.NOT_HELPFUL and self.reason is not None:
            raise ValueError("reason_requires_not_helpful")
        if self.reason == Reason.OPERATION_FAILED:
            return self
        if self.comment is not None and len(self.comment) < 12:
            raise ValueError("comment_too_short")
        if not self.comment and not (
            self.rating == Rating.HELPFUL
            or (self.rating == Rating.NOT_HELPFUL and self.reason)
        ):
            raise ValueError("comment_or_negative_reason_required")
        return self


class TriageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: TriageStatus
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if CONTACT_RE.search(normalized):
            raise ValueError("note_contains_contact_data")
        return normalized or None


def init_feedback_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS feedback_targets (
          target_id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, kind TEXT NOT NULL,
          source_category TEXT NOT NULL, source_key TEXT NOT NULL, versions_json TEXT NOT NULL,
          created_at TEXT NOT NULL, UNIQUE(analysis_id, kind, source_category, source_key),
          FOREIGN KEY(analysis_id) REFERENCES reports(analysis_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS feedback_targets_analysis ON feedback_targets(analysis_id);
        CREATE TABLE IF NOT EXISTS feedback_responses (
          target_id TEXT NOT NULL, actor_hash TEXT NOT NULL, rating TEXT, reason TEXT,
          comment TEXT, actor_email TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, withdrawn_at TEXT,
          PRIMARY KEY(target_id, actor_hash),
          FOREIGN KEY(target_id) REFERENCES feedback_targets(target_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS feedback_responses_active ON feedback_responses(withdrawn_at, updated_at);
        CREATE TABLE IF NOT EXISTS feedback_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, target_id TEXT NOT NULL, actor_hash TEXT NOT NULL,
          event_type TEXT NOT NULL, rating TEXT, reason TEXT, created_at TEXT NOT NULL,
          FOREIGN KEY(target_id) REFERENCES feedback_targets(target_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS feedback_triage (
          target_id TEXT NOT NULL, actor_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new',
          note TEXT, maintainer_hash TEXT, updated_at TEXT NOT NULL,
          PRIMARY KEY(target_id, actor_hash),
          FOREIGN KEY(target_id, actor_hash) REFERENCES feedback_responses(target_id, actor_hash) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS feedback_triage_status ON feedback_triage(status, updated_at);
        CREATE TABLE IF NOT EXISTS feedback_failure_context (
          target_id TEXT PRIMARY KEY, operation_kind TEXT NOT NULL, error_code TEXT NOT NULL,
          retryable INTEGER, attempt_count INTEGER NOT NULL, occurred_at TEXT NOT NULL,
          correlation_id TEXT NOT NULL, versions_json TEXT NOT NULL,
          FOREIGN KEY(target_id) REFERENCES feedback_targets(target_id) ON DELETE CASCADE
        );
        """
    )
    response_columns = {row[1] for row in conn.execute("PRAGMA table_info(feedback_responses)")}
    if "context_label" not in response_columns:
        conn.execute("ALTER TABLE feedback_responses ADD COLUMN context_label TEXT")
    if "context_text" not in response_columns:
        conn.execute("ALTER TABLE feedback_responses ADD COLUMN context_text TEXT")
    if "actor_email" not in response_columns:
        conn.execute("ALTER TABLE feedback_responses ADD COLUMN actor_email TEXT")


class FeedbackStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        with self._connect() as conn:
            init_feedback_schema(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def pseudonym(self, purpose: Literal["actor", "maintainer"], value: str) -> str:
        return hashlib.sha256(f"{purpose}:{value}".encode()).hexdigest()

    def materialize(self, analysis_id: str, payload: dict[str, Any], *, include_failures: bool = True) -> list[dict[str, Any]]:
        candidates = [candidate for candidate in _target_candidates(payload) if include_failures or candidate[0] != TargetKind.OPERATION_FAILURE]
        now = _now()
        with self._connect() as conn:
            for kind, category, key, versions, failure in candidates:
                target_id = str(uuid5(TARGET_NAMESPACE, f"{analysis_id}:{kind}:{category}:{key}"))
                conn.execute(
                    "INSERT OR IGNORE INTO feedback_targets VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (target_id, analysis_id, kind, category, key, json.dumps(versions, sort_keys=True), now),
                )
                if failure:
                    conn.execute(
                        "INSERT OR IGNORE INTO feedback_failure_context VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (target_id, failure["operation_kind"], failure["error_code"], failure["retryable"], failure["attempt_count"], failure["occurred_at"], failure["correlation_id"], json.dumps(failure["versions"], sort_keys=True)),
                    )
        return self.manifest(analysis_id, None)["targets"]

    def manifest(self, analysis_id: str, actor: str | None) -> dict[str, Any]:
        actor_hash = self.pseudonym("actor", actor) if actor else None
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT t.*, r.rating, r.reason, r.comment, r.updated_at, r.withdrawn_at
                   FROM feedback_targets t LEFT JOIN feedback_responses r
                   ON r.target_id=t.target_id AND r.actor_hash=? WHERE t.analysis_id=? ORDER BY t.created_at, t.target_id""",
                (actor_hash, analysis_id),
            ).fetchall()
        return {"analysis_id": analysis_id, "targets": [_manifest_row(row) for row in rows]}

    def put(self, analysis_id: str, target_id: str, actor: str, value: FeedbackInput, *, actor_email: str | None = None) -> dict[str, Any] | None:
        actor_hash = self.pseudonym("actor", actor)
        normalized_email = actor_email.strip().lower()[:320] if actor_email else None
        now = _now()
        with self._connect() as conn:
            target = conn.execute("SELECT kind FROM feedback_targets WHERE target_id=? AND analysis_id=?", (target_id, analysis_id)).fetchone()
            if target is None:
                return None
            since = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            writes = conn.execute("SELECT COUNT(*) FROM feedback_events WHERE actor_hash=? AND created_at>=?", (actor_hash, since)).fetchone()[0]
            if writes >= 30:
                raise ValueError("feedback_rate_limit")
            if target["kind"] == TargetKind.OPERATION_FAILURE:
                if value.rating != Rating.NOT_HELPFUL or value.reason != Reason.OPERATION_FAILED:
                    raise ValueError("failure_feedback_is_closed")
            existing = conn.execute("SELECT rating, reason, comment, context_label, context_text, actor_email, withdrawn_at FROM feedback_responses WHERE target_id=? AND actor_hash=?", (target_id, actor_hash)).fetchone()
            equivalent = existing and existing["withdrawn_at"] is None and (existing["rating"], existing["reason"], existing["comment"], existing["context_label"], existing["context_text"], existing["actor_email"]) == (value.rating, value.reason, value.comment, value.context_label, value.context_text, normalized_email)
            if not equivalent:
                conn.execute(
                    """INSERT INTO feedback_responses(
                         target_id,actor_hash,rating,reason,comment,created_at,updated_at,withdrawn_at,context_label,context_text,actor_email
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
                       ON CONFLICT(target_id, actor_hash) DO UPDATE SET rating=excluded.rating, reason=excluded.reason,
                       comment=excluded.comment, updated_at=excluded.updated_at, withdrawn_at=NULL,
                       context_label=excluded.context_label, context_text=excluded.context_text, actor_email=excluded.actor_email""",
                    (target_id, actor_hash, value.rating, value.reason, value.comment, now, now, value.context_label, value.context_text, normalized_email),
                )
                conn.execute("INSERT INTO feedback_events(target_id,actor_hash,event_type,rating,reason,created_at) VALUES(?,?,?,?,?,?)", (target_id, actor_hash, "submitted", value.rating, value.reason, now))
                conn.execute("INSERT OR IGNORE INTO feedback_triage(target_id,actor_hash,status,updated_at) VALUES(?,?,?,?)", (target_id, actor_hash, TriageStatus.NEW, now))
            row = conn.execute("SELECT rating,reason,comment,updated_at FROM feedback_responses WHERE target_id=? AND actor_hash=?", (target_id, actor_hash)).fetchone()
        return {**dict(row), "target_kind": target["kind"]}

    def withdraw(self, analysis_id: str, target_id: str, actor: str) -> bool | None:
        actor_hash = self.pseudonym("actor", actor)
        now = _now()
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM feedback_targets WHERE target_id=? AND analysis_id=?", (target_id, analysis_id)).fetchone() is None:
                return None
            result = conn.execute("UPDATE feedback_responses SET rating=NULL,reason=NULL,comment=NULL,updated_at=?,withdrawn_at=? WHERE target_id=? AND actor_hash=? AND withdrawn_at IS NULL", (now, now, target_id, actor_hash))
            if result.rowcount:
                conn.execute("DELETE FROM feedback_triage WHERE target_id=? AND actor_hash=?", (target_id, actor_hash))
                conn.execute("INSERT INTO feedback_events(target_id,actor_hash,event_type,created_at) VALUES(?,?,?,?)", (target_id, actor_hash, "withdrawn", now))
            return bool(result.rowcount)

    def inbox(self, *, limit: int = 50, cursor: int = 0, filters: dict[str, str | None] | None = None) -> dict[str, Any]:
        filters = filters or {}
        clauses = ["r.withdrawn_at IS NULL"]
        params: list[Any] = []
        mapping = {"rating": "r.rating", "reason": "r.reason", "kind": "t.kind", "status": "COALESCE(g.status,'new')", "source": "t.source_category", "operation": "f.operation_kind", "error_code": "f.error_code"}
        for key, column in mapping.items():
            if filters.get(key):
                clauses.append(f"{column}=?")
                params.append(filters[key])
        if filters.get("version"):
            clauses.append("t.versions_json LIKE ?")
            params.append(f"%{str(filters['version'])[:80]}%")
        if filters.get("date_from"):
            clauses.append("r.updated_at>=?")
            params.append(filters["date_from"])
        if filters.get("date_to"):
            clauses.append("r.updated_at<=?")
            params.append(filters["date_to"])
        params.extend([cursor, min(max(limit, 1), 100) + 1])
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT r.rowid AS cursor,t.target_id,t.analysis_id,t.kind,t.source_category,t.source_key,t.versions_json,
                    r.actor_hash,r.actor_email,r.rating,r.reason,r.comment,r.context_label,r.context_text,r.updated_at,COALESCE(g.status,'new') AS triage_status,g.note,
                    f.operation_kind,f.error_code,f.retryable,f.attempt_count,f.occurred_at,f.correlation_id,f.versions_json AS failure_versions
                    FROM feedback_responses r JOIN feedback_targets t ON t.target_id=r.target_id
                    LEFT JOIN feedback_triage g ON g.target_id=r.target_id AND g.actor_hash=r.actor_hash
                    LEFT JOIN feedback_failure_context f ON f.target_id=t.target_id
                    WHERE {' AND '.join(clauses)} AND r.rowid>? ORDER BY r.rowid LIMIT ?""",
                params,
            ).fetchall()
            counts = {row["triage_status"]: row["count"] for row in conn.execute("SELECT COALESCE(g.status,'new') triage_status,COUNT(*) count FROM feedback_responses r LEFT JOIN feedback_triage g ON g.target_id=r.target_id AND g.actor_hash=r.actor_hash WHERE r.withdrawn_at IS NULL GROUP BY triage_status")}
        page_limit = min(max(limit, 1), 100)
        return {"items": [_inbox_row(row) for row in rows[:page_limit]], "counts": counts, "next_cursor": rows[page_limit - 1]["cursor"] if len(rows) > page_limit else None}

    def triage(self, target_id: str, actor_hash: str, maintainer: str, value: TriageInput) -> bool:
        now = _now()
        with self._connect() as conn:
            result = conn.execute("UPDATE feedback_triage SET status=?,note=?,maintainer_hash=?,updated_at=? WHERE target_id=? AND actor_hash=?", (value.status, value.note, self.pseudonym("maintainer", maintainer), now, target_id, actor_hash))
        return bool(result.rowcount)

    def delete_response(self, target_id: str, actor_hash: str) -> bool:
        with self._connect() as conn:
            result = conn.execute(
                "DELETE FROM feedback_responses WHERE target_id=? AND actor_hash=?",
                (target_id, actor_hash),
            )
        return bool(result.rowcount)


def _target_candidates(payload: dict[str, Any]):
    versions = _versions(payload)
    yield TargetKind.REPORT_OVERALL, "report", "overall", versions, None
    yield from _presentation_feedback_candidates(payload, versions)
    for finding in payload.get("review_findings") or payload.get("findings") or []:
        if isinstance(finding, dict) and isinstance(finding.get("id"), str):
            yield TargetKind.REVIEW_FINDING, "finding", finding["id"], versions, None
    base_analysis = payload.get("base_analysis") if isinstance(payload.get("base_analysis"), dict) else {}
    for category in ("employment", "education"):
        for value in base_analysis.get(category, []) if isinstance(base_analysis.get(category), list) else []:
            if isinstance(value, dict) and isinstance(value.get("id"), str):
                yield TargetKind.STRUCTURED_FACT, category, value["id"], versions, None
    deterministic = payload.get("deterministic") if isinstance(payload.get("deterministic"), dict) else {}
    for category in ("candidates", "facts"):
        for value in deterministic.get(category, []) if isinstance(deterministic.get(category), list) else []:
            if isinstance(value, dict) and isinstance(value.get("id"), str):
                yield TargetKind.STRUCTURED_FACT, category, value["id"], versions, None
    understanding = payload.get("document_understanding") if isinstance(payload.get("document_understanding"), dict) else {}
    for category in ("records", "skills"):
        for value in understanding.get(category, []) if isinstance(understanding.get(category), list) else []:
            if isinstance(value, dict) and isinstance(value.get("id"), str):
                yield TargetKind.STRUCTURED_FACT, category, value["id"], versions, None
    structural = payload.get("structural_audits") or []
    if isinstance(structural, dict):
        structural = structural.get("observations") or structural.get("audits") or []
    for item in structural if isinstance(structural, list) else []:
        if isinstance(item, dict) and isinstance(item.get("id") or item.get("code"), str):
            yield TargetKind.STRUCTURAL_OBSERVATION, "structural", item.get("id") or item["code"], versions, None
    for item in deterministic.get("observations", []) if isinstance(deterministic.get("observations"), list) else []:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            yield TargetKind.STRUCTURAL_OBSERVATION, "deterministic", item["id"], versions, None
    details = payload.get("file_details", {}).get("fields", {}) if isinstance(payload.get("file_details"), dict) else {}
    for field in details if isinstance(details, dict) else []:
        yield TargetKind.FILE_DETAIL, "file_detail", field, versions, None
    links = payload.get("link_inspection", {}).get("links", []) if isinstance(payload.get("link_inspection"), dict) else []
    for link in links if isinstance(links, list) else []:
        if isinstance(link, dict) and isinstance(link.get("link_id"), str):
            yield TargetKind.LINK_RESULT, "link", link["link_id"], versions, None
    for key, kind in (("company_research", TargetKind.COMPANY_RESEARCH_RESULT), ("education_research", TargetKind.EDUCATION_RESEARCH_RESULT), ("linkedin_discovery", TargetKind.LINKEDIN_RESEARCH_RESULT)):
        result = payload.get(key)
        if isinstance(result, dict) and result.get("status") == "completed":
            values = result.get("organizations") or result.get("credentials") or result.get("possible_profiles") or []
            for index, _ in enumerate(values if isinstance(values, list) else []):
                yield kind, key, str(index), versions, None
        elif isinstance(result, dict) and result.get("status") == "failed":
            yield TargetKind.OPERATION_FAILURE, key, "failure", versions, _failure(key, result, versions)
    ai = payload.get("ai_analysis")
    if isinstance(ai, dict) and ai.get("status") == "failed":
        yield TargetKind.OPERATION_FAILURE, "ai_analysis", "failure", versions, _failure("ai_analysis", ai, versions)


def _presentation_feedback_candidates(payload: dict[str, Any], versions: dict[str, str]):
    base = payload.get("base_analysis") if isinstance(payload.get("base_analysis"), dict) else {}
    profile = base.get("profile") if isinstance(base.get("profile"), dict) else {}
    review = base.get("review") if isinstance(base.get("review"), dict) else {}
    mechanical = payload.get("mechanical") if isinstance(payload.get("mechanical"), dict) else {}

    def evidence(value: Any) -> list[Any]:
        if not isinstance(value, dict):
            return []
        direct = value.get("evidence")
        if isinstance(direct, list) and direct:
            return direct
        for nested in value.values():
            if isinstance(nested, dict) and isinstance(nested.get("evidence"), list) and nested["evidence"]:
                return nested["evidence"]
        return []

    locations = mechanical.get("location_resolution") if isinstance(mechanical.get("location_resolution"), list) else []
    location = next((item for item in locations if isinstance(item, dict) and item.get("subject") == "declared_location"), None)
    if isinstance(location, dict) and location.get("status") not in {None, "unavailable"} and evidence(location):
        relationship = location.get("city_country_relationship") if isinstance(location.get("city_country_relationship"), str) else "null"
        section = "attention" if relationship == "different" else "worth_knowing"
        yield TargetKind.REVIEW_FINDING, section, f"location-{location['status']}-{relationship}", versions, None

    comparisons = mechanical.get("comparisons") if isinstance(mechanical.get("comparisons"), list) else []
    seen_comparisons: set[tuple[Any, ...]] = set()
    grouped: dict[str, list[dict[str, Any]]] = {"same": [], "different": []}
    for item in comparisons:
        if not isinstance(item, dict) or item.get("relationship") not in grouped:
            continue
        key = (
            item.get("kind"), item.get("relationship"),
            tuple(item.get("declared_country_codes") or []),
            tuple(item.get("phone_country_codes") or []),
        )
        if key in seen_comparisons:
            continue
        seen_comparisons.add(key)
        grouped[item["relationship"]].append(item)
    for relationship, items in grouped.items():
        section = "remaining" if relationship == "same" else "attention"
        for index, _item in enumerate(items):
            yield TargetKind.REVIEW_FINDING, section, f"comparison-{relationship}-{index}", versions, None

    email_findings = mechanical.get("email_findings") if isinstance(mechanical.get("email_findings"), list) else []
    seen_emails: set[tuple[Any, ...]] = set()
    email_index = 0
    for item in email_findings:
        if not isinstance(item, dict) or not evidence(item):
            continue
        key = (item.get("kind"), item.get("observed_domain"), item.get("suggested_domain"))
        if key in seen_emails:
            continue
        seen_emails.add(key)
        yield TargetKind.REVIEW_FINDING, "attention", f"email-{email_index}", versions, None
        email_index += 1

    gaps = review.get("coverage_gaps") if isinstance(review.get("coverage_gaps"), list) else []
    seen_gaps: set[tuple[Any, ...]] = set()
    gap_index = 0
    for item in gaps:
        if not isinstance(item, dict) or not evidence(item):
            continue
        reason = str(item.get("reason_code") or "")
        if re.match(r"^(?:invalid|unknown|unsafe|reviewer)(?:_|$)", reason):
            continue
        key = (item.get("target"), item.get("reason_code"), tuple(item.get("source_block_ids") or []))
        if key in seen_gaps:
            continue
        seen_gaps.add(key)
        yield TargetKind.REVIEW_FINDING, "worth_knowing", f"gap-{gap_index}", versions, None
        gap_index += 1

    linkedin = payload.get("linkedin_discovery")
    candidate = profile.get("candidate_name") if isinstance(profile.get("candidate_name"), dict) else {}
    if isinstance(linkedin, dict) and linkedin.get("status") == "completed" and linkedin.get("linkedin_not_found") and evidence(candidate):
        yield TargetKind.REVIEW_FINDING, "attention", "linkedin-not-found", versions, None


def _failure(operation: str, value: dict[str, Any], versions: dict[str, str]) -> dict[str, Any]:
    failure = value.get("failure") if isinstance(value.get("failure"), dict) else {}
    occurred = value.get("created_at") if isinstance(value.get("created_at"), str) else _now()
    correlation = value.get("correlation_id") if isinstance(value.get("correlation_id"), str) else str(uuid5(TARGET_NAMESPACE, f"diagnostic:{operation}:{occurred}"))
    return {"operation_kind": operation, "error_code": str(value.get("failure_reason") or "diagnostics_unavailable")[:64], "retryable": int(bool(failure.get("retryable"))) if failure.get("retryable") is not None else None, "attempt_count": max(1, int(value.get("attempt_count") or failure.get("attempt_count") or 1)), "occurred_at": occurred, "correlation_id": correlation, "versions": versions}


def _versions(payload: dict[str, Any]) -> dict[str, str]:
    strategy = payload.get("strategy") if isinstance(payload.get("strategy"), dict) else {}
    values = {
        "contract": str(payload.get("contract_version") or "unknown")[:80],
        "strategy": str(strategy.get("version") or "unknown")[:80],
    }
    ai = payload.get("ai_analysis")
    if isinstance(ai, dict) and isinstance(ai.get("versions"), dict):
        for key in ("prompt", "schema", "input_contract", "deterministic_observations"):
            if isinstance(ai["versions"].get(key), str):
                values[key] = ai["versions"][key][:80]
    return values


def _manifest_row(row: sqlite3.Row) -> dict[str, Any]:
    response = None if row["updated_at"] is None or row["withdrawn_at"] is not None else {"rating": row["rating"], "reason": row["reason"], "comment": row["comment"], "updated_at": row["updated_at"]}
    return {"target_id": row["target_id"], "kind": row["kind"], "source_category": row["source_category"], "source_key": row["source_key"], "versions": json.loads(row["versions_json"]), "response": response}


def _inbox_row(row: sqlite3.Row) -> dict[str, Any]:
    failure = None if row["operation_kind"] is None else {key: row[key] for key in ("operation_kind", "error_code", "retryable", "attempt_count", "occurred_at", "correlation_id")}
    return {"cursor": row["cursor"], "target_id": row["target_id"], "analysis_id": row["analysis_id"], "kind": row["kind"], "source_category": row["source_category"], "source_key": row["source_key"], "versions": json.loads(row["versions_json"]), "actor_hash": row["actor_hash"], "actor_email": row["actor_email"], "rating": row["rating"], "reason": row["reason"], "comment": row["comment"], "context_label": row["context_label"], "context_text": row["context_text"], "updated_at": row["updated_at"], "triage_status": row["triage_status"], "triage_note": row["note"], "failure": failure}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
