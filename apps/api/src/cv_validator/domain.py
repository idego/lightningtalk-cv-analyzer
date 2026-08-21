from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, NewType, Protocol


CandidateId = NewType("CandidateId", str)
FactId = NewType("FactId", str)
ObservationId = NewType("ObservationId", str)
ScoringSignalId = NewType("ScoringSignalId", str)


class Authority(str, Enum):
    CODE = "code"


class CandidateKind(str, Enum):
    PHONE = "phone"
    EMAIL = "email"
    URL = "url"
    DATE = "date"
    NATIONAL_ID = "national_id"
    POSTAL = "postal"
    EXPLICIT_LOCATION = "explicit_location"


class FactKind(str, Enum):
    PHONE_COUNTRY = "phone_country"


class ObservationKind(str, Enum):
    PHONE = "phone"
    PHONE_COUNTRY_AGGREGATE = "phone_country_aggregate"


class ObservationStatus(str, Enum):
    POSSIBLE = "possible"
    INVALID = "invalid"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"
    INFORMATIONAL = "informational"


class ScoringSignalKind(str, Enum):
    PHONE_COUNTRY = "phone_country"


class Subject(str, Enum):
    PERSON = "person"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ComponentVersion:
    name: str
    version: str


class EvidencePage(Protocol):
    page_id: str
    page_number: int
    text: str


@dataclass(frozen=True)
class Evidence:
    page_id: str
    page_number: int
    start_offset: int
    end_offset: int
    excerpt: str

    @classmethod
    def from_page(
        cls,
        page: EvidencePage,
        start_offset: int,
        end_offset: int,
    ) -> Evidence:
        if (
            start_offset < 0
            or end_offset < start_offset
            or end_offset > len(page.text)
        ):
            raise ValueError("evidence offsets are outside the source page")
        return cls(
            page_id=page.page_id,
            page_number=page.page_number,
            start_offset=start_offset,
            end_offset=end_offset,
            excerpt=page.text[start_offset:end_offset],
        )


@dataclass(frozen=True)
class Provenance:
    authority: Authority
    evidence: tuple[Evidence, ...]
    extractor: ComponentVersion
    reference_data: ComponentVersion | None = None

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError("deterministic results require source evidence")


@dataclass(frozen=True)
class Candidate:
    id: CandidateId
    kind: CandidateKind
    value: str
    provenance: Provenance


@dataclass(frozen=True)
class Fact:
    id: FactId
    kind: FactKind
    value: str
    subject: Subject
    source_candidate_ids: tuple[CandidateId, ...]
    provenance: Provenance


@dataclass(frozen=True)
class Observation:
    id: ObservationId
    kind: ObservationKind
    status: ObservationStatus
    subject_ids: tuple[str, ...]
    values: tuple[str, ...]
    reason: str
    provenance: Provenance


@dataclass(frozen=True)
class ScoringSignal:
    id: ScoringSignalId
    kind: ScoringSignalKind
    value: str
    supporting_fact_ids: tuple[FactId, ...]
    rule_id: str
    ruleset_version: str
    provenance: Provenance


@dataclass(frozen=True)
class DeterministicAnalysisResult:
    candidates: tuple[Candidate, ...]
    facts: tuple[Fact, ...]
    observations: tuple[Observation, ...]
    scoring_signals: tuple[ScoringSignal, ...]

    def __post_init__(self) -> None:
        result_ids = [
            *(str(candidate.id) for candidate in self.candidates),
            *(str(fact.id) for fact in self.facts),
            *(str(observation.id) for observation in self.observations),
            *(str(signal.id) for signal in self.scoring_signals),
        ]
        if len(result_ids) != len(set(result_ids)):
            raise ValueError("deterministic result IDs must be unique")

        candidate_ids = {candidate.id for candidate in self.candidates}
        fact_ids = {fact.id for fact in self.facts}
        known_subject_ids = {str(value) for value in candidate_ids | fact_ids}
        for fact in self.facts:
            if (
                not fact.source_candidate_ids
                or not set(fact.source_candidate_ids) <= candidate_ids
            ):
                raise ValueError("fact references an unknown candidate")
        for observation in self.observations:
            if (
                not observation.subject_ids
                or not set(observation.subject_ids) <= known_subject_ids
            ):
                raise ValueError("observation references an unknown deterministic result")
        for signal in self.scoring_signals:
            if (
                not signal.supporting_fact_ids
                or not set(signal.supporting_fact_ids) <= fact_ids
            ):
                raise ValueError("scoring signal references an unknown fact")


class Band(str, Enum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"
    GRAY = "gray"


class AgreementDirection(str, Enum):
    SUPPORTS = "supports"
    CONFLICTS = "conflicts"
    NEUTRAL = "neutral"
    AMBIGUOUS = "ambiguous"
    INFORMATIONAL = "informational"


class SignalStrength(str, Enum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


@dataclass(frozen=True)
class RulesetVersion:
    version: str
    weights_path: str


@dataclass(frozen=True)
class Signal:
    name: str
    strength: SignalStrength
    observed: str
    inferred_country: str | None
    direction: AgreementDirection
    weight: float
    rationale: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Finding:
    signal: str
    strength: SignalStrength
    observed: str
    claimed: str | None
    direction: AgreementDirection
    weight: float
    rationale: str


@dataclass(frozen=True)
class ClaimedLocation:
    raw: str | None
    country_code: str | None
    region: str | None
    confidence: str  # "high", "low", "undetermined"


@dataclass(frozen=True)
class Report:
    score: int
    band: Band
    claimed_location: ClaimedLocation
    findings: tuple[Finding, ...]
    summary: str
    disclaimer: str
    ruleset_version: RulesetVersion
    signal_count: int
    supporting_count: int
    conflicting_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "band": self.band.value,
            "claimed_location": {
                "raw": self.claimed_location.raw,
                "country_code": self.claimed_location.country_code,
                "region": self.claimed_location.region,
                "confidence": self.claimed_location.confidence,
            },
            "findings": [
                {
                    "signal": f.signal,
                    "strength": f.strength.value,
                    "observed": f.observed,
                    "claimed": f.claimed,
                    "direction": f.direction.value,
                    "weight": f.weight,
                    "rationale": f.rationale,
                }
                for f in self.findings
            ],
            "summary": self.summary,
            "disclaimer": self.disclaimer,
            "ruleset_version": {
                "version": self.ruleset_version.version,
                "weights_path": self.ruleset_version.weights_path,
            },
            "signal_count": self.signal_count,
            "supporting_count": self.supporting_count,
            "conflicting_count": self.conflicting_count,
        }
