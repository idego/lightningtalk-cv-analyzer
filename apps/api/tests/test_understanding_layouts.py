from io import BytesIO

from docx import Document

from cv_validator.document_understanding.service import understand_document, understanding_to_payload
from cv_validator.ingestion import PresentationSpan, RawDocument, SourcePage
from cv_validator.ingestion.docx import extract_docx
from cv_validator.ingestion.redaction import redact_national_ids


def test_docx_table_rows_are_independent_entry_boundaries():
    document = Document(); document.add_paragraph("Experience")
    table = document.add_table(rows=2, cols=3)
    values = (("First Company Ltd", "Software Engineer", "01/2020 - 02/2022"), ("Second Company Ltd", "Product Manager", "03/2022 - Present"))
    for row, row_values in zip(table.rows, values):
        for cell, value in zip(row.cells, row_values): cell.text = value
    buffer = BytesIO(); document.save(buffer)
    parsed = extract_docx(buffer.getvalue())
    payload = understanding_to_payload(understand_document(redact_national_ids(parsed), "test", snapshot_month="2026-08"))
    assert [next(field["value"] for field in record["fields"] if field["name"] == "organization") for record in payload["records"]] == ["First Company Ltd", "Second Company Ltd"]


def test_interleaved_pdf_column_ownership_abstains_instead_of_guessing():
    text = "Experience\nFirst Company Ltd\nSecond Company Ltd\nSoftware Engineer\n01/2020 - 02/2022"
    spans = tuple(PresentationSpan("page-0001", 1, line.text, line.start_offset, line.end_offset, association="exact", bbox=(0, index * 10, 100, index * 10 + 8)) for index, line in enumerate(SourcePage("page-0001", 1, text).lines))
    raw = RawDocument(pages=(SourcePage("page-0001", 1, text),), source_format="pdf", presentation_spans=spans)
    payload = understanding_to_payload(understand_document(redact_national_ids(raw), "test", snapshot_month="2026-08"))
    assert payload["records"] == []
    assert any(item["reason_code"] == "unsupported_employment_identity" for item in payload["ambiguous_spans"])
