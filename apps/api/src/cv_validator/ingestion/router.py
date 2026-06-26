from __future__ import annotations

from pathlib import Path

from cv_validator.ingestion import IngestionError, ParsedCV
from cv_validator.ingestion.docx import extract_docx
from cv_validator.ingestion.pdf import extract_pdf

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


def ingest_cv(content: bytes, filename: str | None = None) -> ParsedCV:
    ext = _resolve_extension(filename)
    if ext == ".pdf":
        return extract_pdf(content)
    if ext == ".docx":
        return extract_docx(content)
    raise IngestionError(f"Unsupported file format: {ext or 'unknown'}")


def _resolve_extension(filename: str | None) -> str:
    if not filename:
        raise IngestionError("Filename is required to determine CV format")
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise IngestionError(
            f"Unsupported file format: {ext or 'none'}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    return ext
