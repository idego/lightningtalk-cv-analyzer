from __future__ import annotations

import hashlib
import re
import unicodedata

from cv_validator.config import IngestionConfig
from cv_validator.ingestion import (
    EmptyTextError,
    InsufficientTextError,
    RawDocument,
    RedactedDocument,
    RedactedDocumentIdentity,
)

_CANONICAL_TEXT_VERSION = "v1"


def meaningful_token_count(parsed: RawDocument | RedactedDocument) -> int:
    text = unicodedata.normalize("NFKC", "\n".join(page.text for page in parsed.pages))
    count = 0
    for raw_token in re.split(r"\s+", text):
        token = _strip_surrounding_punctuation(raw_token)
        if len(token) >= 2 and any(character.isalpha() for character in token):
            count += 1
    return count


def validate_text_sufficiency(
    parsed: RawDocument | RedactedDocument,
    config: IngestionConfig,
) -> None:
    token_count = meaningful_token_count(parsed)
    if token_count == 0:
        if parsed.source_format == "pdf":
            raise EmptyTextError(
                "PDF has no extractable text layer "
                "(scanned/image-only PDFs are not supported; OCR is not supported)"
            )
        raise EmptyTextError(
            f"{parsed.source_format.upper()} contains no extractable text"
        )
    if token_count < config.minimum_meaningful_tokens:
        raise InsufficientTextError(
            "Document contains insufficient meaningful text "
            f"({token_count} found, {config.minimum_meaningful_tokens} required)"
        )


def to_page_markdown(parsed: RedactedDocument) -> str:
    if not isinstance(parsed, RedactedDocument):
        raise TypeError("Markdown formatting requires a redacted document")
    return "\n\n".join(
        f"<!-- page: {page.page_id} -->\n{page.text}" for page in parsed.pages
    )


def redacted_canonical_text(document: RedactedDocument) -> str:
    if not isinstance(document, RedactedDocument):
        raise TypeError("canonical persistence text requires a redacted document")

    parts = [
        f"cv-validator:redacted-canonical-text:{_CANONICAL_TEXT_VERSION}",
        str(len(document.pages)),
    ]
    for page in document.pages:
        parts.extend(
            (
                f"{len(page.page_id)}:{page.page_id}",
                str(page.page_number),
                f"{len(page.text)}:{page.text}",
            )
        )
    return "\n".join(parts)


def redacted_document_identity(
    document: RedactedDocument,
) -> RedactedDocumentIdentity:
    canonical_text = redacted_canonical_text(document)
    return RedactedDocumentIdentity(
        algorithm="sha256",
        format_version=_CANONICAL_TEXT_VERSION,
        digest=hashlib.sha256(canonical_text.encode("utf-8")).hexdigest(),
    )


def _strip_surrounding_punctuation(token: str) -> str:
    start = 0
    end = len(token)
    while start < end and unicodedata.category(token[start]).startswith("P"):
        start += 1
    while end > start and unicodedata.category(token[end - 1]).startswith("P"):
        end -= 1
    return token[start:end]
