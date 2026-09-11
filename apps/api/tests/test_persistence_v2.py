from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

from conftest import valid_report
from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.errors import PersistenceError


def test_persistence_uses_strategy_contract_without_score_or_access_token(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db"))
    payload = valid_report()
    payload["analysis_id"] = "analysis-1"
    payload["analysis_access_token"] = "secret-token"

    store.persist_report(
        payload["source"]["sha256"],
        payload,
        analysis_id="analysis-1",
        owner_user_id="owner-1",
        source_filename="candidate.pdf",
    )

    stored = store.get_analysis_payload("analysis-1")
    assert stored["contract_version"] == "base-analysis-v2"
    assert "score" not in stored
    assert "band" not in stored
    assert "analysis_access_token" not in stored
    assert "secret-token" not in store.get_audit_entries()[0]["output_json"]
    assert store.list_analyses("owner-1")[0]["strategy"] == "document-analysis"


def test_analysis_share_requires_a_persisted_report_not_only_an_analysis_run(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db"))
    store.create_analysis_run("failed-analysis", "correlation-id", "owner-1")

    assert store.analysis_owned_by("failed-analysis", "owner-1") is True
    assert store.persist_analysis_share_token(
        "failed-analysis", "owner-1", "share-secret"
    ) is None


def test_analysis_share_capabilities_are_hashed_scoped_and_deleted_with_report(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db"))
    payload = valid_report()
    payload["analysis_id"] = "analysis-share"
    store.persist_report(
        payload["source"]["sha256"],
        payload,
        analysis_id="analysis-share",
        owner_user_id="owner-1",
        source_filename="candidate.pdf",
    )

    assert store.persist_analysis_share_token("analysis-share", "wrong-owner", "share-secret") is None
    assert store.persist_analysis_share_token("analysis-share", "owner-1", "share-secret") is not None
    assert store.analysis_share_access_allowed("analysis-share", "wrong-share") is False
    assert store.analysis_share_access_allowed("analysis-share", "share-secret") is True
    with store._connect() as connection:
        stored_token = connection.execute(
            "SELECT token_hash FROM analysis_share_tokens WHERE analysis_id = ?",
            ("analysis-share",),
        ).fetchone()["token_hash"]
    assert stored_token != "share-secret"

    view = store.get_analysis_view("analysis-share")
    assert view is not None
    assert view["filename"] == "candidate.pdf"
    assert view["report"]["analysis_id"] == "analysis-share"
    assert "analysis_access_token" not in view["report"]

    assert store.delete_analysis("analysis-share", "owner-1") is True
    assert store.analysis_share_access_allowed("analysis-share", "share-secret") is False


def test_retention_purge_removes_analysis_share_capabilities(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db", retention_days=1))
    payload = valid_report()
    payload["analysis_id"] = "analysis-expired-share"
    store.persist_report(
        payload["source"]["sha256"],
        payload,
        analysis_id="analysis-expired-share",
        owner_user_id="owner-1",
        source_filename="candidate.pdf",
    )
    assert store.persist_analysis_share_token(
        "analysis-expired-share", "owner-1", "share-secret"
    ) is not None
    with store._connect() as connection:
        connection.execute(
            "UPDATE reports SET expires_at = '2000-01-01T00:00:00+00:00' WHERE analysis_id = ?",
            ("analysis-expired-share",),
        )

    deleted = store.purge_expired()

    assert "analysis-expired-share" in deleted["analysis_ids"]
    assert store.analysis_share_access_allowed("analysis-expired-share", "share-secret") is False


def test_legacy_report_database_is_rejected_instead_of_mutated(tmp_path) -> None:
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE reports (id INTEGER PRIMARY KEY, score INTEGER, band TEXT)"
        )

    with pytest.raises(PersistenceError, match="legacy_database_reset_required"):
        PersistenceStore(PersistenceConfig(path))

    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(reports)")
        }
    assert tables == {"reports"}
    assert columns == {"id", "score", "band"}


def test_delete_all_removes_reportless_runs_only_for_the_owner(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db"))
    store.create_analysis_run("failed-owner-a", "corr-a", "owner-a")
    store.create_analysis_run("failed-owner-b", "corr-b", "owner-b")

    assert store.delete_all_analyses("owner-a") == 1
    assert store.analysis_owned_by("failed-owner-a", "owner-a") is False
    assert store.analysis_owned_by("failed-owner-b", "owner-b") is True


def test_retention_uses_report_age_not_older_run_age(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db", retention_days=30))
    payload = valid_report()
    payload["analysis_id"] = "analysis-boundary"
    store.create_analysis_run("analysis-boundary", "corr", "owner-a")
    store.persist_report(
        payload["source"]["sha256"], payload,
        analysis_id="analysis-boundary", owner_user_id="owner-a",
    )
    with store._connect() as connection:
        connection.execute(
            "UPDATE analysis_runs SET expires_at='2000-01-01T00:00:00+00:00' WHERE analysis_id=?",
            ("analysis-boundary",),
        )

    store.purge_expired()

    assert store.get_analysis_payload("analysis-boundary") is not None


def test_owner_schema_migration_removes_legacy_token_columns_and_allows_new_runs(tmp_path) -> None:
    path = tmp_path / "legacy-owner.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE reports (
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
            CREATE TABLE analysis_runs (
                analysis_id TEXT PRIMARY KEY,
                correlation_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                access_token_hash TEXT NOT NULL,
                error_code TEXT
            );
            """
        )

    store = PersistenceStore(PersistenceConfig(path))
    store.create_analysis_run("new-analysis", "corr", "owner-1")

    with store._connect() as connection:
        report_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(reports)")
        }
        run_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(analysis_runs)")
        }
    assert "owner_user_id" in report_columns
    assert "owner_user_id" in run_columns
    assert "access_token_hash" not in report_columns
    assert "access_token_hash" not in run_columns
    assert store.analysis_owned_by("new-analysis", "owner-1") is True


def test_connections_enable_secure_delete(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db"))
    with store._connect() as connection:
        assert connection.execute("PRAGMA secure_delete").fetchone()[0] == 1


def test_vacuum_reclaims_space_after_purge(tmp_path) -> None:
    db_path = tmp_path / "reports.db"
    store = PersistenceStore(PersistenceConfig(db_path, retention_days=1))
    for index in range(20):
        payload = valid_report()
        analysis_id = f"analysis-vacuum-{index}"
        payload["analysis_id"] = analysis_id
        store.persist_report(
            payload["source"]["sha256"],
            payload,
            analysis_id=analysis_id,
            owner_user_id="owner-1",
            source_filename="candidate.pdf",
        )
    with store._connect() as connection:
        connection.execute("UPDATE reports SET expires_at = '2000-01-01T00:00:00+00:00'")
    store.purge_expired()
    before = db_path.stat().st_size

    store.vacuum()

    assert db_path.stat().st_size < before


def _persist(store: PersistenceStore, analysis_id: str) -> None:
    payload = valid_report()
    payload["analysis_id"] = analysis_id
    store.persist_report(
        payload["source"]["sha256"],
        payload,
        analysis_id=analysis_id,
        owner_user_id="owner-1",
        source_filename="candidate.pdf",
    )


def _report_expires_at(store: PersistenceStore, analysis_id: str) -> datetime:
    with store._connect() as connection:
        row = connection.execute(
            "SELECT expires_at FROM reports WHERE analysis_id = ?", (analysis_id,)
        ).fetchone()
    return datetime.fromisoformat(row["expires_at"])


def test_reports_store_their_retention_deadline_on_write(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db", retention_days=30))
    before = datetime.now(timezone.utc)

    _persist(store, "analysis-deadline")

    expires_at = _report_expires_at(store, "analysis-deadline")
    assert timedelta(days=30) - timedelta(minutes=1) < expires_at - before <= timedelta(days=30, minutes=1)
    assert store.list_analyses("owner-1")[0]["expires_at"] == expires_at.isoformat()


def test_changing_retention_keeps_stored_deadlines(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db", retention_days=90))
    _persist(store, "analysis-old-window")
    original = _report_expires_at(store, "analysis-old-window")

    store.set_retention_days(1)
    _persist(store, "analysis-new-window")

    assert _report_expires_at(store, "analysis-old-window") == original
    assert store.get_analysis_payload("analysis-old-window") is not None
    new_deadline = _report_expires_at(store, "analysis-new-window")
    assert new_deadline - datetime.now(timezone.utc) < timedelta(days=1, minutes=1)


def test_purge_ignores_rows_whose_deadline_has_not_passed(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db", retention_days=1))
    _persist(store, "analysis-future")
    with store._connect() as connection:
        connection.execute(
            "UPDATE reports SET created_at = '2000-01-01T00:00:00+00:00' WHERE analysis_id = ?",
            ("analysis-future",),
        )

    deleted = store.purge_expired()

    assert deleted["analysis_ids"] == ()
    assert store.get_analysis_payload("analysis-future") is not None


def test_existing_rows_without_deadline_are_backfilled_from_created_at(tmp_path) -> None:
    db_path = tmp_path / "reports.db"
    store = PersistenceStore(PersistenceConfig(db_path, retention_days=10))
    store.create_analysis_run("analysis-legacy", "corr", "owner-1")
    _persist(store, "analysis-legacy")
    with sqlite3.connect(db_path) as connection:
        for table in ("reports", "analysis_runs"):
            connection.execute(f"DROP INDEX IF EXISTS {table}_expires_at")
            connection.execute(f"ALTER TABLE {table} DROP COLUMN expires_at")
            connection.execute(
                f"UPDATE {table} SET created_at = '2026-01-01T00:00:00+00:00'"
            )

    reopened = PersistenceStore(PersistenceConfig(db_path, retention_days=10))

    assert _report_expires_at(reopened, "analysis-legacy") == datetime(2026, 1, 11, tzinfo=timezone.utc)
    with reopened._connect() as connection:
        run = connection.execute(
            "SELECT expires_at FROM analysis_runs WHERE analysis_id = 'analysis-legacy'"
        ).fetchone()
    assert run["expires_at"] == "2026-01-11T00:00:00+00:00"
