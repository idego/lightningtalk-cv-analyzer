from __future__ import annotations

import re
from datetime import date

from cv_validator.document_understanding.domain import (
    Confidence, SectionKind, SectionSpan, UnderstandingEvidence, stable_source_id,
)
from cv_validator.document_understanding.normalization import normalize_text
from cv_validator.document_understanding.visibility import (
    VisibilityExclusionIndex, build_visibility_exclusion_index,
)
from cv_validator.ingestion import RedactedDocument, SourceLine
from cv_validator.structural.config import StructuralAuditConfig
from cv_validator.structural.domain import (
    Association, AuditStatus, BBox, Coverage, DETECTOR_VERSION,
    PARSER_VERSION, RedactionMetadata, SourceLocation, StructuralAuditResult,
    TimelineAudit, TimelineEntry, TimelineEvidence, TimelineObservation,
    TimelineSummary, VisibilityAudit, VisibilityObservation,
)

_MONTHS = {
    "jan": 1, "january": 1, "sty": 1, "styczen": 1, "stycznia": 1,
    "feb": 2, "february": 2, "lut": 2, "luty": 2, "lutego": 2,
    "mar": 3, "march": 3, "marzec": 3, "marca": 3,
    "apr": 4, "april": 4, "kwi": 4, "kwiecien": 4, "kwietnia": 4,
    "may": 5, "maj": 5, "maja": 5,
    "jun": 6, "june": 6, "cze": 6, "czerwiec": 6, "czerwca": 6,
    "jul": 7, "july": 7, "lip": 7, "lipiec": 7, "lipca": 7,
    "aug": 8, "august": 8, "sie": 8, "sierpien": 8, "sierpnia": 8,
    "sep": 9, "sept": 9, "september": 9, "wrz": 9, "wrzesien": 9, "wrzesnia": 9,
    "oct": 10, "october": 10, "paz": 10, "pazdziernik": 10, "pazdziernika": 10,
    "nov": 11, "november": 11, "lis": 11, "listopad": 11, "listopada": 11,
    "dec": 12, "december": 12, "gru": 12, "grudzien": 12, "grudnia": 12,
}
_TOKEN = r"(?:\d{1,2}[./-]\d{4}|\d{4}|[A-Za-zĄąĆćĘęŁłŃńÓóŚśŹźŻż]{3,12}\.?\s+\d{4}|present|current|now|obecnie|teraz)"
_RANGE = re.compile(rf"(?P<start>{_TOKEN})\s*(?:-|–|—|\bto\b|\bdo\b)\s*(?P<end>{_TOKEN})", re.I)
SECTION_ALIASES = {
    SectionKind.CONTACT: {"contact", "contact details", "personal details", "kontakt", "dane kontaktowe", "dane osobowe"},
    SectionKind.SUMMARY: {"summary", "profile", "professional summary", "podsumowanie", "profil zawodowy"},
    SectionKind.EMPLOYMENT: {"experience", "work experience", "employment", "professional experience", "doswiadczenie", "doswiadczenie zawodowe", "zatrudnienie"},
    SectionKind.EDUCATION: {"education", "academic background", "wyksztalcenie", "edukacja"},
    SectionKind.SKILLS: {"skills", "technical skills", "umiejetnosci", "kompetencje"},
    SectionKind.CERTIFICATIONS: {"certifications", "certificates", "certyfikaty"},
    SectionKind.PROJECTS: {"projects", "projekty"},
    SectionKind.LANGUAGES: {"languages", "jezyki", "jezyki obce"},
    SectionKind.PUBLICATIONS: {"publications", "publikacje"},
    SectionKind.AWARDS: {"awards", "honors", "nagrody", "wyroznienia"},
    SectionKind.VOLUNTEERING: {"volunteering", "volunteer experience", "wolontariat"},
    SectionKind.REFERENCES: {"references", "referencje"},
}
_EXCLUDED = re.compile(r"\b(?:birth|born|dob|date of birth|urodz|certificate|certification|publication|project|award)\b", re.I)


def date_range_spans(text: str) -> tuple[tuple[int, int], ...]:
    """Expose the shared range grammar without creating a second parser."""
    return tuple(match.span() for match in _RANGE.finditer(text))


def build_shared_annotations(document: RedactedDocument, *, snapshot_month: str | None = None, config: StructuralAuditConfig | None = None):
    """Own the shared section/date/visibility grammar for all projections."""
    cfg = config or StructuralAuditConfig()
    snapshot = snapshot_month or date.today().strftime("%Y-%m")
    exclusion = build_visibility_exclusion_index(document, cfg)
    sections = detect_sections(document, exclusion)
    timeline = _timeline(document, snapshot, cfg, sections, exclusion)
    visibility = _visibility(document, cfg)
    return snapshot, exclusion, sections, timeline, visibility


def project_structural_v1(document: RedactedDocument, snapshot: str, timeline: TimelineAudit, visibility: VisibilityAudit) -> StructuralAuditResult:
    """Serialize shared annotations through the unchanged V1 domain contract."""
    omitted = document.presentation_omitted_parts
    coverage_status = AuditStatus.PARTIAL if omitted or document.presentation_truncated else AuditStatus.COMPLETED
    audited = document.presentation_audited_parts
    if document.source_format == "text":
        audited = ("plain_text_pages",)
    coverage = Coverage(coverage_status, document.source_format, audited, omitted)
    statuses = (timeline.status, visibility.status, coverage.status)
    overall = AuditStatus.PARTIAL if AuditStatus.PARTIAL in statuses or AuditStatus.UNAVAILABLE in statuses else AuditStatus.COMPLETED
    return StructuralAuditResult(overall, snapshot, coverage, timeline, visibility)


def _timeline(document: RedactedDocument, snapshot: str, cfg: StructuralAuditConfig, sections: tuple[SectionSpan, ...], exclusion: VisibilityExclusionIndex) -> TimelineAudit:
    entries: list[TimelineEntry] = []
    heading_categories = {section.start_line_id: section.kind.value if section.kind in {SectionKind.EMPLOYMENT, SectionKind.EDUCATION} else "unknown" for section in sections}
    category = "unknown"
    for page in document.pages:
        for line in page.lines:
            if line.line_id in heading_categories:
                category = heading_categories[line.line_id]
                continue
            matches = list(_RANGE.finditer(line.text))
            if not matches:
                continue
            if len(matches) > 1 or _EXCLUDED.search(line.text):
                category_for_entry = "unknown"
            else:
                category_for_entry = category
            for match in matches:
                if exclusion.intersects(line.page_id, line.start_offset + match.start(), line.start_offset + match.end()):
                    continue
                entry = _entry(page.page_number, line, match, category_for_entry, snapshot, len(entries) + 1, cfg)
                entries.append(entry)
    total_entries = len(entries)
    entries = entries[:cfg.max_timeline_entries]
    invalid = [_invalid_observation(entry, index + 1) for index, entry in enumerate(entries) if entry.status == "invalid"]
    overlaps = _overlaps(entries, len(invalid) + 1)
    all_observations = invalid + overlaps
    observations = all_observations[:cfg.max_timeline_observations]
    summaries = _summaries(entries)
    truncated = total_entries > len(entries) or len(all_observations) > len(observations)
    return TimelineAudit(AuditStatus.PARTIAL if truncated else AuditStatus.COMPLETED, PARSER_VERSION, tuple(entries), tuple(summaries), tuple(observations), len(entries), total_entries - len(entries), truncated)


def _entry(page_number: int, line: SourceLine, match: re.Match[str], category: str, snapshot: str, number: int, cfg: StructuralAuditConfig) -> TimelineEntry:
    start_text, end_text = match.group("start")[:64], match.group("end")[:64]
    start = _parse_endpoint(start_text, snapshot, False)
    end = _parse_endpoint(end_text, snapshot, True)
    status = "valid"
    if start[0] is None or end[0] is None or start[3] or end[3] or start[1] > end[2]:
        status = "invalid"
    if category == "unknown" and status == "valid":
        status = "unresolved"
    location = SourceLocation(line.page_id, page_number, line.line_id, line.line_number, line.start_offset + match.start(), line.start_offset + match.end(), association=Association.EXACT)
    evidence = TimelineEvidence(location, match.group(0)[:cfg.max_evidence_excerpt_chars])
    return TimelineEntry(f"timeline-entry-{number:04d}", category, status, start_text, end_text, start[0], end[0], start[4], end[4], location, (evidence,))


def _parse_endpoint(raw: str, snapshot: str, is_end: bool):
    token = _normalize(raw).rstrip(".")
    if token in {"present", "current", "now", "obecnie", "teraz"}:
        value = _month_index(snapshot)
        return snapshot, value, value, False, "open_ended"
    numeric = re.fullmatch(r"(\d{1,2})[./-](\d{4})", token)
    if numeric:
        month, year = int(numeric.group(1)), int(numeric.group(2))
        if not 1 <= month <= 12:
            return None, 0, 0, True, "month"
        value = year * 12 + month - 1
        return f"{year:04d}-{month:02d}", value, value, False, "month"
    if re.fullmatch(r"\d{4}", token):
        year = int(token)
        start, end = year * 12, year * 12 + 11
        return f"{year:04d}-{'12' if is_end else '01'}", start, end, False, "year"
    named = re.fullmatch(r"([^\s]+)\s+(\d{4})", token)
    if named:
        month = _MONTHS.get(_normalize(named.group(1)).rstrip("."))
        if month:
            year = int(named.group(2)); value = year * 12 + month - 1
            return f"{year:04d}-{month:02d}", value, value, False, "month"
    return None, 0, 0, True, "unknown"


def _invalid_observation(entry: TimelineEntry, number: int) -> TimelineObservation:
    start = _parse_endpoint(entry.start_text or "", "2000-01", False)
    end = _parse_endpoint(entry.end_text or "", "2000-01", True)
    reason = "invalid_month" if start[3] or end[3] else "start_after_end"
    return TimelineObservation(f"timeline-observation-{number:04d}", "invalid_period", "needs_review", (entry.id,), None, None, reason, entry.evidence)


def _overlaps(entries: list[TimelineEntry], start_number: int) -> list[TimelineObservation]:
    result = []
    valid = [entry for entry in entries if entry.status == "valid" and entry.category in {"employment", "education"}]
    for left_index, left in enumerate(valid):
        for right in valid[left_index + 1:]:
            if left.category != right.category or left.source_location == right.source_location:
                continue
            left_start = _month_index(left.start_month); left_end = _month_index(left.end_month)
            right_start = _month_index(right.start_month); right_end = _month_index(right.end_month)
            overlap = min(left_end, right_end) - max(left_start, right_start) + 1
            if overlap <= 0:
                continue
            exact = all(value in {"month", "open_ended"} for value in (left.start_precision, left.end_precision, right.start_precision, right.end_precision))
            number = start_number + len(result)
            result.append(TimelineObservation(f"timeline-observation-{number:04d}", "definite_overlap" if exact else "possible_overlap", "needs_review" if exact else "informational", (left.id, right.id), overlap if exact else None, "exact" if exact else "coarse", "definite_calendar_overlap" if exact else "possible_calendar_overlap", left.evidence + right.evidence))
    return result


def _summaries(entries: list[TimelineEntry]) -> list[TimelineSummary]:
    summaries = []
    for category in ("employment", "education", "unknown"):
        selected = [entry for entry in entries if entry.category == category and entry.status == "valid"]
        if not selected:
            continue
        intervals = sorted((_month_index(entry.start_month), _month_index(entry.end_month)) for entry in selected)
        merged = []
        for start, end in intervals:
            if merged and start <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        summaries.append(TimelineSummary(category, len(selected), min(entry.start_month for entry in selected if entry.start_month), max(entry.end_month for entry in selected if entry.end_month), sum(end - start + 1 for start, end in merged)))
    return summaries


def _visibility(document: RedactedDocument, cfg: StructuralAuditConfig) -> VisibilityAudit:
    if document.source_format == "text":
        return VisibilityAudit(AuditStatus.NOT_APPLICABLE, DETECTOR_VERSION, cfg.threshold_version, (), 0, 0, False)
    observations = []
    for span in _group_presentation_spans(document.presentation_spans):
        triggers = []
        if span.explicit_hidden: triggers.append("explicit_hidden")
        if span.font_size_points is not None and span.font_size_points <= cfg.near_zero_font_points: triggers.append("near_zero_font")
        if span.opacity is not None and span.opacity <= cfg.near_zero_opacity: triggers.append("zero_opacity")
        if span.foreground_luminance is not None and span.background_luminance is not None and span.foreground_luminance >= cfg.near_white_luminance and span.background_luminance >= cfg.known_light_background_luminance and abs(span.foreground_luminance - span.background_luminance) <= cfg.max_low_contrast_luminance_delta: triggers.append("low_contrast")
        meaningful = sum(ch.isalnum() for ch in span.text) >= cfg.minimum_meaningful_alphanumeric
        if span.redaction_type_hints: triggers.append("redacted_sensitive_span")
        if not triggers or (not meaningful and not span.redaction_type_hints): continue
        bbox = BBox(*span.bbox) if span.bbox else None
        location = SourceLocation(span.page_id, span.page_number, start_offset=span.start_offset, end_offset=span.end_offset, paragraph_path=span.paragraph_path, bbox=bbox, association=Association(span.association))
        kind = "hidden_text" if "explicit_hidden" in triggers else "near_zero_text" if "near_zero_font" in triggers else "zero_opacity_text" if "zero_opacity" in triggers else "low_contrast_text"
        observations.append(VisibilityObservation(f"visibility-observation-{len(observations)+1:04d}", kind, "needs_review", "high" if "explicit_hidden" in triggers else "medium", location, tuple(triggers[:4]), len(span.text), len(span.text.split()), RedactionMetadata(True, span.redaction_type_hints) if span.redaction_type_hints else None, cfg.threshold_version))
    total = len(observations); reported = observations[:cfg.max_visibility_observations]
    truncated = total > len(reported) or document.presentation_truncated
    status = AuditStatus.PARTIAL if truncated or document.presentation_omitted_parts else AuditStatus.COMPLETED
    return VisibilityAudit(status, DETECTOR_VERSION, cfg.threshold_version, tuple(reported), len(reported), total - len(reported), truncated)


def _group_presentation_spans(spans):
    from dataclasses import replace
    grouped = []
    for span in spans:
        signature = (span.page_id, span.association, span.font_size_points, span.foreground_luminance, span.background_luminance, span.opacity, span.explicit_hidden, span.redaction_type_hints, span.paragraph_path)
        if grouped:
            previous = grouped[-1]
            previous_signature = (previous.page_id, previous.association, previous.font_size_points, previous.foreground_luminance, previous.background_luminance, previous.opacity, previous.explicit_hidden, previous.redaction_type_hints, previous.paragraph_path)
            contiguous = previous.end_offset is not None and span.start_offset is not None and span.start_offset == previous.end_offset
            if signature == previous_signature and contiguous:
                bbox = None
                if previous.bbox and span.bbox:
                    bbox = (min(previous.bbox[0], span.bbox[0]), min(previous.bbox[1], span.bbox[1]), max(previous.bbox[2], span.bbox[2]), max(previous.bbox[3], span.bbox[3]))
                grouped[-1] = replace(previous, text=previous.text + span.text, end_offset=span.end_offset, bbox=bbox)
                continue
        grouped.append(span)
    return grouped


def _normalize(value: str) -> str:
    import unicodedata
    return " ".join("".join(ch for ch in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(ch)).strip().split())


def detect_sections(document: RedactedDocument, exclusion: VisibilityExclusionIndex) -> tuple[SectionSpan, ...]:
    lines = [line for page in document.pages for line in page.lines]
    headings: list[tuple[int, SourceLine, SectionKind]] = []
    for index, line in enumerate(lines):
        normalized = normalize_text(line.text.strip().rstrip(":"))
        kind = next((candidate for candidate, aliases in SECTION_ALIASES.items() if normalized in aliases), None)
        if kind is None and _looks_unknown_heading(line.text):
            kind = SectionKind.OTHER
        if kind is None or exclusion.intersects(line.page_id, line.start_offset, line.end_offset):
            continue
        headings.append((index, line, kind))
    result = []
    pages = {page.page_id: page for page in document.pages}
    for position, (index, line, kind) in enumerate(headings):
        end_index = headings[position + 1][0] - 1 if position + 1 < len(headings) else len(lines) - 1
        end_line = lines[max(index, end_index)]
        evidence = UnderstandingEvidence(line.page_id, pages[line.page_id].page_number, line.line_id, line.start_offset, line.end_offset, "exact", line.text[:256])
        result.append(SectionSpan(stable_source_id(f"section-{kind.value}", line.page_id, line.start_offset, line.end_offset), kind, Confidence.HIGH, line.text.strip(), line.line_id, end_line.line_id, (evidence,), index))
    return tuple(result)


def _looks_unknown_heading(value: str) -> bool:
    text = value.strip().rstrip(":")
    words = text.split()
    return bool(text) and not _RANGE.search(text) and len(words) <= 5 and (value.strip().endswith(":") or (text.upper() == text and any(ch.isalpha() for ch in text)))


def _month_index(value: str | None) -> int:
    if value is None: return 0
    year, month = value.split("-")
    return int(year) * 12 + int(month) - 1
