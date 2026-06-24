import io

import pytest
from docx import Document
from reportlab.pdfgen import canvas

from cv_validator.ingestion import IngestionError
from cv_validator.ingestion.docx import extract_docx
from cv_validator.ingestion.pdf import extract_pdf
from cv_validator.ingestion.router import ingest_cv


def _make_text_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    y = 800
    for line in text.splitlines():
        c.drawString(72, y, line)
        y -= 14
    c.save()
    return buffer.getvalue()


def _make_scanned_pdf() -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.save()
    return buffer.getvalue()


def _make_docx(text: str) -> bytes:
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


SAMPLE = """Jane Doe
Berlin, Germany
+49 30 12345678

Experience
Engineer — Acme, Berlin
"""


def test_pdf_text_extraction():
    content = _make_text_pdf(SAMPLE)
    parsed = extract_pdf(content)
    assert "Berlin, Germany" in parsed.text
    assert parsed.contact_region
    assert parsed.body_region


def test_docx_extraction():
    parsed = extract_docx(_make_docx(SAMPLE))
    assert "Berlin, Germany" in parsed.text


def test_reject_scanned_pdf():
    with pytest.raises(IngestionError, match="no extractable text"):
        extract_pdf(_make_scanned_pdf())


def test_reject_unsupported_format():
    with pytest.raises(IngestionError, match="Unsupported"):
        ingest_cv(b"hello", filename="cv.txt")


def test_reject_empty_docx():
    with pytest.raises(IngestionError, match="no extractable text"):
        extract_docx(_make_docx(""))


def test_contact_region_distinct_from_body():
    parsed = extract_docx(_make_docx(SAMPLE))
    assert any("Berlin" in line for line in parsed.contact_region)
    assert any("Experience" in line or "Engineer" in line for line in parsed.body_region)
