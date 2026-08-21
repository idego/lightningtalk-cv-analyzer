import hashlib
import io
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from cv_validator.api.app import create_app
from cv_validator.pipeline import analyze_cv_bytes_result

FIXTURES = Path(__file__).parent.parent / "fixtures" / "calibration"


@pytest.fixture
def client(tmp_path):
    app = create_app(db_path=tmp_path / "test.db", retention_days=30)
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
    }
    assert "decision-support" in body["disclaimer"].lower()


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
    assert any(r["status"] == "ok" for r in results)
    assert any(r["status"] == "error" for r in results)


def test_audit_entry_written(client):
    content = _docx_bytes((FIXTURES / "consistent_berlin.txt").read_text())
    client.post(
        "/analyze",
        files={"file": ("cv.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    store = client.app.state.store
    entries = store.get_audit_entries()
    assert len(entries) == 1
    assert entries[0]["ruleset_version"] == "1.0.0"


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
