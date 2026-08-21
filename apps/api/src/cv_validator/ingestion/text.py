from __future__ import annotations

import re
import unicodedata

from cv_validator.config import IngestionConfig
from cv_validator.ingestion import EmptyTextError, InsufficientTextError, ParsedCV


def meaningful_token_count(parsed: ParsedCV) -> int:
    text = unicodedata.normalize("NFKC", "\n".join(page.text for page in parsed.pages))
    count = 0
    for raw_token in re.split(r"\s+", text):
        token = _strip_surrounding_punctuation(raw_token)
        if len(token) >= 2 and any(character.isalpha() for character in token):
            count += 1
    return count


def validate_text_sufficiency(parsed: ParsedCV, config: IngestionConfig) -> None:
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


def to_page_markdown(parsed: ParsedCV) -> str:
    return "\n\n".join(
        f"<!-- page: {page.page_id} -->\n{page.text}" for page in parsed.pages
    )


def _strip_surrounding_punctuation(token: str) -> str:
    start = 0
    end = len(token)
    while start < end and unicodedata.category(token[start]).startswith("P"):
        start += 1
    while end > start and unicodedata.category(token[end - 1]).startswith("P"):
        end -= 1
    return token[start:end]
