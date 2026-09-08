import sqlite3

from fastapi.testclient import TestClient

from conftest import valid_report
from cv_validator.api.app import create_app
from cv_validator.api.persistence import REST_GROUP_ID, PersistenceConfig, PersistenceStore
from cv_validator.openai_config import OpenAISettings
from test_api_v2 import FakeStrategy


def _persist(store: PersistenceStore, analysis_id: str, owner: str, group_id: str | None = None) -> None:
    payload = valid_report()
    payload["analysis_id"] = analysis_id
    store.persist_report(
        payload["source"]["sha256"],
        payload,
        analysis_id=analysis_id,
        owner_user_id=owner,
        source_filename=f"{analysis_id}.pdf",
        group_id=group_id,
    )


def test_analyses_without_group_land_in_rest_and_groups_are_owner_scoped(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db"))
    group = store.create_analysis_group("owner-1", "Junior backend engineer")
    _persist(store, "grouped", "owner-1", group["group_id"])
    _persist(store, "loose", "owner-1")
    _persist(store, "foreign", "owner-2", group["group_id"])

    groups = store.list_analysis_groups("owner-1")
    assert [g["name"] for g in groups] == ["Junior backend engineer", "Rest"]
    assert [a["analysis_id"] for a in groups[0]["analyses"]] == ["grouped"]
    assert groups[1]["group_id"] == REST_GROUP_ID and groups[1]["is_rest"] is True
    assert [a["analysis_id"] for a in groups[1]["analyses"]] == ["loose"]

    # a foreign owner's group id is not honoured; the analysis falls back to Rest
    foreign = store.list_analysis_groups("owner-2")
    assert [g["name"] for g in foreign] == ["Rest"]
    assert [a["analysis_id"] for a in foreign[0]["analyses"]] == ["foreign"]
    assert store.list_analysis_groups(None) == []


def test_delete_group_removes_its_analyses_and_rest_deletes_only_ungrouped(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db"))
    group = store.create_analysis_group("owner-1", "Offer")
    _persist(store, "grouped", "owner-1", group["group_id"])
    _persist(store, "loose", "owner-1")

    assert store.delete_analysis_group(group["group_id"], "owner-2") is False
    assert store.delete_analysis_group(REST_GROUP_ID, "owner-1") is True
    assert store.get_analysis_payload("loose") is None
    assert store.get_analysis_payload("grouped") is not None

    assert store.delete_analysis_group(group["group_id"], "owner-1") is True
    assert store.get_analysis_payload("grouped") is None
    assert store.analysis_group_owned_by(group["group_id"], "owner-1") is False
    assert store.list_analysis_groups("owner-1")[0]["group_id"] == REST_GROUP_ID


def test_existing_reports_table_gains_group_column(tmp_path) -> None:
    db_path = tmp_path / "reports.db"
    PersistenceStore(PersistenceConfig(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute("ALTER TABLE reports DROP COLUMN group_id")
    store = PersistenceStore(PersistenceConfig(db_path))
    _persist(store, "legacy", "owner-1")
    assert store.list_analyses("owner-1")[0]["group_id"] is None


def test_group_endpoints_and_analyze_header_assign_batch_to_group(tmp_path) -> None:
    client = TestClient(
        create_app(
            db_path=tmp_path / "reports.db",
            openai_settings=OpenAISettings(enabled=False),
            analysis_strategy=FakeStrategy(),
        )
    )
    owner = {"X-Analysis-Owner-Id": "owner-token"}

    assert client.post("/analysis-groups", json={"name": "   "}, headers=owner).status_code == 400
    created = client.post("/analysis-groups", json={"name": "  Junior  backend "}, headers=owner)
    assert created.status_code == 201
    group_id = created.json()["group_id"]
    assert created.json()["name"] == "Junior backend"

    analyzed = client.post(
        "/analyze",
        files={"file": ("candidate.pdf", b"%PDF-1.7 text", "application/pdf")},
        headers={**owner, "X-Analysis-Group-Id": group_id},
    )
    assert analyzed.status_code == 200
    unknown = client.post(
        "/analyze",
        files={"file": ("candidate.pdf", b"%PDF-1.7 text", "application/pdf")},
        headers={**owner, "X-Analysis-Group-Id": "missing-group"},
    )
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "analysis_group_not_found"
    loose = client.post(
        "/analyze",
        files={"file": ("other.pdf", b"%PDF-1.7 other", "application/pdf")},
        headers={**owner, "X-Analysis-Group-Id": REST_GROUP_ID},
    )
    assert loose.status_code == 200

    groups = client.get("/analysis-groups", headers=owner).json()["groups"]
    assert [g["name"] for g in groups] == ["Junior backend", "Rest"]
    assert groups[0]["analyses"][0]["analysis_id"] == analyzed.json()["analysis_id"]
    assert groups[1]["analyses"][0]["analysis_id"] == loose.json()["analysis_id"]

    assert client.delete("/analysis-groups/nope", headers=owner).status_code == 404
    assert client.delete(
        f"/analysis-groups/{group_id}", headers={"X-Analysis-Owner-Id": "someone-else"}
    ).status_code == 404
    assert client.delete(f"/analysis-groups/{group_id}", headers=owner).json() == {"deleted": True}
    assert client.get(
        f"/analyses/{analyzed.json()['analysis_id']}", headers=owner
    ).status_code == 404
    assert [g["name"] for g in client.get("/analysis-groups", headers=owner).json()["groups"]] == ["Rest"]
