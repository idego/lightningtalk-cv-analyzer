from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re
import unicodedata
from typing import Any, Iterator, Mapping

from jsonschema import Draft202012Validator

from cv_validator.ai.domain import ValidatedDocumentAnalysis
from cv_validator.ai.request import (
    DETERMINISTIC_OBSERVATIONS_VERSION,
    SCHEMA_VERSION,
    load_document_analysis_schema,
)
from cv_validator.ingestion import RedactedDocument, SourcePage


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
_CATEGORY_CHECK_IDS = {
    "contact_conflict": "contact",
    "missing_contact_data": "contact",
    "timeline_gap": "timeline",
    "timeline_overlap": "timeline",
    "duration_claim_conflict": "duration_claims",
    "relationship_ambiguity": "relationships",
    "document_artifact": "document_quality",
}
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
    source_lines = _source_line_index(pages)
    if any(
        evidence.get("excerpt") is not None
        for evidence in _iter_evidence(payload)
    ):
        failure_kinds.append("model evidence")
    if any(
        evidence.get("line_id") not in source_lines
        or source_lines.get(evidence.get("line_id"), (None, None))[0]
        != evidence.get("page_id")
        or not source_lines.get(evidence.get("line_id"), (None, ""))[1]
        for evidence in _iter_evidence(payload)
    ):
        failure_kinds.append("source line")
    elif _has_duplicate_item_evidence(payload) or not _literal_evidence_is_supported(
        payload,
        source_lines,
    ):
        failure_kinds.append("evidence support")

    checklist = payload.get("checklist")
    if not isinstance(checklist, dict) or set(checklist) != REQUIRED_CHECK_IDS:
        failure_kinds.append("checklist completeness")
    else:
        finding_counts = Counter(
            finding["check_id"] for finding in payload["findings"]
        )
        if any(
            checklist[check_id]["issue_count"] != finding_counts[check_id]
            for check_id in REQUIRED_CHECK_IDS
        ) or any(
            expected_check_id is not None
            and finding["check_id"] != expected_check_id
            for finding in payload["findings"]
            for expected_check_id in (
                _CATEGORY_CHECK_IDS.get(finding["category"]),
            )
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

    materialized = deepcopy(payload)
    for evidence in _iter_evidence(materialized):
        _, excerpt = source_lines[evidence["line_id"]]
        evidence["excerpt"] = excerpt

    return ValidatedDocumentAnalysis(
        schema_version=SCHEMA_VERSION,
        payload=materialized,
    )


def _iter_evidence(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if "page_id" in value or "line_id" in value or "excerpt" in value:
            yield value
        for child in value.values():
            yield from _iter_evidence(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_evidence(child)


def _source_line_index(
    pages: Mapping[str, str],
) -> dict[str, tuple[str, str]]:
    index: dict[str, tuple[str, str]] = {}
    for page_number, (page_id, text) in enumerate(pages.items(), start=1):
        page = SourcePage(page_id, page_number, text)
        for line in page.lines:
            index[line.line_id] = (page_id, line.text)
    return index


def _has_duplicate_item_evidence(payload: dict[str, Any]) -> bool:
    facts = payload["facts"]
    items = [
        *facts["contact"],
        *facts["education"],
        *facts["employment"],
        *payload["findings"],
    ]
    for item in items:
        evidence = item["evidence"]
        line_ids = [entry["line_id"] for entry in evidence]
        if len(line_ids) != len(set(line_ids)):
            return True
    return False


def _literal_evidence_is_supported(
    payload: dict[str, Any],
    source_lines: Mapping[str, tuple[str, str]],
) -> bool:
    facts = payload["facts"]
    for fact in facts["contact"]:
        if not _fields_appear_in_evidence(fact, ("value",), source_lines):
            return False
    for fact in facts["education"]:
        if not _fields_appear_in_evidence(
            fact,
            ("institution",),
            source_lines,
        ) or not _fields_appear_in_evidence(
            fact,
            ("program", "study_dates"),
            source_lines,
            allow_source_ordered_join=True,
        ):
            return False
    for fact in facts["employment"]:
        if not _fields_appear_in_evidence(
            fact,
            ("organization",),
            source_lines,
        ) or not _fields_appear_in_evidence(
            fact,
            ("role", "employment_dates", "location"),
            source_lines,
            allow_source_ordered_join=True,
        ):
            return False
    for candidate in payload["research_candidates"]:
        if not _fields_appear_in_evidence(
            candidate,
            ("query_subject",),
            source_lines,
        ):
            return False
    return True


def _fields_appear_in_evidence(
    item: Mapping[str, Any],
    field_names: tuple[str, ...],
    source_lines: Mapping[str, tuple[str, str]],
    *,
    allow_source_ordered_join: bool = False,
) -> bool:
    evidence_lines = [
        (
            evidence["line_id"],
            evidence["page_id"],
            int(evidence["line_id"].rsplit("-line-", 1)[1]),
            source_lines[evidence["line_id"]][1],
        )
        for evidence in (
            item["evidence"]
            if isinstance(item["evidence"], list)
            else [item["evidence"]]
        )
    ]
    for field_name in field_names:
        value = item.get(field_name)
        if value is None:
            continue
        normalized = _normalize_literal(value)
        supported_by_one_line = any(
            normalized in _normalize_literal(line)
            for _, _, _, line in evidence_lines
        )
        supported_by_join = (
            allow_source_ordered_join
            and _semantic_value_is_supported_by_local_window(
                value,
                evidence_lines,
            )
        )
        if not normalized or not (supported_by_one_line or supported_by_join):
            return False
    return True


def _normalize_literal(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.translate(str.maketrans({"–": "-", "—": "-", "−": "-"}))
    return " ".join(normalized.split())


def _normalize_semantic_literal(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    without_punctuation = "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in normalized
    )
    return " ".join(without_punctuation.split())


def _tokens_are_subsequence(
    expected_tokens: list[str],
    source_tokens: list[str],
) -> bool:
    source = iter(source_tokens)
    return all(any(token == candidate for candidate in source) for token in expected_tokens)


def _semantic_value_is_supported_by_local_window(
    value: str,
    evidence_lines: list[tuple[str, str, int, str]],
) -> bool:
    expected_tokens = _normalize_semantic_literal(value).split()
    if not expected_tokens:
        return False
    lines_by_page: dict[str, list[tuple[int, str]]] = {}
    for _, page_id, line_number, text in evidence_lines:
        lines_by_page.setdefault(page_id, []).append((line_number, text))
    for page_lines in lines_by_page.values():
        ordered_lines = sorted(page_lines)
        for start in range(len(ordered_lines)):
            for end in range(start + 2, min(start + 3, len(ordered_lines)) + 1):
                window = ordered_lines[start:end]
                if window[-1][0] - window[0][0] > 4:
                    continue
                if any(
                    later[0] - earlier[0] > 2
                    for earlier, later in zip(window, window[1:])
                ):
                    continue
                source_tokens = _normalize_semantic_literal(
                    " ".join(text for _, text in window)
                ).split()
                if _tokens_are_subsequence(expected_tokens, source_tokens):
                    return True
    return False


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
