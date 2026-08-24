from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Iterator, Mapping

from jsonschema import Draft202012Validator

from cv_validator.ai.domain import ValidatedDocumentAnalysis
from cv_validator.ai.request import (
    DETERMINISTIC_OBSERVATIONS_VERSION,
    SCHEMA_VERSION,
    load_document_analysis_schema,
)
from cv_validator.ingestion import RedactedDocument


REQUIRED_CHECK_IDS = frozenset(
    {
        "contact",
        "education",
        "employment",
        "timeline",
        "duration_claims",
        "relationships",
        "document_quality",
        "protected_boundaries",
    }
)
_FORBIDDEN_AUTHORED_PATTERNS = (
    re.compile(
        r"\b(?:score|band|verdict|ranking|hiring recommendation|nationality|"
        r"ethnicity|race|racial|national origin|appearance|religion|health|"
        r"age|gender|sex|family status|work eligibility)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:the\s+)?(?:candidate|applicant|person)\s+"
        r"(?:is|appears|seems|may be|is likely)\s+[^.!?\n]{1,100}?\s+"
        r"based on\s+(?:their\s+|the\s+)?"
        r"(?:name|surname|photo|appearance|language|school|university)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:(?:do not|don't|should not|must not)\s+"
        r"(?:interview|hire|advance|progress|select|consider)|"
        r"(?:reject|advance|hire)\s+(?:(?:this|the)\s+)?"
        r"(?:candidate|applicant)|"
        r"recommend(?:ation)?\s+(?:to\s+)?(?:hire|reject|advance))\b",
        re.IGNORECASE,
    ),
)


class DocumentAnalysisValidationError(ValueError):
    """Safe validation failure that never embeds candidate content."""


def validate_document_analysis_response(
    payload: Any,
    document: RedactedDocument,
) -> ValidatedDocumentAnalysis:
    if not isinstance(document, RedactedDocument):
        raise TypeError("Document Analyzer validation requires a RedactedDocument")

    return validate_document_analysis_payload(
        payload,
        pages={page.page_id: page.text for page in document.pages},
        deterministic_observations_version=DETERMINISTIC_OBSERVATIONS_VERSION,
    )


def validate_document_analysis_payload(
    payload: Any,
    *,
    pages: Mapping[str, str],
    deterministic_observations_version: str,
) -> ValidatedDocumentAnalysis:
    """Canonical pure validation shared by runtime and offline eval."""
    if (
        deterministic_observations_version != DETERMINISTIC_OBSERVATIONS_VERSION
        or not pages
        or any(
            not isinstance(page_id, str)
            or not page_id
            or not isinstance(text, str)
            for page_id, text in pages.items()
        )
    ):
        raise DocumentAnalysisValidationError(
            "AI document analysis response failed validation: context"
        )

    validator = Draft202012Validator(load_document_analysis_schema())
    if any(validator.iter_errors(payload)):
        raise DocumentAnalysisValidationError(
            "AI document analysis response failed validation: schema"
        )

    failure_kinds: list[str] = []
    if any(
        evidence.get("page_id") not in pages
        or evidence.get("excerpt") not in pages.get(evidence.get("page_id"), "")
        for evidence in _iter_evidence(payload)
    ):
        failure_kinds.append("exact excerpt")

    checklist = payload.get("checklist")
    if isinstance(checklist, list):
        checklist_ids = [
            item.get("id") for item in checklist if isinstance(item, dict)
        ]
        if (
            len(checklist_ids) != len(REQUIRED_CHECK_IDS)
            or set(checklist_ids) != REQUIRED_CHECK_IDS
        ):
            failure_kinds.append("checklist completeness")

    if any(
        pattern.search(text)
        for text in _iter_model_authored_conclusions(payload)
        for pattern in _FORBIDDEN_AUTHORED_PATTERNS
    ):
        failure_kinds.append("protected boundary")

    if failure_kinds:
        kinds = ", ".join(dict.fromkeys(failure_kinds))
        raise DocumentAnalysisValidationError(
            f"AI document analysis response failed validation: {kinds}"
        )

    return ValidatedDocumentAnalysis(
        schema_version=SCHEMA_VERSION,
        payload=deepcopy(payload),
    )


def _iter_evidence(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if "page_id" in value or "excerpt" in value:
            yield value
        for child in value.values():
            yield from _iter_evidence(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_evidence(child)


def _iter_model_authored_conclusions(payload: dict[str, Any]) -> Iterator[str]:
    for finding in payload["findings"]:
        yield finding["observation"]
        yield finding["reason"]
        yield finding["limitation"]
    for unknown in payload["unknowns"]:
        yield unknown["reason"]
    for candidate in payload["research_candidates"]:
        yield candidate["question"]
    yield from payload["analysis_limitations"]
