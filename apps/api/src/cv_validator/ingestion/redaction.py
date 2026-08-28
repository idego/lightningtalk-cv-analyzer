from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from cv_validator.ingestion import (
    NationalIdRedaction,
    RawDocument,
    RedactedDocument,
    SourcePage,
)

MASK_CHARACTER = "█"
NATIONAL_ID_REDACTION_VERSION = "1"

_US_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PESEL = re.compile(r"\b\d{11}\b")
_UK_NINO = re.compile(
    r"\b[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z](?:\s?\d){6}\s?[A-D]?\b",
    re.IGNORECASE,
)
_LABELED_ID = re.compile(
    r"\b(?:PESEL|SSN|NINO|national\s+ID|national\s+insurance(?:\s+number)?)\b"
    r"[ \t]*(?:[:#-][ \t]*)?"
    r"(?P<value>\S(?:[^\r\n]*\S)?)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
_DISALLOWED_NINO_PREFIXES = {"BG", "GB", "KN", "NK", "NT", "TN", "ZZ"}


@dataclass(frozen=True, repr=False)
class _SensitiveSpan:
    start_offset: int
    end_offset: int
    type_hints: tuple[str, ...]


def redact_national_ids(document: RawDocument) -> RedactedDocument:
    redacted_pages: list[SourcePage] = []
    redactions: list[NationalIdRedaction] = []

    for page in document.pages:
        spans = _merge_spans(_find_sensitive_spans(page.text))
        masked_characters = list(page.text)
        for span in spans:
            masked_characters[span.start_offset : span.end_offset] = (
                MASK_CHARACTER * (span.end_offset - span.start_offset)
            )
            redactions.append(
                NationalIdRedaction(
                    page_id=page.page_id,
                    page_number=page.page_number,
                    start_offset=span.start_offset,
                    end_offset=span.end_offset,
                    type_hints=span.type_hints,
                )
            )
        redacted_pages.append(
            SourcePage(
                page_id=page.page_id,
                page_number=page.page_number,
                text="".join(masked_characters),
            )
        )

    return RedactedDocument(
        pages=tuple(redacted_pages),
        source_format=document.source_format,
        redactions=tuple(redactions),
        file_details=document.file_details,
        document_links=document.document_links,
        presentation_spans=tuple(
            _redact_presentation_span(span, redactions)
            for span in document.presentation_spans
        ),
        presentation_audited_parts=document.presentation_audited_parts,
        presentation_omitted_parts=document.presentation_omitted_parts,
        presentation_truncated=document.presentation_truncated,
        source_blocks=document.source_blocks,
        source_blocks_partial=document.source_blocks_partial,
    )


def _redact_presentation_span(span, redactions):
    from dataclasses import replace

    hints: set[str] = set(span.redaction_type_hints)
    text = span.text
    if span.start_offset is not None and span.end_offset is not None:
        chars = list(text)
        for redaction in redactions:
            if redaction.page_id != span.page_id:
                continue
            left = max(span.start_offset, redaction.start_offset)
            right = min(span.end_offset, redaction.end_offset)
            if left >= right:
                continue
            chars[left - span.start_offset:right - span.start_offset] = MASK_CHARACTER * (right - left)
            hints.update(redaction.type_hints)
        text = "".join(chars)
    return replace(span, text=text, redaction_type_hints=tuple(sorted(hints)))


def _find_sensitive_spans(text: str) -> list[_SensitiveSpan]:
    spans: list[_SensitiveSpan] = []
    spans.extend(
        _SensitiveSpan(match.start(), match.end(), ("US_SSN",))
        for match in _US_SSN.finditer(text)
    )

    for match in _PESEL.finditer(text):
        if _is_valid_pesel(match.group(0)):
            spans.append(
                _SensitiveSpan(match.start(), match.end(), ("PL_PESEL",))
            )

    for match in _UK_NINO.finditer(text):
        normalized = re.sub(r"\s+", "", match.group(0)).upper()
        if normalized[:2] not in _DISALLOWED_NINO_PREFIXES:
            spans.append(
                _SensitiveSpan(match.start(), match.end(), ("UK_NINO",))
            )

    spans.extend(
        _SensitiveSpan(
            match.start("value"),
            match.end("value"),
            ("LABELED_NATIONAL_ID",),
        )
        for match in _LABELED_ID.finditer(text)
    )
    return spans


def _merge_spans(spans: list[_SensitiveSpan]) -> tuple[_SensitiveSpan, ...]:
    ordered = sorted(spans, key=lambda span: (span.start_offset, span.end_offset))
    merged: list[_SensitiveSpan] = []
    for span in ordered:
        if not merged or span.start_offset >= merged[-1].end_offset:
            merged.append(span)
            continue

        previous = merged[-1]
        merged[-1] = _SensitiveSpan(
            start_offset=previous.start_offset,
            end_offset=max(previous.end_offset, span.end_offset),
            type_hints=tuple(sorted(set(previous.type_hints + span.type_hints))),
        )
    return tuple(merged)


def _is_valid_pesel(value: str) -> bool:
    weights = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
    weighted_sum = sum(
        int(digit) * weight for digit, weight in zip(value[:10], weights)
    )
    checksum = (10 - weighted_sum % 10) % 10
    if checksum != int(value[-1]):
        return False

    year = int(value[:2])
    encoded_month = int(value[2:4])
    day = int(value[4:6])
    if 1 <= encoded_month <= 12:
        century, month = 1900, encoded_month
    elif 21 <= encoded_month <= 32:
        century, month = 2000, encoded_month - 20
    elif 41 <= encoded_month <= 52:
        century, month = 2100, encoded_month - 40
    elif 61 <= encoded_month <= 72:
        century, month = 2200, encoded_month - 60
    elif 81 <= encoded_month <= 92:
        century, month = 1800, encoded_month - 80
    else:
        return False

    try:
        date(century + year, month, day)
    except ValueError:
        return False
    return True
