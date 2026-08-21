from __future__ import annotations

import re
from collections.abc import Iterable

from cv_validator.domain import (
    Authority,
    Candidate,
    CandidateId,
    CandidateKind,
    ComponentVersion,
    Evidence,
    Provenance,
)
from cv_validator.gazetteer.data import POSTAL_PATTERNS
from cv_validator.ingestion import RedactedDocument, SourcePage
from cv_validator.ingestion.redaction import NATIONAL_ID_REDACTION_VERSION

CANDIDATE_EXTRACTOR_VERSION = "1"

_PHONE = re.compile(
    r"(?<![\w])(?:\+|00)?\d(?:[\d \t()./-]*\d){6,}"
    r"(?:[ \t]*(?:ext\.?|x)[ \t]*\d{1,6})?(?!\w)",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_URL = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>]+")
_DATE_PATTERNS = (
    re.compile(r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b"),
    re.compile(r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b"),
    re.compile(
        r"(?i)\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b"
    ),
    re.compile(
        r"(?i)\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|"
        r"Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|"
        r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b"
    ),
)
_POSTAL = re.compile(
    "|".join(f"(?:{pattern})" for pattern in POSTAL_PATTERNS.values()),
    re.IGNORECASE,
)
_EXPLICIT_LOCATION = re.compile(
    r"(?im)^[ \t]*(?:current[ \t]+location|location|based[ \t]+in|residence|"
    r"address|lokalizacja|miejsce[ \t]+zamieszkania|adres)"
    r"(?:[ \t]*[:#-][ \t]*|[ \t]+)(?P<value>[^\n]+?)[ \t]*$"
)


def extract_candidates(document: RedactedDocument) -> tuple[Candidate, ...]:
    candidates: list[Candidate] = []
    seen: set[tuple[CandidateKind, str, int, int]] = set()

    for page in document.pages:
        candidates.extend(
            _from_matches(page, CandidateKind.PHONE, _PHONE.finditer(page.text), seen)
        )
        candidates.extend(
            _from_matches(page, CandidateKind.EMAIL, _EMAIL.finditer(page.text), seen)
        )
        candidates.extend(
            _from_matches(page, CandidateKind.URL, _URL.finditer(page.text), seen)
        )
        for pattern in _DATE_PATTERNS:
            candidates.extend(
                _from_matches(
                    page,
                    CandidateKind.DATE,
                    pattern.finditer(page.text),
                    seen,
                )
            )
        candidates.extend(
            _from_matches(page, CandidateKind.POSTAL, _POSTAL.finditer(page.text), seen)
        )
        candidates.extend(
            _from_matches(
                page,
                CandidateKind.EXPLICIT_LOCATION,
                _EXPLICIT_LOCATION.finditer(page.text),
                seen,
                group="value",
            )
        )

    pages = {page.page_id: page for page in document.pages}
    for redaction in document.redactions:
        page = pages[redaction.page_id]
        key = (
            CandidateKind.NATIONAL_ID,
            page.page_id,
            redaction.start_offset,
            redaction.end_offset,
        )
        if key in seen:
            continue
        seen.add(key)
        evidence = Evidence.from_page(
            page,
            redaction.start_offset,
            redaction.end_offset,
        )
        candidates.append(
            Candidate(
                id=_candidate_id(
                    CandidateKind.NATIONAL_ID,
                    page,
                    redaction.start_offset,
                    redaction.end_offset,
                ),
                kind=CandidateKind.NATIONAL_ID,
                value=f"present:{'+'.join(redaction.type_hints)}",
                provenance=Provenance(
                    authority=Authority.CODE,
                    evidence=(evidence,),
                    extractor=ComponentVersion(
                        "national-id-redaction",
                        NATIONAL_ID_REDACTION_VERSION,
                    ),
                ),
            )
        )

    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.provenance.evidence[0].page_number,
                candidate.provenance.evidence[0].start_offset,
                candidate.kind.value,
            ),
        )
    )


def _from_matches(
    page: SourcePage,
    kind: CandidateKind,
    matches: Iterable[re.Match[str]],
    seen: set[tuple[CandidateKind, str, int, int]],
    group: int | str = 0,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    for match in matches:
        start_offset, end_offset = match.span(group)
        value = match.group(group)
        if kind is CandidateKind.PHONE:
            core = re.split(r"(?i)[ \t]*(?:ext\.?|x)[ \t]*", value, maxsplit=1)[0]
            digit_count = len(re.sub(r"\D", "", core))
            if not 7 <= digit_count <= 15:
                continue

        key = (kind, page.page_id, start_offset, end_offset)
        if key in seen:
            continue
        seen.add(key)
        evidence = Evidence.from_page(page, start_offset, end_offset)
        candidates.append(
            Candidate(
                id=_candidate_id(kind, page, start_offset, end_offset),
                kind=kind,
                value=value,
                provenance=Provenance(
                    authority=Authority.CODE,
                    evidence=(evidence,),
                    extractor=ComponentVersion(
                        "contact-candidates",
                        CANDIDATE_EXTRACTOR_VERSION,
                    ),
                ),
            )
        )
    return candidates


def _candidate_id(
    kind: CandidateKind,
    page: SourcePage,
    start_offset: int,
    end_offset: int,
) -> CandidateId:
    return CandidateId(
        f"candidate:{kind.value}:{page.page_id}:{start_offset}:{end_offset}"
    )
