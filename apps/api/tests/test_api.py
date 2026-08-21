import io
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from cv_validator.api.app import create_app

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
    assert "band" in body
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


def test_national_id_not_retained_raw(client):
    text = "Jane\nBerlin, Germany\n123-45-6789\n\nExperience\nEngineer\n"
    content = _docx_bytes(text)
    client.post(
        "/analyze",
        files={"file": ("cv.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    store = client.app.state.store
    output = store.get_audit_entries()[0]["output_json"]
    assert "123-45-6789" not in output
    assert "REDACTED" in output or "present" in output
