from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
from cv_validator.api.persistence import PersistenceStore
from cv_validator.errors import PersistenceError
from cv_validator.profile_builder import (
    CandidateProfile,
    ProfileBuilderPreferences,
    ProfileBuilderSnapshot,
    ProfileCustomFieldDefinition,
    ProfileTemplate,
    sanitize_candidate_profile,
    sanitize_profile_builder_filename,
    sanitize_profile_builder_preferences,
    sanitize_profile_builder_snapshot,
    sanitize_profile_custom_field_definition,
    sanitize_profile_template,
)

_SHARED_TEMPLATE_SCOPE = "__profile_builder_shared__"


class ProfileBuilderStore:
    def __init__(self, analysis_store: PersistenceStore) -> None:
        self.config = analysis_store.config
        self._retention_days = analysis_store.get_retention_days
        with self._connect() as conn:
            conn.executescript('CREATE TABLE IF NOT EXISTS candidate_profiles (\n                    profile_id TEXT PRIMARY KEY,\n                    access_token_hash TEXT NOT NULL,\n                    source_filename TEXT NOT NULL,\n                    profile_json TEXT NOT NULL,\n                    anonymization_json TEXT NOT NULL,\n                    template_json TEXT NOT NULL,\n                    created_at TEXT NOT NULL,\n                    updated_at TEXT NOT NULL\n                );\n                CREATE INDEX IF NOT EXISTS candidate_profiles_owner_updated\n                    ON candidate_profiles(access_token_hash, updated_at DESC);\n                CREATE TABLE IF NOT EXISTS profile_templates (\n                    access_token_hash TEXT NOT NULL,\n                    template_id TEXT NOT NULL,\n                    name TEXT NOT NULL,\n                    template_json TEXT NOT NULL,\n                    created_at TEXT NOT NULL,\n                    updated_at TEXT NOT NULL,\n                    PRIMARY KEY (access_token_hash, template_id)\n                );\n                CREATE INDEX IF NOT EXISTS profile_templates_owner_updated\n                    ON profile_templates(access_token_hash, updated_at DESC);\n                CREATE TABLE IF NOT EXISTS profile_custom_fields (\n                    field_id TEXT PRIMARY KEY,\n                    field_json TEXT NOT NULL,\n                    created_at TEXT NOT NULL,\n                    updated_at TEXT NOT NULL\n                );\n                CREATE TABLE IF NOT EXISTS profile_builder_preferences (\n                    access_token_hash TEXT PRIMARY KEY,\n                    preferences_json TEXT NOT NULL,\n                    updated_at TEXT NOT NULL\n                );\n                ')
            _sanitize_profile_builder_storage(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.config.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def purge_expired(self) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self._retention_days())).isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM candidate_profiles WHERE updated_at < ?", (cutoff,))

    def create_candidate_profile(
        self,
        access_token: str | None,
        snapshot: ProfileBuilderSnapshot,
    ) -> str:
        if not access_token:
            raise PersistenceError("profile builder access token required")
        profile_id = str(uuid4())
        now = _utc_now()
        safe_snapshot = sanitize_profile_builder_snapshot(snapshot)
        payload = safe_snapshot.model_dump(mode="json")
        try:
            self.purge_expired()
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO candidate_profiles (
                        profile_id, access_token_hash, source_filename, profile_json,
                        anonymization_json, template_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        profile_id,
                        _token_hash(access_token),
                        payload["source_filename"],
                        json.dumps(payload["profile"]),
                        json.dumps(payload["anonymization"]),
                        json.dumps(payload["template"]),
                        now,
                        now,
                    ),
                )
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("candidate profile persistence failed") from exc
        return profile_id

    def list_candidate_profiles(self, access_token: str | None) -> list[dict[str, Any]]:
        if not access_token:
            return []
        self.purge_expired()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT profile_id, source_filename, profile_json, template_json,
                       created_at, updated_at
                FROM candidate_profiles
                WHERE access_token_hash = ?
                ORDER BY updated_at DESC
                """,
                (_token_hash(access_token),),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            try:
                profile = sanitize_candidate_profile(
                    CandidateProfile.model_validate(json.loads(row["profile_json"]))
                ).model_dump(mode="json")
                template = ProfileTemplate.model_validate(
                    json.loads(row["template_json"])
                )
            except (json.JSONDecodeError, ValueError):
                continue
            result.append(
                {
                    "profile_id": row["profile_id"],
                    "source_filename": sanitize_profile_builder_filename(row["source_filename"]),
                    "candidate_name": _profile_candidate_name(profile),
                    "template_id": template.id,
                    "template_name": template.name,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return result

    def get_candidate_profile(
        self,
        profile_id: str,
        access_token: str | None,
    ) -> dict[str, Any] | None:
        if not access_token:
            return None
        self.purge_expired()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM candidate_profiles
                WHERE profile_id = ? AND access_token_hash = ?
                """,
                (profile_id, _token_hash(access_token)),
            ).fetchone()
        if row is None:
            return None
        try:
            snapshot = sanitize_profile_builder_snapshot(
                ProfileBuilderSnapshot.model_validate(
                    {
                        "source_filename": row["source_filename"],
                        "profile": json.loads(row["profile_json"]),
                        "anonymization": json.loads(row["anonymization_json"]),
                        "template": json.loads(row["template_json"]),
                    }
                )
            )
        except (json.JSONDecodeError, ValueError):
            return None
        return {
            "profile_id": row["profile_id"],
            **snapshot.model_dump(mode="json"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def update_candidate_profile(
        self,
        profile_id: str,
        access_token: str | None,
        snapshot: ProfileBuilderSnapshot,
    ) -> bool:
        if not access_token:
            return False
        self.purge_expired()
        safe_snapshot = sanitize_profile_builder_snapshot(snapshot)
        payload = safe_snapshot.model_dump(mode="json")
        try:
            with self._connect() as conn:
                updated = conn.execute(
                    """
                    UPDATE candidate_profiles
                    SET source_filename = ?, profile_json = ?, anonymization_json = ?,
                        template_json = ?, updated_at = ?
                    WHERE profile_id = ? AND access_token_hash = ?
                    """,
                    (
                        payload["source_filename"],
                        json.dumps(payload["profile"]),
                        json.dumps(payload["anonymization"]),
                        json.dumps(payload["template"]),
                        _utc_now(),
                        profile_id,
                        _token_hash(access_token),
                    ),
                ).rowcount
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("candidate profile update failed") from exc
        return updated == 1

    def delete_candidate_profile(
        self,
        profile_id: str,
        access_token: str | None,
    ) -> bool:
        if not access_token:
            return False
        try:
            with self._connect() as conn:
                deleted = conn.execute(
                    """
                    DELETE FROM candidate_profiles
                    WHERE profile_id = ? AND access_token_hash = ?
                    """,
                    (profile_id, _token_hash(access_token)),
                ).rowcount
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("candidate profile delete failed") from exc
        return deleted == 1

    def list_profile_templates(self, access_token: str | None) -> list[dict[str, Any]]:
        if not access_token:
            return []
        owner_hash = _token_hash(access_token)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT access_token_hash, template_id, template_json, created_at, updated_at
                FROM profile_templates
                WHERE access_token_hash IN (?, ?)
                ORDER BY CASE WHEN access_token_hash = ? THEN 0 ELSE 1 END, updated_at DESC
                """,
                (owner_hash, _SHARED_TEMPLATE_SCOPE, owner_hash),
            ).fetchall()
        shared_ids = {
            row["template_id"]
            for row in rows
            if row["access_token_hash"] == _SHARED_TEMPLATE_SCOPE
        }
        templates: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            if row["template_id"] in seen:
                continue
            try:
                template = ProfileTemplate.model_validate(
                    json.loads(row["template_json"])
                )
            except (json.JSONDecodeError, ValueError):
                continue
            template.visibility = (
                "shared"
                if row["access_token_hash"] == _SHARED_TEMPLATE_SCOPE
                else "private"
            )
            template = sanitize_profile_template(template)
            seen.add(template.id)
            templates.append(
                {
                    "template": template.model_dump(mode="json"),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "shared": row["access_token_hash"] == _SHARED_TEMPLATE_SCOPE,
                    "overrides_shared": (
                        row["access_token_hash"] == owner_hash
                        and template.id in shared_ids
                    ),
                }
            )
        return templates

    def get_profile_template(
        self,
        template_id: str,
        access_token: str | None,
    ) -> dict[str, Any] | None:
        if not access_token:
            return None
        owner_hash = _token_hash(access_token)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT access_token_hash, template_json, created_at, updated_at
                FROM profile_templates
                WHERE template_id = ? AND access_token_hash IN (?, ?)
                ORDER BY CASE WHEN access_token_hash = ? THEN 0 ELSE 1 END
                LIMIT 1
                """,
                (template_id, owner_hash, _SHARED_TEMPLATE_SCOPE, owner_hash),
            ).fetchone()
        if row is None:
            return None
        try:
            template = ProfileTemplate.model_validate(json.loads(row["template_json"]))
        except (json.JSONDecodeError, ValueError):
            return None
        template.visibility = (
            "shared"
            if row["access_token_hash"] == _SHARED_TEMPLATE_SCOPE
            else "private"
        )
        template = sanitize_profile_template(template)
        return {
            "template": template.model_dump(mode="json"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "shared": row["access_token_hash"] == _SHARED_TEMPLATE_SCOPE,
        }

    def upsert_profile_template(
        self,
        access_token: str | None,
        template: ProfileTemplate,
    ) -> None:
        if not access_token:
            raise PersistenceError("profile builder access token required")
        owner_hash = _token_hash(access_token)
        stored_template = sanitize_profile_template(template)
        if stored_template.id == "idego-default":
            stored_template.visibility = "shared"
        target_scope = (
            _SHARED_TEMPLATE_SCOPE
            if stored_template.visibility == "shared"
            else owner_hash
        )
        now = _utc_now()
        payload = stored_template.model_dump(mode="json")
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO profile_templates (
                        access_token_hash, template_id, name, template_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(access_token_hash, template_id) DO UPDATE SET
                        name = excluded.name,
                        template_json = excluded.template_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        target_scope,
                        stored_template.id,
                        stored_template.name,
                        json.dumps(payload),
                        now,
                        now,
                    ),
                )
                if target_scope == _SHARED_TEMPLATE_SCOPE:
                    conn.execute(
                        "DELETE FROM profile_templates WHERE access_token_hash = ? AND template_id = ?",
                        (owner_hash, stored_template.id),
                    )
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("profile template persistence failed") from exc

    def delete_profile_template(
        self,
        template_id: str,
        access_token: str | None,
    ) -> bool:
        if not access_token:
            return False
        owner_hash = _token_hash(access_token)
        try:
            with self._connect() as conn:
                deleted = conn.execute(
                    """
                    DELETE FROM profile_templates
                    WHERE template_id = ? AND access_token_hash = ?
                    """,
                    (template_id, owner_hash),
                ).rowcount
                if not deleted:
                    deleted = conn.execute(
                        "DELETE FROM profile_templates WHERE template_id = ? AND access_token_hash = ?",
                        (template_id, _SHARED_TEMPLATE_SCOPE),
                    ).rowcount
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("profile template delete failed") from exc
        return deleted == 1

    def list_profile_custom_fields(self) -> list[ProfileCustomFieldDefinition]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT field_json FROM profile_custom_fields ORDER BY created_at, field_id"
            ).fetchall()
        result: list[ProfileCustomFieldDefinition] = []
        for row in rows:
            try:
                result.append(
                    sanitize_profile_custom_field_definition(
                        ProfileCustomFieldDefinition.model_validate(
                            json.loads(row["field_json"])
                        )
                    )
                )
            except (json.JSONDecodeError, ValueError):
                continue
        return result

    def upsert_profile_custom_field(
        self, definition: ProfileCustomFieldDefinition
    ) -> None:
        now = _utc_now()
        safe_definition = sanitize_profile_custom_field_definition(definition)
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO profile_custom_fields (field_id, field_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(field_id) DO UPDATE SET
                        field_json = excluded.field_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        safe_definition.id,
                        json.dumps(safe_definition.model_dump(mode="json")),
                        now,
                        now,
                    ),
                )
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("profile custom field persistence failed") from exc

    def delete_profile_custom_field(self, field_id: str) -> bool:
        try:
            with self._connect() as conn:
                deleted = conn.execute(
                    "DELETE FROM profile_custom_fields WHERE field_id = ?",
                    (field_id,),
                ).rowcount
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("profile custom field delete failed") from exc
        return deleted == 1

    def get_profile_builder_preferences(
        self, access_token: str | None
    ) -> ProfileBuilderPreferences:
        if not access_token:
            return ProfileBuilderPreferences()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT preferences_json FROM profile_builder_preferences WHERE access_token_hash = ?",
                (_token_hash(access_token),),
            ).fetchone()
        if row is None:
            return ProfileBuilderPreferences()
        try:
            return sanitize_profile_builder_preferences(
                ProfileBuilderPreferences.model_validate(
                    json.loads(row["preferences_json"])
                )
            )
        except (json.JSONDecodeError, ValueError):
            return ProfileBuilderPreferences()

    def set_profile_builder_preferences(
        self,
        access_token: str | None,
        preferences: ProfileBuilderPreferences,
    ) -> None:
        if not access_token:
            raise PersistenceError("profile builder access token required")
        safe_preferences = sanitize_profile_builder_preferences(preferences)
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO profile_builder_preferences (access_token_hash, preferences_json, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(access_token_hash) DO UPDATE SET
                        preferences_json = excluded.preferences_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        _token_hash(access_token),
                        json.dumps(safe_preferences.model_dump(mode="json")),
                        _utc_now(),
                    ),
                )
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("profile builder preferences persistence failed") from exc

def _sanitize_profile_builder_storage(conn: sqlite3.Connection) -> None:
    """One-time normalization for rows written before current privacy guards."""
    marker_key = "profile_builder_storage_sanitized_v1"
    if conn.execute(
        "SELECT 1 FROM runtime_settings WHERE key = ?", (marker_key,)
    ).fetchone() is not None:
        return

    migration_complete = True
    for row in conn.execute(
        """
        SELECT profile_id, source_filename, profile_json, anonymization_json, template_json
        FROM candidate_profiles
        """
    ).fetchall():
        try:
            snapshot = sanitize_profile_builder_snapshot(
                ProfileBuilderSnapshot.model_validate(
                    {
                        "source_filename": row["source_filename"],
                        "profile": json.loads(row["profile_json"]),
                        "anonymization": json.loads(row["anonymization_json"]),
                        "template": json.loads(row["template_json"]),
                    }
                )
            )
        except (json.JSONDecodeError, ValueError):
            migration_complete = False
            continue
        payload = snapshot.model_dump(mode="json")
        conn.execute(
            """
            UPDATE candidate_profiles
            SET source_filename = ?, profile_json = ?, template_json = ?
            WHERE profile_id = ?
            """,
            (
                payload["source_filename"],
                json.dumps(payload["profile"]),
                json.dumps(payload["template"]),
                row["profile_id"],
            ),
        )

    for row in conn.execute(
        "SELECT access_token_hash, template_id, template_json FROM profile_templates"
    ).fetchall():
        try:
            template = sanitize_profile_template(
                ProfileTemplate.model_validate(json.loads(row["template_json"]))
            )
        except (json.JSONDecodeError, ValueError):
            migration_complete = False
            continue
        conn.execute(
            """
            UPDATE profile_templates
            SET name = ?, template_json = ?
            WHERE access_token_hash = ? AND template_id = ?
            """,
            (
                template.name,
                json.dumps(template.model_dump(mode="json")),
                row["access_token_hash"],
                row["template_id"],
            ),
        )

    for row in conn.execute(
        "SELECT field_id, field_json FROM profile_custom_fields"
    ).fetchall():
        try:
            definition = sanitize_profile_custom_field_definition(
                ProfileCustomFieldDefinition.model_validate(
                    json.loads(row["field_json"])
                )
            )
        except (json.JSONDecodeError, ValueError):
            migration_complete = False
            continue
        conn.execute(
            "UPDATE profile_custom_fields SET field_json = ? WHERE field_id = ?",
            (json.dumps(definition.model_dump(mode="json")), row["field_id"]),
        )

    for row in conn.execute(
        "SELECT access_token_hash, preferences_json FROM profile_builder_preferences"
    ).fetchall():
        try:
            preferences = sanitize_profile_builder_preferences(
                ProfileBuilderPreferences.model_validate(
                    json.loads(row["preferences_json"])
                )
            )
        except (json.JSONDecodeError, ValueError):
            migration_complete = False
            continue
        conn.execute(
            """
            UPDATE profile_builder_preferences
            SET preferences_json = ?
            WHERE access_token_hash = ?
            """,
            (
                json.dumps(preferences.model_dump(mode="json")),
                row["access_token_hash"],
            ),
        )

    if migration_complete:
        conn.execute(
            """
            INSERT INTO runtime_settings (key, value, updated_at)
            VALUES (?, '1', ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (marker_key, _utc_now()),
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _profile_candidate_name(profile: dict[str, Any]) -> str | None:
    personal = profile.get("personal")
    if not isinstance(personal, dict):
        return None
    parts = [
        value.strip()
        for value in (personal.get("first_name"), personal.get("last_name"))
        if isinstance(value, str) and value.strip()
    ]
    return " ".join(parts) or None
