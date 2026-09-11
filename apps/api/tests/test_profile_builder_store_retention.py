from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.api.profile_builder_store import ProfileBuilderStore
from cv_validator.errors import PersistenceError
from cv_validator.profile_builder import (
    CandidateProfile,
    ProfileBuilderSnapshot,
    default_profile_template,
)

TOKEN = "profile-owner-token"


def _snapshot(filename: str = "candidate.pdf") -> ProfileBuilderSnapshot:
    return ProfileBuilderSnapshot(
        source_filename=filename,
        profile=CandidateProfile(),
        template=default_profile_template(),
    )


def _stores(tmp_path, retention_days: int) -> tuple[PersistenceStore, ProfileBuilderStore]:
    analysis_store = PersistenceStore(
        PersistenceConfig(tmp_path / "reports.db", retention_days=retention_days)
    )
    return analysis_store, ProfileBuilderStore(analysis_store)


def _expires_at(store: ProfileBuilderStore, profile_id: str) -> datetime:
    with store._connect() as conn:
        row = conn.execute(
            "SELECT expires_at FROM candidate_profiles WHERE profile_id = ?", (profile_id,)
        ).fetchone()
    return datetime.fromisoformat(row["expires_at"])


def test_new_profile_stores_deadline_from_current_retention(tmp_path) -> None:
    _, store = _stores(tmp_path, retention_days=30)
    before = datetime.now(timezone.utc)

    profile_id = store.create_candidate_profile(TOKEN, _snapshot())

    remaining = _expires_at(store, profile_id) - before
    assert timedelta(days=30) - timedelta(minutes=1) < remaining <= timedelta(days=30, minutes=1)


def test_updating_a_profile_renews_its_deadline_with_the_current_window(tmp_path) -> None:
    analysis_store, store = _stores(tmp_path, retention_days=30)
    profile_id = store.create_candidate_profile(TOKEN, _snapshot())
    original = _expires_at(store, profile_id)
    analysis_store.set_retention_days(2)

    assert store.update_candidate_profile(profile_id, TOKEN, _snapshot("edited.pdf")) is True

    renewed = _expires_at(store, profile_id)
    assert renewed < original
    assert renewed - datetime.now(timezone.utc) < timedelta(days=2, minutes=1)


def test_purge_uses_the_stored_deadline_not_updated_at(tmp_path) -> None:
    _, store = _stores(tmp_path, retention_days=1)
    expired = store.create_candidate_profile(TOKEN, _snapshot("old.pdf"))
    kept = store.create_candidate_profile(TOKEN, _snapshot("recent.pdf"))
    with store._connect() as conn:
        conn.execute(
            "UPDATE candidate_profiles SET expires_at = '2000-01-01T00:00:00+00:00' WHERE profile_id = ?",
            (expired,),
        )
        # An ancient updated_at alone no longer expires a row.
        conn.execute(
            "UPDATE candidate_profiles SET updated_at = '2000-01-01T00:00:00+00:00' WHERE profile_id = ?",
            (kept,),
        )

    store.purge_expired()

    remaining = {row["profile_id"] for row in store.list_candidate_profiles(TOKEN)}
    assert remaining == {kept}


def test_profile_purge_wraps_sqlite_errors(tmp_path) -> None:
    _, store = _stores(tmp_path, retention_days=30)
    with sqlite3.connect(tmp_path / "reports.db") as conn:
        conn.execute("DROP TABLE candidate_profiles")

    with pytest.raises(PersistenceError, match="candidate profile purge failed"):
        store.purge_expired()
