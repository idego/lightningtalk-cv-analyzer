from __future__ import annotations

import re
from dataclasses import replace
from collections.abc import Iterable

from cv_validator.domain import (
    Authority,
    Candidate,
    CandidateId,
    CandidateKind,
    ComponentVersion,
    Evidence,
    LocationRelation,
    Provenance,
    SourceContext,
    Subject,
)
from cv_validator.extraction.postal import POSTAL_PATTERNS
from cv_validator.ingestion import RedactedDocument, SourcePage
from cv_validator.ingestion.redaction import NATIONAL_ID_REDACTION_VERSION
from cv_validator.phone_policy import PHONE_CANDIDATE_EXTRACTOR
from cv_validator.document_understanding.annotations import date_range_spans

CANDIDATE_EXTRACTOR_VERSION = PHONE_CANDIDATE_EXTRACTOR.version

_PERSON_PHONE_LABEL = re.compile(
    r"\b(?:phone|mobile|telephone|tel|contact[ \t]+number|telefon|"
    r"telefon[ \t]+komórkowy|handy|mobil)\b[ \t]*[:#-]?[ \t]*$",
    re.IGNORECASE,
)
_NON_PERSON_PHONE_LABEL = re.compile(
    r"\b(?:fax|referee|reference|company|office)\b",
    re.IGNORECASE,
)

_PHONE = re.compile(
    r"(?<![\w])(?:\+|00)?\d(?:[\d \t()./-]*\d){6,}"
    r"(?:[ \t]*(?:ext\.?|x)[ \t]*\d{1,6})?(?!\w)",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_URL = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>]+")
_DATE_PATTERNS = (
    re.compile(r"\b\d{1,2}[/.]\d{4}\b"),
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
_RIGHT_TO_WORK = re.compile(
    r"(?im)^[ \t]*(?P<value>[^\n]*(?:right[ \t]+to[ \t]+work|"
    r"work[ \t]+authori[sz]ation|visa[ \t]+status|requires[ \t]+sponsorship|"
    r"eligible[ \t]+to[ \t]+work)[^\n]*?)[ \t]*$"
)
_PERSON_SPECIFIC_LOCATION = re.compile(
    r"(?im)^[ \t]*(?P<label>candidate[ \t]+location|current[ \t]+location|"
    r"place[ \t]+of[ \t]+residence|home[ \t]+address|lokalizacja[ \t]+kandydata|"
    r"obecna[ \t]+lokalizacja|miejsce[ \t]+zamieszkania|adres[ \t]+zamieszkania)"
    r"[ \t]*[:#-][ \t]*(?P<value>[^\n]+?)[ \t]*$"
)
_GENERIC_LOCATION = re.compile(
    r"(?im)^[ \t]*(?P<label>location|address|lokalizacja|adres)"
    r"[ \t]*[:#-][ \t]*(?P<value>[^\n]+?)[ \t]*$|"
    r"^[ \t]*(?P<label_phrase>based[ \t]+in|mieszka[ \t]+w)"
    r"(?:[ \t]*[:#-][ \t]*|[ \t]+)(?P<value_phrase>[^\n]+?)[ \t]*$"
)
_RELATED_LOCATION_PATTERNS = (
    (
        LocationRelation.EMPLOYER,
        re.compile(
            r"(?im)^[ \t]*(?P<label>employer(?:[ \t]+location)?|"
            r"company[ \t]+location|lokalizacja[ \t]+pracodawcy|siedziba[ \t]+firmy)"
            r"[ \t]*[:#-][ \t]*(?P<value>[^\n]+?)[ \t]*$"
        ),
    ),
    (
        LocationRelation.CLIENT,
        re.compile(
            r"(?im)^[ \t]*(?P<label>client[ \t]+location|lokalizacja[ \t]+klienta)"
            r"[ \t]*[:#-][ \t]*(?P<value>[^\n]+?)[ \t]*$"
        ),
    ),
    (
        LocationRelation.PROJECT,
        re.compile(
            r"(?im)^[ \t]*(?P<label>project[ \t]+location|lokalizacja[ \t]+projektu)"
            r"[ \t]*[:#-][ \t]*(?P<value>[^\n]+?)[ \t]*$"
        ),
    ),
    (
        LocationRelation.OFFICE,
        re.compile(
            r"(?im)^[ \t]*(?P<label>office[ \t]+location|lokalizacja[ \t]+biura)"
            r"[ \t]*[:#-][ \t]*(?P<value>[^\n]+?)[ \t]*$"
        ),
    ),
    (
        LocationRelation.EDUCATION,
        re.compile(
            r"(?im)^[ \t]*(?P<label>(?:education|school|university)[ \t]+location|"
            r"lokalizacja[ \t]+(?:uczelni|szkoły))"
            r"[ \t]*[:#-][ \t]*(?P<value>[^\n]+?)[ \t]*$"
        ),
    ),
)


def extract_candidates(document: RedactedDocument, *, exclusion_index=None) -> tuple[Candidate, ...]:
    candidates: list[Candidate] = []
    seen: set[tuple[CandidateKind, str, int, int]] = set()

    for page in document.pages:
        email_matches = tuple(_EMAIL.finditer(page.text))
        email_spans = tuple(match.span() for match in email_matches)
        candidates.extend(
            _from_matches(
                page,
                CandidateKind.PHONE,
                _PHONE.finditer(page.text),
                seen,
                excluded_spans=email_spans,
            )
        )
        candidates.extend(
            _from_matches(page, CandidateKind.EMAIL, email_matches, seen)
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
                CandidateKind.RIGHT_TO_WORK,
                _RIGHT_TO_WORK.finditer(page.text),
                seen,
                group="value",
            )
        )
        candidates.extend(_explicit_location_candidates(page, seen))

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

    result = tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.provenance.evidence[0].page_number,
                candidate.provenance.evidence[0].start_offset,
                candidate.kind.value,
            ),
        )
    )
    if exclusion_index is None:
        return result
    admitted = []
    for candidate in result:
        evidence = tuple(e for e in candidate.provenance.evidence if not exclusion_index.intersects(e.page_id, e.start_offset, e.end_offset))
        if not evidence:
            continue
        relation_evidence = tuple(e for e in candidate.relation_evidence if not exclusion_index.intersects(e.page_id, e.start_offset, e.end_offset))
        value_evidence = tuple(e for e in candidate.value_evidence if not exclusion_index.intersects(e.page_id, e.start_offset, e.end_offset))
        if candidate.relation_evidence and len(relation_evidence) != len(candidate.relation_evidence):
            # Ownership labels are atomic. A visible value cannot inherit a
            # person/employer/client relation from quarantined label evidence.
            continue
        admitted.append(replace(
            candidate,
            provenance=replace(candidate.provenance, evidence=evidence),
            relation_evidence=relation_evidence,
            value_evidence=value_evidence,
        ))
    return tuple(admitted)


def _from_matches(
    page: SourcePage,
    kind: CandidateKind,
    matches: Iterable[re.Match[str]],
    seen: set[tuple[CandidateKind, str, int, int]],
    group: int | str = 0,
    excluded_spans: tuple[tuple[int, int], ...] = (),
) -> list[Candidate]:
    candidates: list[Candidate] = []
    for match in matches:
        start_offset, end_offset = match.span(group)
        value = match.group(group)
        if any(
            start_offset < excluded_end and excluded_start < end_offset
            for excluded_start, excluded_end in excluded_spans
        ):
            continue
        if kind is CandidateKind.PHONE:
            explicitly_labeled = _phone_subject(page.text, start_offset) is Subject.PERSON
            has_international_prefix = bool(re.match(r"\s*(?:\+|00)", value))
            if any(left <= start_offset and end_offset <= right for left, right in date_range_spans(page.text)) and not (
                explicitly_labeled and has_international_prefix
            ):
                continue
            if any(pattern.fullmatch(value.strip()) for pattern in _DATE_PATTERNS):
                continue
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
                    extractor=PHONE_CANDIDATE_EXTRACTOR,
                ),
                subject=(
                    _phone_subject(page.text, start_offset)
                    if kind is CandidateKind.PHONE
                    else Subject.UNKNOWN
                ),
            )
        )
    return candidates


def _phone_subject(page_text: str, start_offset: int) -> Subject:
    line_start = page_text.rfind("\n", 0, start_offset) + 1
    prefix = page_text[line_start:start_offset]
    if _NON_PERSON_PHONE_LABEL.search(prefix):
        return Subject.UNKNOWN
    # A phone number in a candidate's CV is candidate-owned by default. Only an
    # explicit reference, company, office or fax label overrides that ownership.
    # This keeps ordinary unlabeled contact blocks useful while still failing
    # closed when the document names a different owner.
    return Subject.PERSON


def _candidate_id(
    kind: CandidateKind,
    page: SourcePage,
    start_offset: int,
    end_offset: int,
) -> CandidateId:
    return CandidateId(
        f"candidate:{kind.value}:{page.page_id}:{start_offset}:{end_offset}"
    )


def _explicit_location_candidates(
    page: SourcePage,
    seen: set[tuple[CandidateKind, str, int, int]],
) -> list[Candidate]:
    candidates: list[Candidate] = []
    patterns = (
        (LocationRelation.PERSON, _PERSON_SPECIFIC_LOCATION, True),
        (LocationRelation.UNKNOWN, _GENERIC_LOCATION, False),
        *((relation, pattern, True) for relation, pattern in _RELATED_LOCATION_PATTERNS),
    )
    for configured_relation, pattern, relation_is_fixed in patterns:
        for match in pattern.finditer(page.text):
            value_group = "value" if match.groupdict().get("value") is not None else "value_phrase"
            label_group = "label" if match.groupdict().get("label") is not None else "label_phrase"
            start_offset, end_offset = match.span(value_group)
            source_context = source_context_for_offset(page, start_offset)
            relation = configured_relation
            if not relation_is_fixed and source_context is SourceContext.DOCUMENT_START_BLOCK:
                relation = LocationRelation.PERSON
            key = (
                CandidateKind.EXPLICIT_LOCATION,
                page.page_id,
                start_offset,
                end_offset,
            )
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                Candidate(
                    id=_candidate_id(
                        CandidateKind.EXPLICIT_LOCATION,
                        page,
                        start_offset,
                        end_offset,
                    ),
                    kind=CandidateKind.EXPLICIT_LOCATION,
                    value=match.group(value_group),
                    provenance=Provenance(
                        authority=Authority.CODE,
                        evidence=(Evidence.from_page(page, start_offset, end_offset),),
                        extractor=ComponentVersion(
                            "contact-candidates",
                            CANDIDATE_EXTRACTOR_VERSION,
                        ),
                    ),
                    relation=relation,
                    subject=(
                        Subject.PERSON
                        if relation is LocationRelation.PERSON
                        else Subject.UNKNOWN
                    ),
                    source_context=source_context,
                    label=match.group(label_group),
                    relation_evidence=(Evidence.from_page(page, *match.span(0)),),
                    value_evidence=(Evidence.from_page(page, start_offset, end_offset),),
                )
            )
    return candidates


def source_context_for_offset(page: SourcePage, offset: int) -> SourceContext:
    if page.page_number != 1:
        return SourceContext.DOCUMENT_BODY
    block_started = False
    cursor = 0
    for line in page.text.splitlines(keepends=True):
        line_end = cursor + len(line)
        is_blank = not line.rstrip("\r\n").strip()
        if not block_started and not is_blank:
            block_started = True
        elif block_started and is_blank:
            return (
                SourceContext.DOCUMENT_START_BLOCK
                if offset < cursor
                else SourceContext.DOCUMENT_BODY
            )
        if cursor <= offset < line_end and block_started:
            return SourceContext.DOCUMENT_START_BLOCK
        cursor = line_end
    return (
        SourceContext.DOCUMENT_START_BLOCK
        if block_started and offset <= len(page.text)
        else SourceContext.DOCUMENT_BODY
    )
