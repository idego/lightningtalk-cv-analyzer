from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

CONTRACT_VERSION = "structural-audits-v1"
PARSER_VERSION = "timeline-parser-v1"
DETECTOR_VERSION = "visibility-detector-v1"


class AuditStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class Association(str, Enum):
    EXACT = "exact"
    PARTIAL = "partial"
    UNMAPPED = "unmapped"


@dataclass(frozen=True)
class BBox:
    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        if self.x0 > self.x1 or self.y0 > self.y1:
            raise ValueError("invalid bounding box")


@dataclass(frozen=True)
class SourceLocation:
    page_id: str
    page_number: int
    line_id: str | None = None
    line_number: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    paragraph_path: str | None = None
    bbox: BBox | None = None
    association: Association = Association.UNMAPPED

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise ValueError("page_number must be positive")
        if self.association is Association.UNMAPPED and (
            self.start_offset is not None or self.end_offset is not None
        ):
            raise ValueError("unmapped locations cannot have offsets")
        if (self.start_offset is None) != (self.end_offset is None):
            raise ValueError("source offsets must be supplied together")


@dataclass(frozen=True)
class TimelineEvidence:
    location: SourceLocation
    excerpt: str

    def __post_init__(self) -> None:
        if len(self.excerpt) > 256:
            raise ValueError("timeline excerpt exceeds 256 characters")


@dataclass(frozen=True)
class TimelineEntry:
    id: str
    category: str
    status: str
    start_text: str | None
    end_text: str | None
    start_month: str | None
    end_month: str | None
    start_precision: str
    end_precision: str
    source_location: SourceLocation
    evidence: tuple[TimelineEvidence, ...]


@dataclass(frozen=True)
class TimelineSummary:
    category: str
    entry_count: int
    earliest_month: str | None
    latest_month: str | None
    non_overlapping_months: int


@dataclass(frozen=True)
class TimelineObservation:
    id: str
    kind: str
    status: str
    entry_ids: tuple[str, ...]
    overlap_months: int | None
    precision: str | None
    reason_code: str
    evidence: tuple[TimelineEvidence, ...]


@dataclass(frozen=True)
class RedactionMetadata:
    present: bool
    type_hints: tuple[str, ...]


@dataclass(frozen=True)
class VisibilityObservation:
    id: str
    kind: str
    status: str
    confidence: str
    source_location: SourceLocation
    trigger_codes: tuple[str, ...]
    character_count: int
    word_count: int
    redaction: RedactionMetadata | None
    threshold_version: str


@dataclass(frozen=True)
class Coverage:
    status: AuditStatus
    source_format: str
    audited_parts: tuple[str, ...]
    omitted_parts: tuple[str, ...]


@dataclass(frozen=True)
class TimelineAudit:
    status: AuditStatus
    parser_version: str
    entries: tuple[TimelineEntry, ...]
    summaries: tuple[TimelineSummary, ...]
    observations: tuple[TimelineObservation, ...]
    reported_entry_count: int
    additional_entry_count: int
    truncated: bool


@dataclass(frozen=True)
class VisibilityAudit:
    status: AuditStatus
    detector_version: str
    threshold_version: str
    observations: tuple[VisibilityObservation, ...]
    reported_observation_count: int
    additional_observation_count: int
    truncated: bool


@dataclass(frozen=True)
class StructuralAuditResult:
    status: AuditStatus
    snapshot_month: str | None
    coverage: Coverage
    timeline: TimelineAudit
    visibility: VisibilityAudit
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError("unsupported structural audit contract")

    def to_dict(self) -> dict[str, Any]:
        return _json_value(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> StructuralAuditResult | None:
        if payload is None:
            return None
        def loc(raw: dict[str, Any]) -> SourceLocation:
            bbox = raw.get("bbox")
            return SourceLocation(**{**raw, "association": Association(raw["association"]), "bbox": BBox(**bbox) if bbox else None})
        def evidence(raw: dict[str, Any]) -> TimelineEvidence:
            return TimelineEvidence(location=loc(raw["location"]), excerpt=raw["excerpt"])
        timeline_raw = payload["timeline"]
        visibility_raw = payload["visibility"]
        entries = tuple(TimelineEntry(**{**item, "source_location": loc(item["source_location"]), "evidence": tuple(evidence(value) for value in item["evidence"])}) for item in timeline_raw["entries"])
        observations = tuple(TimelineObservation(**{**item, "entry_ids": tuple(item["entry_ids"]), "evidence": tuple(evidence(value) for value in item["evidence"])}) for item in timeline_raw["observations"])
        visibility = tuple(VisibilityObservation(**{**item, "source_location": loc(item["source_location"]), "trigger_codes": tuple(item["trigger_codes"]), "redaction": RedactionMetadata(present=item["redaction"]["present"], type_hints=tuple(item["redaction"]["type_hints"])) if item.get("redaction") else None}) for item in visibility_raw["observations"])
        coverage_raw = payload["coverage"]
        return cls(
            contract_version=payload["contract_version"], status=AuditStatus(payload["status"]), snapshot_month=payload.get("snapshot_month"),
            coverage=Coverage(status=AuditStatus(coverage_raw["status"]), source_format=coverage_raw["source_format"], audited_parts=tuple(coverage_raw["audited_parts"]), omitted_parts=tuple(coverage_raw["omitted_parts"])),
            timeline=TimelineAudit(**{**timeline_raw, "status": AuditStatus(timeline_raw["status"]), "entries": entries, "summaries": tuple(TimelineSummary(**item) for item in timeline_raw["summaries"]), "observations": observations}),
            visibility=VisibilityAudit(**{**visibility_raw, "status": AuditStatus(visibility_raw["status"]), "observations": visibility}),
        )


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value
