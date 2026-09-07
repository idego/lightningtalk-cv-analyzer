"""Exercise populated pre-owner-id v2 databases, not just empty schema upgrades."""
from __future__ import annotations

import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from conftest import valid_report
from cv_validator.api.app import create_app
from cv_validator.api.feedback import FeedbackInput, FeedbackStore, TriageInput
from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.openai_config import OpenAISettings

SECRET = "synthetic-migration-secret-with-sufficient-length"


def legacy_token(owner: str, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), f"cv-analysis-history:{owner}".encode(), "sha256").hexdigest()


def populated_legacy_database(tmp_path):
    path = tmp_path / "legacy-v2.db"
    store = PersistenceStore(PersistenceConfig(path))
    for owner in ("owner-a", "owner-b"):
        report = valid_report()
        report["analysis_id"] = f"analysis-{owner}"
        store.create_analysis_run(report["analysis_id"], f"correlation-{owner}", owner)
        store.persist_report(report["source"]["sha256"], report,
                             analysis_id=report["analysis_id"], owner_user_id=owner,
                             source_filename="synthetic.pdf")
        store.persist_source_document(report["analysis_id"], "synthetic.pdf", "application/pdf", b"%PDF-synthetic")
    store.create_analysis_run("failed-owner-a", "synthetic-failed-run", "owner-a")
    store.persist_analysis_share_token("analysis-owner-a", "owner-a", "synthetic-share")
    feedback = FeedbackStore(path)
    report = store.get_analysis_payload("analysis-owner-a")
    targets = feedback.materialize("analysis-owner-a", report)
    target_id = targets[0]["target_id"]
    feedback.put("analysis-owner-a", target_id, legacy_token("owner-a"), FeedbackInput(
        rating="helpful", context_label="Synthetic snapshot", context_text="Keep this entire context",
        context_report=report,
    ), actor_email="owner-a@example.test")
    actor = feedback.pseudonym("actor", legacy_token("owner-a"))
    feedback.triage(target_id, actor, "synthetic-maintainer", TriageInput(status="reviewing", note="Keep triage"))
    with store._connect() as conn:
        conn.execute("DROP INDEX reports_owner_created")
        conn.execute("DROP INDEX analysis_runs_owner")
        for table in ("reports", "analysis_runs"):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN access_token_hash TEXT")
            for owner in ("owner-a", "owner-b"):
                conn.execute(f"UPDATE {table} SET access_token_hash = ? WHERE owner_user_id = ?",
                             (hashlib.sha256(legacy_token(owner).encode()).hexdigest(), owner))
            conn.execute(f"ALTER TABLE {table} DROP COLUMN owner_user_id")
    return path, target_id


def migrated_app(path, monkeypatch, secret=SECRET):
    monkeypatch.setenv("CV_VALIDATOR_LEGACY_OWNER_SECRET", secret)
    return create_app(db_path=path, openai_settings=OpenAISettings(enabled=False))


def test_authenticated_owner_recovers_reports_documents_shares_failed_runs_and_feedback(tmp_path, monkeypatch):
    path, target_id = populated_legacy_database(tmp_path)
    app = migrated_app(path, monkeypatch)
    client = TestClient(app, headers={"X-Analysis-Owner-Id": "owner-a"})
    result = client.get("/analyses")
    assert result.status_code == 200
    assert [row["analysis_id"] for row in result.json()["analyses"]] == ["analysis-owner-a"]
    assert client.get("/analyses/analysis-owner-a").status_code == 200
    assert client.get("/analyses/analysis-owner-a/document").content == b"%PDF-synthetic"
    assert client.get("/analyses/analysis-owner-b").status_code == 404
    assert app.state.store.analysis_owned_by("failed-owner-a", "owner-a")
    assert app.state.store.analysis_share_access_allowed("analysis-owner-a", "synthetic-share")
    assert "analysis_access_token" not in client.get("/analyses/analysis-owner-a").json()
    actor = FeedbackStore(path).pseudonym("actor", "owner-a")
    with app.state.store._connect() as conn:
        response = conn.execute("SELECT * FROM feedback_responses WHERE target_id = ? AND actor_hash = ?",
                                (target_id, actor)).fetchone()
        assert response["context_text"] == "Keep this entire context"
        assert json.loads(response["context_report_json"])["analysis_id"] == "analysis-owner-a"
        assert response["actor_email"] == "owner-a@example.test"
        triage = conn.execute("SELECT * FROM feedback_triage WHERE target_id = ? AND actor_hash = ?",
                              (target_id, actor)).fetchone()
        assert (triage["status"], triage["note"]) == ("reviewing", "Keep triage")
        assert conn.execute("SELECT COUNT(*) FROM legacy_analysis_owners").fetchone()[0] == 1
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert client.delete("/analyses/analysis-owner-a").status_code == 200
    with app.state.store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM feedback_responses").fetchone()[0] == 1


def test_browser_capability_cannot_claim_another_users_history(tmp_path, monkeypatch):
    path, _ = populated_legacy_database(tmp_path)
    app = migrated_app(path, monkeypatch)
    client = TestClient(app)
    assert client.get("/analyses", headers={"X-Analysis-Access-Token": legacy_token("owner-a")}).json() == {"analyses": []}
    response = client.get("/analyses/analysis-owner-a", headers={
        "X-Analysis-Owner-Id": "owner-b", "X-Analysis-Access-Token": legacy_token("owner-a"),
    })
    assert response.status_code == 404
    assert not app.state.store.analysis_owned_by("analysis-owner-a", "owner-b")


def test_wrong_secret_does_not_destroy_pending_bindings_and_migrated_owners_survive_rotation(tmp_path, monkeypatch):
    path, _ = populated_legacy_database(tmp_path)
    wrong = migrated_app(path, monkeypatch, secret="wrong-synthetic-secret")
    assert TestClient(wrong, headers={"X-Analysis-Owner-Id": "owner-a"}).get("/analyses").json() == {"analyses": []}
    with wrong.state.store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM legacy_analysis_owners").fetchone()[0] == 3
    correct = migrated_app(path, monkeypatch)
    assert len(TestClient(correct, headers={"X-Analysis-Owner-Id": "owner-a"}).get("/analyses").json()["analyses"]) == 1
    rotated = migrated_app(path, monkeypatch, secret="rotated-synthetic-secret")
    assert len(TestClient(rotated, headers={"X-Analysis-Owner-Id": "owner-a"}).get("/analyses").json()["analyses"]) == 1


def test_concurrent_migration_is_idempotent(tmp_path):
    path, _ = populated_legacy_database(tmp_path)
    store = PersistenceStore(PersistenceConfig(path))
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _: store.bind_legacy_owner("owner-a", legacy_token("owner-a")), range(8)))
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM feedback_responses").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM feedback_triage").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM feedback_events").fetchone()[0] == 1
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_retention_removes_unclaimed_migration_rows_but_preserves_feedback(tmp_path):
    path, _ = populated_legacy_database(tmp_path)
    store = PersistenceStore(PersistenceConfig(path))
    with store._connect() as conn:
        conn.execute("UPDATE reports SET created_at = '2000-01-01T00:00:00+00:00'")
        conn.execute("UPDATE analysis_runs SET created_at = '2000-01-01T00:00:00+00:00'")
    store.purge_expired()
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM legacy_analysis_owners").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM feedback_responses").fetchone()[0] == 1
    # Feedback outlives reports, but the original author still retains ownership.
    store.bind_legacy_owner("owner-a", legacy_token("owner-a"))
    with store._connect() as conn:
        assert conn.execute("SELECT actor_hash FROM feedback_responses").fetchone()[0] == FeedbackStore(path).pseudonym("actor", "owner-a")
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
