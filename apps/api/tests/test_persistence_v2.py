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
        access_token="secret-token",
        source_filename="candidate.pdf",
    )

    stored = store.get_analysis_payload("analysis-1")
    assert stored["contract_version"] == "base-analysis-v2"
    assert "score" not in stored
    assert "band" not in stored
    assert "analysis_access_token" not in stored
    assert "secret-token" not in store.get_audit_entries()[0]["output_json"]
    assert store.list_analyses("secret-token")[0]["strategy"] == "document-analysis"


def test_analysis_share_capabilities_are_hashed_scoped_and_deleted_with_report(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db"))
    payload = valid_report()
    payload["analysis_id"] = "analysis-share"
    store.persist_report(
        payload["source"]["sha256"],
        payload,
        analysis_id="analysis-share",
        access_token="owner-token",
        source_filename="candidate.pdf",
    )

    assert store.persist_analysis_share_token("analysis-share", "wrong-owner", "share-secret") is False
    assert store.persist_analysis_share_token("analysis-share", "owner-token", "share-secret") is True
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

    assert store.delete_analysis("analysis-share", "owner-token") is True
    assert store.analysis_share_access_allowed("analysis-share", "share-secret") is False


def test_retention_purge_removes_analysis_share_capabilities(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db", retention_days=1))
    payload = valid_report()
    payload["analysis_id"] = "analysis-expired-share"
    store.persist_report(
        payload["source"]["sha256"],
        payload,
        analysis_id="analysis-expired-share",
        access_token="owner-token",
        source_filename="candidate.pdf",
    )
    assert store.persist_analysis_share_token(
        "analysis-expired-share", "owner-token", "share-secret"
    ) is True
    with store._connect() as connection:
        connection.execute(
            "UPDATE reports SET created_at = '2000-01-01T00:00:00+00:00' WHERE analysis_id = ?",
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
    assert tables == {"reports"}
