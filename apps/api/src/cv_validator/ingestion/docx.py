from __future__ import annotations

import io

from docx import Document

from cv_validator.ingestion import IngestionError, ParsedCV
from cv_validator.ingestion.regions import split_contact_and_body


def extract_docx(content: bytes) -> ParsedCV:
    try:
        document = Document(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        raise IngestionError(f"Failed to read DOCX: {exc}") from exc

    lines = [para.text.strip() for para in document.paragraphs if para.text.strip()]
    if not lines:
        raise IngestionError("DOCX contains no extractable text")

    contact, body = split_contact_and_body(lines)
    return ParsedCV(
        lines=tuple(lines),
        contact_region=tuple(contact),
        body_region=tuple(body),
        source_format="docx",
    )
