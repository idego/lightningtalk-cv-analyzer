from fastapi.testclient import TestClient

from conftest import valid_report
from cv_validator.api.app import ANALYSIS_NOTE_MAX_CHARS, create_app
from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.openai_config import OpenAISettings
from test_api_v2 import FakeStrategy


def _persist(store: PersistenceStore, analysis_id: str, owner: str) -> None:
    payload = valid_report()
    payload["analysis_id"] = analysis_id
    store.persist_report(
        payload["source"]["sha256"], payload, analysis_id=analysis_id, owner_user_id=owner
    )


def test_notes_are_owner_scoped_and_deleted_with_the_analysis(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db"))
    _persist(store, "a1", "owner-1")

    assert store.get_analysis_note("a1", "owner-1") is None
    saved = store.set_analysis_note("a1", "owner-1", "Strong Django background")
    assert saved["content"] == "Strong Django background"
    assert store.get_analysis_note("a1", "owner-1")["content"] == "Strong Django background"
    assert store.get_analysis_note("a1", "owner-2") is None
    assert store.list_analyses("owner-1")[0]["has_note"] is True

    store.set_analysis_note("a1", "owner-1", "Updated")
    assert store.get_analysis_note("a1", "owner-1")["content"] == "Updated"
    assert store.delete_analysis_note("a1", "owner-2") is False
    assert store.delete_analysis_note("a1", "owner-1") is True
    assert store.list_analyses("owner-1")[0]["has_note"] is False

    store.set_analysis_note("a1", "owner-1", "Again")
    store.delete_analysis("a1", "owner-1")
    assert store.get_analysis_note("a1", "owner-1") is None


def test_note_endpoints_validate_length_and_ownership(tmp_path) -> None:
    client = TestClient(
        create_app(
            db_path=tmp_path / "reports.db",
            openai_settings=OpenAISettings(enabled=False),
            analysis_strategy=FakeStrategy(),
        )
    )
    owner = {"X-Analysis-Owner-Id": "owner-token"}
    analysis_id = client.post(
        "/analyze",
        files={"file": ("candidate.pdf", b"%PDF-1.7 text", "application/pdf")},
        headers=owner,
    ).json()["analysis_id"]

    empty = client.get(f"/analyses/{analysis_id}/note", headers=owner)
    assert empty.status_code == 200
    assert empty.json() == {"note": None, "max_chars": ANALYSIS_NOTE_MAX_CHARS}

    assert client.put(f"/analyses/{analysis_id}/note", json={"content": "   "}, headers=owner).status_code == 400
    too_long = client.put(
        f"/analyses/{analysis_id}/note", json={"content": "x" * (ANALYSIS_NOTE_MAX_CHARS + 1)}, headers=owner
    )
    assert too_long.status_code == 413
    assert too_long.json()["detail"] == "note_too_long"

    saved = client.put(f"/analyses/{analysis_id}/note", json={"content": "  Call back Monday\r\n"}, headers=owner)
    assert saved.status_code == 200
    assert saved.json()["note"]["content"] == "Call back Monday"
    assert client.get("/analyses", headers=owner).json()["analyses"][0]["has_note"] is True

    foreign = {"X-Analysis-Owner-Id": "someone-else"}
    assert client.get(f"/analyses/{analysis_id}/note", headers=foreign).status_code == 404
    assert client.put(f"/analyses/{analysis_id}/note", json={"content": "x"}, headers=foreign).status_code == 404
    assert client.delete(f"/analyses/{analysis_id}/note", headers=foreign).status_code == 404

    assert client.delete(f"/analyses/{analysis_id}/note", headers=owner).json() == {"deleted": True}
    assert client.get(f"/analyses/{analysis_id}/note", headers=owner).json()["note"] is None


def test_retention_purge_removes_notes_together_with_their_analysis(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db", retention_days=1))
    _persist(store, "expired", "owner-1")
    _persist(store, "fresh", "owner-1")
    store.set_analysis_note("expired", "owner-1", "old remark")
    store.set_analysis_note("fresh", "owner-1", "new remark")
    with store._connect() as connection:
        connection.execute(
            "UPDATE reports SET created_at = '2000-01-01T00:00:00+00:00' WHERE analysis_id = ?",
            ("expired",),
        )

    deleted = store.purge_expired()

    assert deleted["analysis_ids"] == ("expired",)
    assert deleted["analysis_notes"] == 1
    assert store.get_analysis_note("expired", "owner-1") is None
    assert store.get_analysis_note("fresh", "owner-1")["content"] == "new remark"
