from __future__ import annotations

from dataclasses import dataclass
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
    RIGHT_TO_WORK = "right_to_work"
    EXPLICIT_LOCATION = "explicit_location"
    UNLABELED_LOCATION = "unlabeled_location"


class FactKind(str, Enum):
    PHONE_COUNTRY = "phone_country"
    CLAIMED_LOCATION = "claimed_location"


class ObservationKind(str, Enum):
    PHONE = "phone"
    PHONE_COUNTRY_AGGREGATE = "phone_country_aggregate"
    LOCATION = "location"
    UNLABELED_LOCATION = "unlabeled_location"
    LOCATION_CLAIM_AGGREGATE = "location_claim_aggregate"
    POSTAL_COMPATIBILITY = "postal_compatibility"
    RIGHT_TO_WORK = "right_to_work"
    NATIONAL_ID = "national_id"
    PHONE_OUTSIDE_EU = "phone_outside_eu"
    STATED_LOCATION_OUTSIDE_EU = "stated_location_outside_eu"
    COMBINED_LOCATION_OUTSIDE_EU = "combined_location_outside_eu"
    MIXED_EU_LOCATION_EVIDENCE = "mixed_eu_location_evidence"
    SMALL_LOCALITY_NOT_EVALUATED = "small_locality_not_evaluated"
    POSSIBLE_EMAIL_DOMAIN_TYPO = "possible_email_domain_typo"


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


class LocationRelation(str, Enum):
    PERSON = "person"
    EMPLOYER = "employer"
    CLIENT = "client"
    PROJECT = "project"
    OFFICE = "office"
    EDUCATION = "education"
    UNKNOWN = "unknown"


class SourceContext(str, Enum):
    DOCUMENT_START_BLOCK = "document_start_block"
    DOCUMENT_BODY = "document_body"


@dataclass(frozen=True)
class ComponentVersion:
    name: str
    version: str
    source_url: str | None = None


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
    subject: Subject = Subject.UNKNOWN
    relation: LocationRelation | None = None
    source_context: SourceContext | None = None
    label: str | None = None
    relation_evidence: tuple[Evidence, ...] = ()
    value_evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        if self.kind in {
            CandidateKind.EXPLICIT_LOCATION,
            CandidateKind.UNLABELED_LOCATION,
        } and self.relation is None:
            raise ValueError("location candidates require a relation")


@dataclass(frozen=True)
class Fact:
    id: FactId
    kind: FactKind
    value: str
    subject: Subject
    source_candidate_ids: tuple[CandidateId, ...]
    provenance: Provenance
    relation: LocationRelation | None = None
    source_context: SourceContext | None = None
    label: str | None = None
    relation_evidence: tuple[Evidence, ...] = ()
    value_evidence: tuple[Evidence, ...] = ()
    resolved_level: str | None = None
    resolved_name: str | None = None
    resolved_record_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind is FactKind.CLAIMED_LOCATION and self.relation is not LocationRelation.PERSON:
            raise ValueError("claimed-location facts require a person relation")


@dataclass(frozen=True)
class Observation:
    id: ObservationId
    kind: ObservationKind
    status: ObservationStatus
    subject_ids: tuple[str, ...]
    values: tuple[str, ...]
    reason: str
    provenance: Provenance
    relation: LocationRelation | None = None
    source_context: SourceContext | None = None
    label: str | None = None
    relation_evidence: tuple[Evidence, ...] = ()
    value_evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        if self.kind in {
            ObservationKind.LOCATION,
            ObservationKind.UNLABELED_LOCATION,
            ObservationKind.LOCATION_CLAIM_AGGREGATE,
        } and self.relation is None:
            raise ValueError("location observations require a relation")


@dataclass(frozen=True)
class ScoringSignal:
    id: ScoringSignalId
    kind: ScoringSignalKind
    value: str
    supporting_fact_ids: tuple[FactId, ...]
    rule_id: str
    ruleset_version: str
    provenance: Provenance
    relation: LocationRelation | None = None
    source_context: SourceContext | None = None
    label: str | None = None


@dataclass(frozen=True)
class DeterministicAnalysisResult:
    ruleset_version: str
    candidates: tuple[Candidate, ...]
    facts: tuple[Fact, ...]
    observations: tuple[Observation, ...]
    scoring_signals: tuple[ScoringSignal, ...]

    def __post_init__(self) -> None:
        if not self.ruleset_version.strip():
            raise ValueError("deterministic ruleset_version must not be empty")
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
            if fact.kind is FactKind.CLAIMED_LOCATION:
                from cv_validator.location_policy import (
                    claimed_location_graph_is_valid,
                )

                if not claimed_location_graph_is_valid(self.candidates, fact):
                    raise ValueError("invalid claimed-location graph")
        for observation in self.observations:
            if (
                not observation.subject_ids
                or not set(observation.subject_ids) <= known_subject_ids
            ):
                raise ValueError("observation references an unknown deterministic result")
        signal_categories = [
            (signal.kind, signal.rule_id) for signal in self.scoring_signals
        ]
        if len(signal_categories) != len(set(signal_categories)):
            raise ValueError("duplicate scoring category")
        reused_supporting_facts: set[FactId] = set()
        for signal in self.scoring_signals:
            if (
                not signal.supporting_fact_ids
                or not set(signal.supporting_fact_ids) <= fact_ids
            ):
                raise ValueError("scoring signal references an unknown fact")
            if set(signal.supporting_fact_ids) & reused_supporting_facts:
                raise ValueError("supporting facts cannot be reused across categories")
            reused_supporting_facts.update(signal.supporting_fact_ids)
            from cv_validator.phone_policy import phone_signal_graph_is_valid

            if not phone_signal_graph_is_valid(
                self.candidates,
                self.facts,
                signal,
                expected_ruleset_version=self.ruleset_version,
            ):
                raise ValueError("invalid phone scoring graph")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ruleset_version": self.ruleset_version,
            "candidates": [_candidate_to_dict(value) for value in self.candidates],
            "facts": [_fact_to_dict(value) for value in self.facts],
            "observations": [
                _observation_to_dict(value) for value in self.observations
            ],
            "scoring_signals": [
                _scoring_signal_to_dict(value) for value in self.scoring_signals
            ],
        }


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
    scoring_policy_version: str

    @property
    def audit_identity(self) -> str:
        return (
            f"weights:{self.version};policy:{self.scoring_policy_version}"
        )


@dataclass(frozen=True)
class Finding:
    signal: str
    strength: SignalStrength
    observed: str
    claimed: str | None
    direction: AgreementDirection
    weight: float
    rationale: str
    authority: Authority | None = None
    evidence: tuple[Evidence, ...] = ()
    extractor_version: ComponentVersion | None = None
    reference_data_version: ComponentVersion | None = None
    rule_id: str | None = None
    score_impact: str | None = None
    supporting_fact_ids: tuple[str, ...] = ()


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
    deterministic: DeterministicAnalysisResult | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
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
                    "authority": _enum_value(f.authority),
                    "evidence": _evidence_list(f.evidence),
                    "extractor_version": _component_version_to_dict(
                        f.extractor_version
                    ),
                    "reference_data_version": _component_version_to_dict(
                        f.reference_data_version
                    ),
                    "rule_id": f.rule_id,
                    "score_impact": f.score_impact,
                    "supporting_fact_ids": list(f.supporting_fact_ids),
                }
                for f in self.findings
            ],
            "summary": self.summary,
            "disclaimer": self.disclaimer,
            "ruleset_version": {
                "version": self.ruleset_version.version,
                "weights_path": self.ruleset_version.weights_path,
                "scoring_policy_version": (
                    self.ruleset_version.scoring_policy_version
                ),
            },
            "signal_count": self.signal_count,
            "supporting_count": self.supporting_count,
            "conflicting_count": self.conflicting_count,
        }
        if self.deterministic is not None:
            payload["deterministic"] = self.deterministic.to_dict()
        return payload


def _candidate_to_dict(candidate: Candidate) -> dict[str, Any]:
    return {
        "id": str(candidate.id),
        "kind": candidate.kind.value,
        "value": candidate.value,
        "subject": candidate.subject.value,
        **_provenance_to_dict(candidate.provenance),
        "relation": _enum_value(candidate.relation),
        "source_context": _enum_value(candidate.source_context),
        "label": candidate.label,
        "relation_evidence": _evidence_list(candidate.relation_evidence),
        "value_evidence": _evidence_list(candidate.value_evidence),
    }


def _fact_to_dict(fact: Fact) -> dict[str, Any]:
    return {
        "id": str(fact.id),
        "kind": fact.kind.value,
        "value": fact.value,
        "subject": fact.subject.value,
        "source_candidate_ids": [str(value) for value in fact.source_candidate_ids],
        **_provenance_to_dict(fact.provenance),
        "relation": _enum_value(fact.relation),
        "source_context": _enum_value(fact.source_context),
        "label": fact.label,
        "relation_evidence": _evidence_list(fact.relation_evidence),
        "value_evidence": _evidence_list(fact.value_evidence),
        "resolved_level": fact.resolved_level,
        "resolved_name": fact.resolved_name,
        "resolved_record_ids": list(fact.resolved_record_ids),
    }


def _observation_to_dict(observation: Observation) -> dict[str, Any]:
    return {
        "id": str(observation.id),
        "kind": observation.kind.value,
        "status": observation.status.value,
        "subject_ids": list(observation.subject_ids),
        "values": list(observation.values),
        "reason": observation.reason,
        **_provenance_to_dict(observation.provenance),
        "relation": _enum_value(observation.relation),
        "source_context": _enum_value(observation.source_context),
        "label": observation.label,
        "relation_evidence": _evidence_list(observation.relation_evidence),
        "value_evidence": _evidence_list(observation.value_evidence),
    }


def _scoring_signal_to_dict(signal: ScoringSignal) -> dict[str, Any]:
    return {
        "id": str(signal.id),
        "kind": signal.kind.value,
        "value": signal.value,
        "supporting_fact_ids": [str(value) for value in signal.supporting_fact_ids],
        "rule_id": signal.rule_id,
        "ruleset_version": signal.ruleset_version,
        **_provenance_to_dict(signal.provenance),
        "relation": _enum_value(signal.relation),
        "source_context": _enum_value(signal.source_context),
        "label": signal.label,
    }


def _provenance_to_dict(provenance: Provenance) -> dict[str, Any]:
    return {
        "authority": provenance.authority.value,
        "evidence": _evidence_list(provenance.evidence),
        "extractor_version": _component_version_to_dict(provenance.extractor),
        "reference_data_version": _component_version_to_dict(
            provenance.reference_data
        ),
    }


def _evidence_list(evidence: tuple[Evidence, ...]) -> list[dict[str, Any]]:
    return [
        {
            "page_id": value.page_id,
            "page_number": value.page_number,
            "start_offset": value.start_offset,
            "end_offset": value.end_offset,
            "excerpt": value.excerpt,
        }
        for value in evidence
    ]


def _component_version_to_dict(
    version: ComponentVersion | None,
) -> dict[str, str] | None:
    if version is None:
        return None
    value = {"name": version.name, "version": version.version}
    if version.source_url is not None:
        value["source_url"] = version.source_url
    return value


def _enum_value(value: Enum | None) -> str | None:
    return None if value is None else str(value.value)
