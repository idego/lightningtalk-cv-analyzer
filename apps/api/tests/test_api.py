import hashlib
import io
import json
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile as StarletteUploadFile

from cv_validator.api.app import create_app
from cv_validator.errors import (
    LocationAnalysisError,
    PersistenceError,
)
from cv_validator.domain import Report
from cv_validator.location import LocationResolver, ResolutionLevel
from cv_validator.pipeline import analyze_cv_bytes_result

FIXTURES = Path(__file__).parent.parent / "fixtures" / "calibration"


@pytest.fixture
def client(tmp_path, location_resolver):
    app = create_app(
        db_path=tmp_path / "test.db",
        retention_days=30,
        location_resolver=location_resolver,
    )
    return TestClient(app)


def _docx_bytes(text: str) -> bytes:
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_single_analyze_success(client):
    content = _docx_bytes((FIXTURES / "consistent_berlin.txt").read_text())
    response = client.post(
        "/analyze",
        files={"file": ("cv.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "score",
        "band",
        "claimed_location",
        "findings",
        "summary",
        "disclaimer",
        "ruleset_version",
        "signal_count",
        "supporting_count",
        "conflicting_count",
        "deterministic",
        "analysis_id",
        "ai_analysis",
        "checklist",
        "structural_audits",
        "ai_features_enabled",
        "ai_capabilities",
    }
    assert set(body["deterministic"]) == {
        "ruleset_version",
        "candidates",
        "facts",
        "observations",
        "scoring_signals",
    }
    assert "decision-support" in body["disclaimer"].lower()
    assert body["analysis_id"]
    assert body["ai_analysis"]["status"] == "disabled"
    assert len(body["checklist"]["checks"]) == 8
    assert body["score"] == 50
    assert body["band"] == "gray"
    assert body["ruleset_version"] == {
        "version": "1.0.0",
        "weights_path": body["ruleset_version"]["weights_path"],
            "scoring_policy_version": "deterministic-phone-postal-comparison-v2",
    }


def test_single_analyze_scores_independent_phone_and_postal_country(client):
    content = _docx_bytes(
        "Jane Example\n"
        "jane@example.com +48 732080047 Opole, Poland 45-061\n"
        "Software engineer"
    )

    response = client.post(
        "/analyze",
        files={
            "file": (
                "cv.docx",
                content,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 100
    assert body["band"] == "green"
    assert body["signal_count"] == 2
    assert {fact["kind"] for fact in body["deterministic"]["facts"]} >= {
        "claimed_location",
        "phone_country",
        "postal_country",
    }
    assert {
        signal["kind"]
        for signal in body["deterministic"]["scoring_signals"]
    } == {"phone_country", "postal_country"}
    assert any(
        observation["kind"] == "combined_location_inside_eu"
        for observation in body["deterministic"]["observations"]
    )
    phone_finding = next(
        finding for finding in body["findings"]
        if finding["signal"] == "phone_country"
    )
    assert phone_finding["authority"] == "code"
    assert phone_finding["evidence"]
    assert phone_finding["extractor_version"] == {
        "name": "phone-classification",
        "version": "1",
    }
    assert phone_finding["reference_data_version"] == {
        "name": "libphonenumber",
        "version": "9.0.37",
    }
    assert phone_finding["rule_id"] == "phone-country-all-person-owned-agree:v1"
    assert phone_finding["score_impact"] == "weighted"
    assert phone_finding["supporting_fact_ids"]


def test_single_analyze_does_not_report_email_digits_as_phone(client):
    content = _docx_bytes(
        "Jane Example\n"
        "Email: candidate.1234567@example.com\n"
        "Experienced software engineer profile"
    )

    response = client.post(
        "/analyze",
        files={"file": ("cv.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 200
    deterministic = response.json()["deterministic"]
    assert not [
        candidate for candidate in deterministic["candidates"]
        if candidate["kind"] == "phone"
    ]
    assert not [fact for fact in deterministic["facts"] if fact["kind"] == "phone_country"]
    assert not [
        observation for observation in deterministic["observations"]
        if observation["kind"] in {"phone", "phone_country_aggregate"}
    ]


def test_rejected_upload(client):
    response = client.post(
        "/analyze",
        files={"file": ("cv.txt", b"not a cv", "text/plain")},
    )
    assert response.status_code == 422


def test_mixed_batch(client):
    good = _docx_bytes((FIXTURES / "consistent_berlin.txt").read_text())
    response = client.post(
        "/analyze/batch",
        files=[
            ("files", ("good.docx", good, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("bad.txt", b"nope", "text/plain")),
        ],
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 2
    successful = next(result for result in results if result["status"] == "ok")
    failed = next(result for result in results if result["status"] == "error")
    assert "deterministic" in successful["report"]
    assert failed["filename"] == "bad.txt"
    assert "report" not in failed


def test_batch_rejects_more_than_the_v1_file_limit_before_analysis(
    tmp_path,
    location_resolver,
    monkeypatch,
) -> None:
    calls = 0

    def should_not_analyze(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("batch analysis started before file-count preflight")

    monkeypatch.setattr(
        "cv_validator.api.app.analyze_cv_bytes_result",
        should_not_analyze,
    )
    app = create_app(
        db_path=tmp_path / "batch-limit.db",
        location_resolver=location_resolver,
        batch_max_files=4,
    )
    files = [
        (
            "files",
            (
                f"candidate-{number}.docx",
                _docx_bytes("Candidate\nSoftware engineer profile"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        )
        for number in range(5)
    ]

    with TestClient(app) as local_client:
        response = local_client.post("/analyze/batch", files=files)

    assert response.status_code == 413
    assert response.json() == {"detail": "batch_file_limit_exceeded"}
    assert calls == 0


def test_batch_rejects_total_readable_bytes_before_analysis(
    tmp_path,
    location_resolver,
    monkeypatch,
) -> None:
    calls = 0

    def should_not_analyze(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("batch analysis started before request-size preflight")

    monkeypatch.setattr(
        "cv_validator.api.app.analyze_cv_bytes_result",
        should_not_analyze,
    )
    app = create_app(
        db_path=tmp_path / "batch-bytes.db",
        location_resolver=location_resolver,
        batch_max_bytes=100,
    )

    with TestClient(app) as local_client:
        response = local_client.post(
            "/analyze/batch",
            files=[
                ("files", ("one.docx", b"a" * 60, "application/octet-stream")),
                ("files", ("two.docx", b"b" * 60, "application/octet-stream")),
            ],
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "batch_request_size_limit_exceeded"}
    assert calls == 0


def test_batch_isolates_upload_read_failure_and_continues_without_leaking_pii(
    client,
    monkeypatch,
    caplog,
) -> None:
    raw_id = "123-45-6789"
    original_read = StarletteUploadFile.read
    calls = 0

    async def fail_first_read(self, size: int = -1):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError(f"read failed at /private/{raw_id}.docx")
        return await original_read(self, size)

    monkeypatch.setattr(StarletteUploadFile, "read", fail_first_read)
    good = _docx_bytes((FIXTURES / "consistent_berlin.txt").read_text())

    response = client.post(
        "/analyze/batch",
        files=[
            (
                "files",
                (
                    "first.docx",
                    _docx_bytes("First Candidate\nExperience\nEngineer profile"),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            ),
            (
                "files",
                (
                    "second.docx",
                    good,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            ),
        ],
    )

    assert response.status_code == 200
    assert response.json()["results"][0] == {
        "filename": "first.docx",
        "status": "error",
        "error": "analysis_runtime_error",
    }
    assert response.json()["results"][1]["status"] == "ok"
    assert "/private/" not in response.text
    assert raw_id not in response.text
    assert raw_id not in caplog.text


def test_audit_entry_written(client):
    content = _docx_bytes((FIXTURES / "consistent_berlin.txt").read_text())
    response = client.post(
        "/analyze",
        files={"file": ("cv.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200
    store = client.app.state.store
    entries = store.get_audit_entries()
    assert len(entries) == 1
    assert entries[0]["ruleset_version"] == (
        "weights:1.0.0;policy:deterministic-phone-postal-comparison-v2"
    )
    output = json.loads(entries[0]["output_json"])
    assert output == response.json()
    assert output["score"] == 50
    assert output["band"] == "gray"
    assert (
        output["ruleset_version"]["scoring_policy_version"]
            == "deterministic-phone-postal-comparison-v2"
    )


def test_analysis_history_is_private_reopenable_and_deletable(client):
    content = _docx_bytes((FIXTURES / "consistent_berlin.txt").read_text())
    owner_headers = {"X-Analysis-Access-Token": "owner-token"}
    response = client.post(
        "/analyze",
        headers=owner_headers,
        files={"file": ("candidate.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    analysis_id = response.json()["analysis_id"]

    history = client.get("/analyses", headers=owner_headers)
    assert history.status_code == 200
    assert history.json()["analyses"][0]["analysis_id"] == analysis_id
    assert history.json()["analyses"][0]["filename"] == "candidate.docx"
    assert client.get(
        "/analyses", headers={"X-Analysis-Access-Token": "another-owner"}
    ).json() == {"analyses": []}

    reopened = client.get(f"/analyses/{analysis_id}", headers=owner_headers)
    assert reopened.status_code == 200
    assert reopened.json() == response.json()
    assert client.delete(
        f"/analyses/{analysis_id}",
        headers={"X-Analysis-Access-Token": "another-owner"},
    ).status_code == 404
    assert client.delete(f"/analyses/{analysis_id}", headers=owner_headers).json() == {"deleted": True}
    assert client.get(f"/analyses/{analysis_id}", headers=owner_headers).status_code == 404


def test_retention_setting_is_validated_and_persists(client):
    assert client.get("/settings/retention").json() == {"days": 30}
    assert client.put("/settings/retention", json={"days": 120}).json() == {"days": 120}
    assert client.put("/settings/retention", json={"days": 0}).status_code == 422

    reopened = create_app(db_path=client.app.state.store.config.db_path, retention_days=30)
    with TestClient(reopened) as reopened_client:
        assert reopened_client.get("/settings/retention").json() == {"days": 120}


def test_national_id_audit_payload_exactly_matches_api_response(client) -> None:
    raw_id = "123-45-6789"
    response = client.post(
        "/analyze",
        files={
            "file": (
                "cv.docx",
                _docx_bytes(
                    f"Jane Example\nSSN: {raw_id}\n\nExperience\nEngineer profile"
                ),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    persisted = json.loads(
        client.app.state.store.get_audit_entries()[0]["output_json"]
    )
    national_id = next(
        finding
        for finding in response.json()["findings"]
        if finding["signal"] == "national_id"
    )
    assert national_id["observed"] == "present:LABELED_NATIONAL_ID+US_SSN"
    assert persisted == response.json()


@pytest.mark.parametrize(
    ("text", "expected_score", "expected_signal_count"),
    (
        (
            "Alex Example\nCurrent location: Berlin, Germany\n"
            "Phone: +49 30 123456\n\nExperience\nEngineer",
            50,
            1,
        ),
        (
            "Alex Example\nCurrent location: Berlin, Germany\n"
            "Phone: +1 415 555 0100\n\nExperience\nEngineer",
            50,
            1,
        ),
        (
            "Alex Example\nCurrent location: Berlin, Germany\n\n"
            "Experience\nSoftware Engineer",
            50,
            0,
        ),
        (
            "Alex Example\nSoftware engineer profile\n\n"
            "Experience\nDelivery systems specialist",
            0,
            0,
        ),
    ),
)
def test_gray_score_semantics_match_api_and_persisted_audit(
    client,
    text,
    expected_score,
    expected_signal_count,
) -> None:
    response = client.post(
        "/analyze",
        files={
            "file": (
                "cv.docx",
                _docx_bytes(text),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["score"] == expected_score
    assert body["band"] == "gray"
    assert body["signal_count"] == expected_signal_count
    persisted = json.loads(client.app.state.store.get_audit_entries()[0]["output_json"])
    assert persisted["score"] == body["score"]
    assert persisted["band"] == body["band"]
    assert persisted["signal_count"] == body["signal_count"]
    assert persisted["supporting_count"] == body["supporting_count"]
    assert persisted["conflicting_count"] == body["conflicting_count"]


def test_national_id_not_retained_raw(client, caplog):
    raw_id = "ABC123456789XYZ987654321"
    text = (
        f"Jane\nBerlin, Germany\nNational ID: {raw_id}"
        "\n\nExperience\nEngineer\n"
    )
    content = _docx_bytes(text)
    response = client.post(
        "/analyze",
        files={"file": ("cv.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    store = client.app.state.store
    output = store.get_audit_entries()[0]["output_json"]
    assert response.status_code == 200
    assert raw_id.encode() not in response.content
    assert raw_id not in output
    assert "REDACTED" in output or "present" in output
    assert raw_id.encode() not in store.config.db_path.read_bytes()
    assert raw_id not in caplog.text


def test_batch_national_ids_are_absent_from_api_persistence_and_logs(client, caplog):
    raw_ids = (
        "12345678901234567890",
        "PL-ABC 12-34/56.XYZ",
    )
    files = [
        (
            "files",
            (
                f"cv-{index}.docx",
                _docx_bytes(
                    "Jane\nBerlin, Germany\n"
                    f"National ID: {raw_id}\n\nExperience\nEngineer\n"
                ),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        )
        for index, raw_id in enumerate(raw_ids, start=1)
    ]

    response = client.post("/analyze/batch", files=files)

    assert response.status_code == 200
    assert all(result["status"] == "ok" for result in response.json()["results"])
    persisted = client.app.state.store.config.db_path.read_bytes()
    for raw_id in raw_ids:
        assert raw_id.encode() not in response.content
        assert raw_id.encode() not in persisted
        assert raw_id not in caplog.text


def test_persistence_identity_uses_redacted_canonical_text_hash(client):
    raw_id = "123" + "-45-" + "6789"
    content = _docx_bytes(
        f"Jane\nBerlin, Germany\nSSN: {raw_id}\n\nExperience\nEngineer\n"
    )
    expected = analyze_cv_bytes_result(content, "cv.docx").document_identity.digest

    response = client.post(
        "/analyze",
        files={
            "file": (
                "cv.docx",
                content,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    entry = client.app.state.store.get_audit_entries()[0]
    assert entry["input_hash"] == expected
    assert entry["input_hash"] != hashlib.sha256(content).hexdigest()


class _FailOnceResolver:
    def __init__(self, delegate: LocationResolver, message: str) -> None:
        self.delegate = delegate
        self.message = message
        self.failed = False

    def resolve(self, value: str, *, level: ResolutionLevel):
        if not self.failed:
            self.failed = True
            raise LocationAnalysisError(self.message)
        return self.delegate.resolve(value, level=level)


def test_batch_isolates_typed_resolver_failure_without_leaking_pii(
    tmp_path,
    location_resolver,
    caplog,
) -> None:
    raw_id = "123-45-6789"
    resolver = _FailOnceResolver(location_resolver, f"failed near {raw_id}")
    app = create_app(db_path=tmp_path / "batch.db", location_resolver=resolver)
    files = [
        (
            "files",
            (
                "first.docx",
                _docx_bytes(
                    f"Jane\nCurrent location: Berlin, Germany\nSSN: {raw_id}\nEngineer"
                ),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        ),
        (
            "files",
            (
                "second.docx",
                _docx_bytes(
                    "Alex\nCurrent location: Berlin, Germany\nSoftware engineer"
                ),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        ),
    ]

    with TestClient(app) as local_client:
        response = local_client.post("/analyze/batch", files=files)

    results = response.json()["results"]
    assert results[0] == {
        "filename": "first.docx",
        "status": "error",
        "error": "analysis_runtime_error",
    }
    assert results[1]["status"] == "ok"
    assert raw_id not in response.text
    assert raw_id not in caplog.text


def test_batch_isolates_typed_persistence_failure(tmp_path, location_resolver) -> None:
    app = create_app(
        db_path=tmp_path / "batch-persistence.db",
        location_resolver=location_resolver,
    )
    original = app.state.store.persist_report
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PersistenceError("sqlite path /private/internal.db")
        return original(*args, **kwargs)

    app.state.store.persist_report = fail_once
    files = [
        (
            "files",
            (
                f"candidate-{number}.docx",
                _docx_bytes(
                    "Candidate\nCurrent location: Berlin, Germany\nSoftware engineer"
                ),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        )
        for number in (1, 2)
    ]

    with TestClient(app) as local_client:
        response = local_client.post("/analyze/batch", files=files)

    results = response.json()["results"]
    assert results[0]["error"] == "analysis_runtime_error"
    assert results[1]["status"] == "ok"
    assert "/private/internal.db" not in response.text
    assert len(app.state.store.get_audit_entries()) == 1


def test_batch_preflights_deterministic_json_before_persistence(
    monkeypatch,
    tmp_path,
    location_resolver,
) -> None:
    app = create_app(
        db_path=tmp_path / "batch-json.db",
        location_resolver=location_resolver,
    )
    original = Report.to_dict
    calls = 0

    def non_json_first(self):
        nonlocal calls
        calls += 1
        payload = original(self)
        if calls == 1:
            payload["deterministic"]["facts"].append({"unsafe": object()})
        return payload

    monkeypatch.setattr(Report, "to_dict", non_json_first)
    files = [
        (
            "files",
            (
                f"candidate-{number}.docx",
                _docx_bytes(
                    "Candidate\nCurrent location: Berlin, Germany\nSoftware engineer"
                ),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        )
        for number in (1, 2)
    ]

    with TestClient(app) as local_client:
        response = local_client.post("/analyze/batch", files=files)

    results = response.json()["results"]
    assert results[0]["error"] == "analysis_runtime_error"
    assert results[1]["status"] == "ok"
    assert len(app.state.store.get_audit_entries()) == 1
