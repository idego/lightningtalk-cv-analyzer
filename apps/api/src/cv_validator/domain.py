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
    POSTAL_COUNTRY = "postal_country"
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
    COMBINED_LOCATION_INSIDE_EU = "combined_location_inside_eu"
    MIXED_EU_LOCATION_EVIDENCE = "mixed_eu_location_evidence"
    SMALL_LOCALITY_NOT_EVALUATED = "small_locality_not_evaluated"
    SMALL_LOCALITY_OUTSIDE_EU = "small_locality_outside_eu"
    POSSIBLE_EMAIL_DOMAIN_TYPO = "possible_email_domain_typo"


class ObservationStatus(str, Enum):
    POSSIBLE = "possible"
    INVALID = "invalid"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"
    INFORMATIONAL = "informational"


class ScoringSignalKind(str, Enum):
    PHONE_COUNTRY = "phone_country"
    POSTAL_COUNTRY = "postal_country"


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
    resolved_population: int | None = None

    def __post_init__(self) -> None:
        if self.kind is FactKind.CLAIMED_LOCATION and self.relation is not LocationRelation.PERSON:
            raise ValueError("claimed-location facts require a person relation")
        if self.resolved_population is not None and self.resolved_population < 0:
            raise ValueError("resolved_population must not be negative")


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
            if signal.kind is ScoringSignalKind.PHONE_COUNTRY:
                from cv_validator.phone_policy import phone_signal_graph_is_valid

                valid = phone_signal_graph_is_valid(
                    self.candidates,
                    self.facts,
                    signal,
                    expected_ruleset_version=self.ruleset_version,
                )
                invalid_message = "invalid phone scoring graph"
            elif signal.kind is ScoringSignalKind.POSTAL_COUNTRY:
                from cv_validator.postal_policy import postal_signal_graph_is_valid

                valid = postal_signal_graph_is_valid(
                    self.candidates,
                    self.facts,
                    signal,
                    expected_ruleset_version=self.ruleset_version,
                )
                invalid_message = "invalid postal scoring graph"
            else:
                valid = False
                invalid_message = "invalid deterministic scoring graph"
            if not valid:
                raise ValueError(invalid_message)

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


FILE_DETAILS_CONTRACT_VERSION = "file-details-v1"
LINK_INSPECTION_CONTRACT_VERSION = "link-inspection-v1"


class FileDetailField(str, Enum):
    AUTHOR = "author"
    CREATOR = "creator"
    PRODUCER = "producer"
    TITLE = "title"
    SUBJECT = "subject"
    CREATION_TIME = "creation_time"
    MODIFICATION_TIME = "modification_time"
    CREATED = "created"
    MODIFIED = "modified"
    LAST_MODIFIER = "last_modifier"
    REVISION = "revision"


class FileDetailStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class FileDetail:
    field: FileDetailField
    value: str | None
    status: FileDetailStatus
    source_format: str
    extractor_version: ComponentVersion

    def __post_init__(self) -> None:
        if not isinstance(self.field, FileDetailField):
            raise ValueError("file detail field is invalid")
        if not isinstance(self.status, FileDetailStatus):
            raise ValueError("file detail status is invalid")
        if not isinstance(self.source_format, str) or not self.source_format.strip():
            raise ValueError("file detail source_format must not be empty")
        if not isinstance(self.extractor_version, ComponentVersion):
            raise ValueError("file detail extractor_version is invalid")
        if self.value is not None and not isinstance(self.value, str):
            raise ValueError("file detail value must be a string or null")
        if self.status is FileDetailStatus.AVAILABLE and not self.value:
            raise ValueError("available file details require a value")
        if self.status is FileDetailStatus.UNAVAILABLE and self.value is not None:
            raise ValueError("unavailable file details must not have a value")
        if self.value is not None and len(self.value) > 1024:
            raise ValueError("file detail values are bounded to 1024 characters")

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field.value,
            "value": self.value,
            "status": self.status.value,
            "source_format": self.source_format,
            "extractor_version": _component_version_to_dict(self.extractor_version),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> FileDetail:
        if not isinstance(payload, dict):
            raise ValueError("file detail payload must be an object")
        version = payload.get("extractor_version")
        if not isinstance(version, dict):
            raise ValueError("file detail extractor_version is required")
        return cls(
            field=FileDetailField(payload["field"]),
            value=payload.get("value"),
            status=FileDetailStatus(payload["status"]),
            source_format=str(payload["source_format"]),
            extractor_version=_component_version_from_dict(version),
        )


@dataclass(frozen=True)
class FileDetails:
    source_format: str
    extractor_version: ComponentVersion
    fields: tuple[FileDetail, ...]
    contract_version: str = FILE_DETAILS_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.source_format, str) or not self.source_format.strip():
            raise ValueError("file details source_format must not be empty")
        if not isinstance(self.extractor_version, ComponentVersion):
            raise ValueError("file details extractor_version is invalid")
        if self.contract_version != FILE_DETAILS_CONTRACT_VERSION:
            raise ValueError("unsupported file details contract version")
        if any(not isinstance(field, FileDetail) for field in self.fields):
            raise ValueError("file details fields must contain file details")
        field_names = [field.field for field in self.fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError("file detail fields must be unique")

    @property
    def metadata(self) -> tuple[FileDetail, ...]:
        return self.fields

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "source_format": self.source_format,
            "extractor_version": _component_version_to_dict(self.extractor_version),
            "fields": {field.field.value: {
                "value": field.value,
                "status": field.status.value,
                "source_format": field.source_format,
                "extractor_version": _component_version_to_dict(
                    field.extractor_version
                ),
            } for field in self.fields},
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> FileDetails:
        if not isinstance(payload, dict):
            raise ValueError("file details payload must be an object")
        version = payload.get("extractor_version")
        fields = payload.get("fields")
        if not isinstance(version, dict) or not isinstance(fields, dict):
            raise ValueError("file details payload is incomplete")
        field_records = tuple(
            FileDetail.from_dict({
                "field": field_name,
                **field_payload,
            })
            for field_name, field_payload in fields.items()
            if isinstance(field_payload, dict)
        )
        if len(field_records) != len(fields):
            raise ValueError("file details fields must be objects")
        return cls(
            source_format=str(payload["source_format"]),
            extractor_version=_component_version_from_dict(version),
            fields=field_records,
            contract_version=str(payload.get("contract_version", "")),
        )


class LinkSource(str, Enum):
    VISIBLE_URL = "visible_url"
    EMBEDDED_HYPERLINK = "embedded_hyperlink"
    VISIBLE_AND_EMBEDDED = "visible_and_embedded"


class LinkAssociation(str, Enum):
    VISIBLE_ONLY = "visible_only"
    EMBEDDED_ONLY = "embedded_only"
    MATCHED = "matched"
    MISMATCHED = "mismatched"
    UNKNOWN = "unknown"


class LinkRole(str, Enum):
    PROFILE = "profile"
    PORTFOLIO = "portfolio"
    PROJECT = "project"
    PUBLICATION = "publication"
    CREDENTIAL = "credential"
    CV_CLAIM = "cv_claim"
    GENERIC = "generic"


class LinkOutcomeStatus(str, Enum):
    REACHABLE = "REACHABLE"
    SUSPICIOUS = "SUSPICIOUS"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_CHECKED = "NOT_CHECKED"


class LinkReasonCode(str, Enum):
    REACHABLE = "reachable"
    HYPERLINK_TARGET_MISMATCH = "hyperlink_target_mismatch"
    SERVICE_DOMAIN_LOOKALIKE = "service_domain_lookalike"
    UNSAFE_SCHEME = "unsafe_scheme"
    EMBEDDED_CREDENTIALS = "embedded_credentials"
    INVALID_HOST = "invalid_host"
    DISALLOWED_PORT = "disallowed_port"
    UNSAFE_DESTINATION = "unsafe_destination"
    UNSAFE_REDIRECT = "unsafe_redirect"
    UNRELATED_CROSS_DOMAIN_REDIRECT = "unrelated_cross_domain_redirect"
    DECLARED_LINK_NOT_FOUND = "declared_link_not_found"
    INVALID_LINK_TARGET = "invalid_link_target"
    INSPECTION_DISABLED = "inspection_disabled"
    DNS_FAILURE = "dns_failure"
    CONNECTION_FAILURE = "connection_failure"
    TIMEOUT = "timeout"
    TLS_FAILURE = "tls_failure"
    RESPONSE_LIMIT = "response_limit"
    REDIRECT_LIMIT = "redirect_limit"
    HTTP_FORBIDDEN = "http_forbidden"
    RATE_LIMITED = "rate_limited"
    ANTI_BOT = "anti_bot"
    REQUEST_BUDGET_EXCEEDED = "request_budget_exceeded"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    HTTP_STATUS_UNAVAILABLE = "http_status_unavailable"
    REDIRECT_WITHOUT_LOCATION = "redirect_without_location"


@dataclass(frozen=True)
class DocumentLink:
    id: str
    displayed_value: str | None
    target: str | None
    source_format: str
    source: LinkSource
    association: LinkAssociation
    role: LinkRole
    page_number: int | None
    evidence: tuple[Evidence, ...] = ()
    source_location: str = "body"
    invalid_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("document link id must not be empty")
        if not isinstance(self.source_format, str) or not self.source_format.strip():
            raise ValueError("document link source_format must not be empty")
        if not isinstance(self.source, LinkSource):
            raise ValueError("document link source is invalid")
        if not isinstance(self.association, LinkAssociation):
            raise ValueError("document link association is invalid")
        if not isinstance(self.role, LinkRole):
            raise ValueError("document link role is invalid")
        if not isinstance(self.source_location, str) or not self.source_location.strip():
            raise ValueError("document link source_location must not be empty")
        if any(
            value is not None and not isinstance(value, str)
            for value in (self.displayed_value, self.target, self.invalid_reason)
        ):
            raise ValueError("document link text values must be strings or null")
        if self.page_number is not None:
            if isinstance(self.page_number, bool) or not isinstance(self.page_number, int):
                raise ValueError("document link page_number must be an integer")
            if self.page_number < 1:
                raise ValueError("document link page_number must be positive")
        for value in (self.displayed_value, self.target, self.invalid_reason):
            if value is not None and len(value) > 4096:
                raise ValueError("document link values are bounded to 4096 characters")
        if self.target is None and not self.invalid_reason:
            raise ValueError("invalid document links require a reason")
        if any(not isinstance(evidence, Evidence) for evidence in self.evidence):
            raise ValueError("document link evidence must contain evidence records")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "displayed_value": self.displayed_value,
            "target": self.target,
            "source_format": self.source_format,
            "source": self.source.value,
            "association": self.association.value,
            "role": self.role.value,
            "page_number": self.page_number,
            "evidence": _evidence_list(self.evidence),
            "source_location": self.source_location,
            "invalid_reason": self.invalid_reason,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DocumentLink:
        if not isinstance(payload, dict):
            raise ValueError("document link payload must be an object")
        return cls(
            id=str(payload["id"]),
            displayed_value=payload.get("displayed_value"),
            target=payload.get("target"),
            source_format=str(payload["source_format"]),
            source=LinkSource(payload["source"]),
            association=LinkAssociation(payload["association"]),
            role=LinkRole(payload["role"]),
            page_number=payload.get("page_number"),
            evidence=tuple(_evidence_from_dict(item) for item in payload.get("evidence", [])),
            source_location=str(payload.get("source_location", "body")),
            invalid_reason=payload.get("invalid_reason"),
        )


@dataclass(frozen=True)
class LinkCheckResult:
    link_id: str
    status: LinkOutcomeStatus
    displayed_value: str | None
    sanitized_target: str | None
    source: LinkSource
    association: LinkAssociation
    role: LinkRole
    source_page: int | None
    source_evidence: tuple[Evidence, ...]
    reason_code: LinkReasonCode
    source_location: str = "body"
    terminal_status: int | None = None
    terminal_registrable_domain: str | None = None
    checked_at: str | None = None
    configuration_version: str = ""
    title: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.link_id, str) or not self.link_id.strip():
            raise ValueError("link check result link_id must not be empty")
        if not isinstance(self.status, LinkOutcomeStatus):
            raise ValueError("link check status is invalid")
        if not isinstance(self.source, LinkSource):
            raise ValueError("link check source is invalid")
        if not isinstance(self.association, LinkAssociation):
            raise ValueError("link check association is invalid")
        if not isinstance(self.role, LinkRole):
            raise ValueError("link check role is invalid")
        if not isinstance(self.reason_code, LinkReasonCode):
            raise ValueError("link check reason code is invalid")
        if any(
            value is not None and not isinstance(value, str)
            for value in (
                self.displayed_value,
                self.sanitized_target,
                self.source_location,
                self.terminal_registrable_domain,
                self.checked_at,
            )
        ):
            raise ValueError("link check text values must be strings or null")
        if not isinstance(self.configuration_version, str) or not isinstance(self.title, str):
            raise ValueError("link check metadata must be strings")
        if self.source_page is not None:
            if isinstance(self.source_page, bool) or not isinstance(self.source_page, int):
                raise ValueError("link check source_page must be an integer")
            if self.source_page < 1:
                raise ValueError("link check source_page must be positive")
        if self.terminal_status is not None:
            if isinstance(self.terminal_status, bool) or not isinstance(self.terminal_status, int):
                raise ValueError("terminal HTTP status must be an integer")
            if not 100 <= self.terminal_status <= 599:
                raise ValueError("terminal HTTP status must be between 100 and 599")
        if any(not isinstance(evidence, Evidence) for evidence in self.source_evidence):
            raise ValueError("link check source evidence must contain evidence records")
        if self.status is LinkOutcomeStatus.REACHABLE and self.reason_code is not LinkReasonCode.REACHABLE:
            raise ValueError("reachable links require the reachable reason code")
        if self.status is LinkOutcomeStatus.SUSPICIOUS and self.reason_code in {
            LinkReasonCode.DNS_FAILURE,
            LinkReasonCode.CONNECTION_FAILURE,
            LinkReasonCode.TIMEOUT,
            LinkReasonCode.TLS_FAILURE,
            LinkReasonCode.RESPONSE_LIMIT,
            LinkReasonCode.REDIRECT_LIMIT,
            LinkReasonCode.HTTP_FORBIDDEN,
            LinkReasonCode.RATE_LIMITED,
            LinkReasonCode.ANTI_BOT,
            LinkReasonCode.REQUEST_BUDGET_EXCEEDED,
            LinkReasonCode.HTTP_STATUS_UNAVAILABLE,
        }:
            raise ValueError("network-limited outcomes must be unavailable")

    def to_dict(self) -> dict[str, Any]:
        return {
            "link_id": self.link_id,
            "status": self.status.value,
            "displayed_value": self.displayed_value,
            "sanitized_target": self.sanitized_target,
            "source": self.source.value,
            "association": self.association.value,
            "role": self.role.value,
            "source_page": self.source_page,
            "source_evidence": _evidence_list(self.source_evidence),
            "source_location": self.source_location,
            "reason_code": self.reason_code.value,
            "terminal_status": self.terminal_status,
            "terminal_registrable_domain": self.terminal_registrable_domain,
            "checked_at": self.checked_at,
            "configuration_version": self.configuration_version,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LinkCheckResult:
        if not isinstance(payload, dict):
            raise ValueError("link check result payload must be an object")
        return cls(
            link_id=str(payload["link_id"]),
            status=LinkOutcomeStatus(payload["status"]),
            displayed_value=payload.get("displayed_value"),
            sanitized_target=payload.get("sanitized_target"),
            source=LinkSource(payload["source"]),
            association=LinkAssociation(payload["association"]),
            role=LinkRole(payload["role"]),
            source_page=payload.get("source_page"),
            source_evidence=tuple(
                _evidence_from_dict(item) for item in payload.get("source_evidence", [])
            ),
            reason_code=LinkReasonCode(payload["reason_code"]),
            source_location=str(payload.get("source_location", "body")),
            terminal_status=payload.get("terminal_status"),
            terminal_registrable_domain=payload.get("terminal_registrable_domain"),
            checked_at=payload.get("checked_at"),
            configuration_version=str(payload.get("configuration_version", "")),
            title=str(payload.get("title", "")),
        )


@dataclass(frozen=True)
class LinkInspection:
    links: tuple[LinkCheckResult, ...]
    checked_at: str
    configuration_version: str
    contract_version: str = LINK_INSPECTION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.checked_at, str) or not self.checked_at.strip():
            raise ValueError("link inspection checked_at must not be empty")
        if not isinstance(self.configuration_version, str) or not self.configuration_version.strip():
            raise ValueError("link inspection configuration_version must not be empty")
        if self.contract_version != LINK_INSPECTION_CONTRACT_VERSION:
            raise ValueError("unsupported link inspection contract version")
        if any(not isinstance(link, LinkCheckResult) for link in self.links):
            raise ValueError("link inspection links must contain check results")
        link_ids = [link.link_id for link in self.links]
        if len(link_ids) != len(set(link_ids)):
            raise ValueError("link inspection link IDs must be unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "checked_at": self.checked_at,
            "configuration_version": self.configuration_version,
            "links": [link.to_dict() for link in self.links],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LinkInspection:
        if not isinstance(payload, dict):
            raise ValueError("link inspection payload must be an object")
        links = payload.get("links", [])
        if not isinstance(links, list):
            raise ValueError("link inspection links must be a list")
        if any(not isinstance(item, dict) for item in links):
            raise ValueError("link inspection links must be objects")
        return cls(
            links=tuple(
                LinkCheckResult.from_dict(item)
                for item in links
            ),
            checked_at=str(payload["checked_at"]),
            configuration_version=str(payload["configuration_version"]),
            contract_version=str(payload.get("contract_version", "")),
        )


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
    file_details: FileDetails | None = None
    link_inspection: LinkInspection | None = None

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
        if self.file_details is not None:
            payload["file_details"] = self.file_details.to_dict()
        if self.link_inspection is not None:
            payload["link_inspection"] = self.link_inspection.to_dict()
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
        "resolved_population": fact.resolved_population,
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


def _component_version_from_dict(payload: dict[str, Any]) -> ComponentVersion:
    name = payload.get("name")
    version = payload.get("version")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("component version name must not be empty")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("component version version must not be empty")
    source_url = payload.get("source_url")
    if source_url is not None and not isinstance(source_url, str):
        raise ValueError("component version source_url must be a string")
    return ComponentVersion(name=name, version=version, source_url=source_url)


def _evidence_from_dict(payload: dict[str, Any]) -> Evidence:
    if not isinstance(payload, dict):
        raise ValueError("evidence must be an object")
    return Evidence(
        page_id=str(payload["page_id"]),
        page_number=int(payload["page_number"]),
        start_offset=int(payload["start_offset"]),
        end_offset=int(payload["end_offset"]),
        excerpt=str(payload["excerpt"]),
    )


def _enum_value(value: Enum | None) -> str | None:
    return None if value is None else str(value.value)
