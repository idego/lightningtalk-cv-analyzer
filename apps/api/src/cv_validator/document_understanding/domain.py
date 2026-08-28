from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Any

from cv_validator.domain import DeterministicAnalysisResult
from cv_validator.ingestion import RedactedDocument
from cv_validator.structural.domain import StructuralAuditResult


class Status(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SectionKind(str, Enum):
    CONTACT = "contact"
    SUMMARY = "summary"
    EMPLOYMENT = "employment"
    EDUCATION = "education"
    SKILLS = "skills"
    CERTIFICATIONS = "certifications"
    PROJECTS = "projects"
    LANGUAGES = "languages"
    PUBLICATIONS = "publications"
    AWARDS = "awards"
    VOLUNTEERING = "volunteering"
    REFERENCES = "references"
    OTHER = "other"


@dataclass(frozen=True)
class UnderstandingEvidence:
    page_id: str
    page_number: int
    line_id: str | None
    start_offset: int | None
    end_offset: int | None
    association: str
    excerpt: str | None


@dataclass(frozen=True)
class SectionSpan:
    id: str
    kind: SectionKind
    confidence: Confidence
    heading: str
    start_line_id: str
    end_line_id: str
    evidence: tuple[UnderstandingEvidence, ...]
    source_order: int


@dataclass(frozen=True)
class DateRangeAnnotation:
    id: str
    source_literal: str
    start_month: str | None
    end_month: str | None
    start_precision: str
    end_precision: str
    status: str
    snapshot_month: str
    evidence: tuple[UnderstandingEvidence, ...]
    source_order: int
    timeline_entry_id: str


@dataclass(frozen=True)
class EntrySpan:
    id: str
    section_id: str
    block_ids: tuple[str, ...]
    date_range_ids: tuple[str, ...]
    source_order: int


@dataclass(frozen=True)
class AmbiguousSpan:
    id: str
    category: str
    reason_code: str
    evidence: tuple[UnderstandingEvidence, ...]
    source_order: int


@dataclass(frozen=True)
class StructuredField:
    name: str
    status: str
    value: str | None
    confidence: Confidence
    evidence: tuple[UnderstandingEvidence, ...]


@dataclass(frozen=True)
class StructuredRecord:
    id: str
    kind: str
    section_id: str
    confidence: Confidence
    fields: tuple[StructuredField, ...]
    date_range_ids: tuple[str, ...]
    source_order: int


@dataclass(frozen=True)
class ResearchSubject:
    id: str
    category: str
    subject: str
    record_id: str
    field_name: str
    source_order: int


@dataclass(frozen=True)
class UnderstandingCoverage:
    status: Status
    source_format: str
    audited_parts: tuple[str, ...]
    omitted_parts: tuple[str, ...]


@dataclass(frozen=True)
class DocumentAnnotationIndex:
    exclusion_intervals: tuple[tuple[str, int, int], ...]
    sections: tuple[SectionSpan, ...]
    date_ranges: tuple[DateRangeAnnotation, ...]


@dataclass(frozen=True)
class DocumentUnderstandingResult:
    document: RedactedDocument
    annotation_index: DocumentAnnotationIndex
    deterministic: DeterministicAnalysisResult
    structural_audits: StructuralAuditResult
    sections: tuple[SectionSpan, ...]
    date_ranges: tuple[DateRangeAnnotation, ...]
    records: tuple[StructuredRecord, ...]
    skills: tuple[Any, ...]
    ambiguous_spans: tuple[Any, ...]
    timeline_record_links: tuple[dict[str, str], ...]
    code_research_subjects: tuple[ResearchSubject, ...]
    coverage: UnderstandingCoverage
    snapshot_month: str
    parser_version: str = "document-understanding-parser-v1"
    ruleset_version: str = "document-understanding-rules-v1"


def stable_source_id(category: str, page_id: str, start: int, end: int) -> str:
    seed = f"{category}\0{page_id}\0{start}\0{end}".encode()
    return f"{category}-{sha256(seed).hexdigest()[:20]}"
