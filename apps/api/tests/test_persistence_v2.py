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
    assert store.list_analyses("secret-token")[0]["strategy"] == "luna-only"


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
