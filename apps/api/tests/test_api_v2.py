from fastapi.testclient import TestClient

from conftest import valid_report
from cv_validator.api.app import create_app
from cv_validator.openai_config import OpenAISettings


class FakeStrategy:
    name = "docling-luna"
    version = "docling-luna-test-v1"
    ready = True

    def analyze(self, request):
        return valid_report(
            request.sha256,
            source_format=request.source_format.value,
            strategy_name=self.name,
        )


def test_health_reports_docling_strategy_and_invalid_pdf_fails_clearly(tmp_path) -> None:
    client = TestClient(
        create_app(
            db_path=tmp_path / "reports.db",
            openai_settings=OpenAISettings(enabled=False),
        )
    )

    health = client.get("/health")
    response = client.post(
        "/analyze",
        files={"file": ("candidate.pdf", b"%PDF-1.7", "application/pdf")},
    )

    assert health.json()["capabilities"]["base_analysis"] == {
        "ready": True,
        "strategy": "docling-luna",
    }
    assert response.status_code == 422
    assert response.json()["detail"] == "document_conversion_failed"


def test_analysis_round_trip_uses_new_contract(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "reports.db",
        openai_settings=OpenAISettings(enabled=False),
        analysis_strategy=FakeStrategy(),
    )
    client = TestClient(app)
    response = client.post(
        "/analyze",
        files={"file": ("candidate.pdf", b"%PDF-1.7 text", "application/pdf")},
        headers={"X-Analysis-Access-Token": "owner-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "base-analysis-v2"
    assert payload["strategy"]["name"] == "docling-luna"
    assert "score" not in payload
    assert "document_understanding" not in payload
    loaded = client.get(
        f"/analyses/{payload['analysis_id']}",
        headers={"X-Analysis-Access-Token": "owner-token"},
    )
    assert loaded.status_code == 200
    assert loaded.json()["base_analysis"]["education"][0]["added_by_reviewer"] is True


def test_batch_limits_are_enforced_before_analysis(tmp_path) -> None:
    client = TestClient(
        create_app(
            db_path=tmp_path / "reports.db",
            openai_settings=OpenAISettings(enabled=False),
            analysis_strategy=FakeStrategy(),
            batch_max_files=1,
            batch_max_bytes=8,
        )
    )

    too_many = client.post(
        "/analyze/batch",
        files=[
            ("files", ("one.pdf", b"%PDF", "application/pdf")),
            ("files", ("two.pdf", b"%PDF", "application/pdf")),
        ],
    )
    too_large = client.post(
        "/analyze/batch",
        files={"files": ("one.pdf", b"%PDF-1.7 text", "application/pdf")},
    )

    assert too_many.status_code == 413
    assert too_many.json()["detail"] == "batch_file_limit_exceeded"
    assert too_large.status_code == 413
    assert too_large.json()["detail"] == "batch_request_size_limit_exceeded"


def test_analysis_lifecycle_is_owner_scoped(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "reports.db",
        openai_settings=OpenAISettings(enabled=False),
        analysis_strategy=FakeStrategy(),
    )
    client = TestClient(app)
    owner_headers = {"X-Analysis-Access-Token": "owner-token"}
    created = client.post(
        "/analyze",
        files={"file": ("candidate.pdf", b"%PDF-1.7 text", "application/pdf")},
        headers=owner_headers,
    ).json()
    analysis_id = created["analysis_id"]

    purge_expired = app.state.store.purge_expired
    purge_calls = 0

    def tracked_purge_expired():
        nonlocal purge_calls
        purge_calls += 1
        return purge_expired()

    app.state.store.purge_expired = tracked_purge_expired
    history = client.get("/analyses", headers=owner_headers)

    assert history.json()["analyses"][0]["analysis_id"] == analysis_id
    assert purge_calls == 1
    assert client.get(
        f"/analyses/{analysis_id}",
        headers={"X-Analysis-Access-Token": "another-owner"},
    ).status_code == 404
    assert client.delete(f"/analyses/{analysis_id}", headers=owner_headers).status_code == 200
    assert client.get(f"/analyses/{analysis_id}", headers=owner_headers).status_code == 404
