from __future__ import annotations

import io
from typing import Iterable

import pdfplumber

from cv_validator.ingestion import IngestionError, ParsedCV
from cv_validator.ingestion.regions import split_contact_and_body


def extract_pdf(content: bytes) -> ParsedCV:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            page_texts: list[str] = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                page_texts.append(text)
    except Exception as exc:  # noqa: BLE001
        raise IngestionError(f"Failed to read PDF: {exc}") from exc

    combined = "\n".join(page_texts).strip()
    if not combined:
        raise IngestionError(
            "PDF has no extractable text layer (scanned/image-only PDFs are not supported)"
        )

    lines = _normalize_lines(combined.splitlines())
    contact, body = split_contact_and_body(lines)
    return ParsedCV(
        lines=tuple(lines),
        contact_region=tuple(contact),
        body_region=tuple(body),
        source_format="pdf",
    )


def _normalize_lines(lines: Iterable[str]) -> list[str]:
    return [line.strip() for line in lines if line.strip()]
