from __future__ import annotations

import io

import pdfplumber

from cv_validator.config import IngestionConfig, load_ingestion_config
from cv_validator.ingestion import IngestionError, ParsedCV, SourcePage
from cv_validator.ingestion.text import validate_text_sufficiency


def extract_pdf(
    content: bytes, config: IngestionConfig | None = None
) -> ParsedCV:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = tuple(
                SourcePage(
                    page_id=f"page-{page_number:04d}",
                    page_number=page_number,
                    text=page.extract_text() or "",
                )
                for page_number, page in enumerate(pdf.pages, start=1)
            )
    except Exception as exc:  # noqa: BLE001
        raise IngestionError(f"Failed to read PDF: {exc}") from exc

    parsed = ParsedCV(pages=pages, source_format="pdf")
    validate_text_sufficiency(parsed, config or load_ingestion_config())
    return parsed
