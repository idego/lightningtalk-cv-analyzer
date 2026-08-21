from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

from cv_validator.domain import (
    Authority,
    Candidate,
    CandidateId,
    CandidateKind,
    ComponentVersion,
    Evidence,
    Fact,
    FactId,
    FactKind,
    LocationRelation,
    Observation,
    ObservationId,
    ObservationKind,
    ObservationStatus,
    Provenance,
    ScoringSignal,
    Subject,
)
from cv_validator.extraction.candidates import source_context_for_offset
from cv_validator.ingestion import RedactedDocument, SourcePage
from cv_validator.location import (
    Ambiguous,
    LocationResolver,
    ResolutionLevel,
    Resolved,
    ScopeResolution,
    Unresolved,
)


LOCATION_CLASSIFIER_VERSION = "1"


@dataclass(frozen=True)
class _ResolutionAttempt:
    scope: ScopeResolution | None
    status: ObservationStatus
    detail: str
    reference_data: ComponentVersion | None


def classify_locations(
    document: RedactedDocument,
    candidates: tuple[Candidate, ...],
    ruleset_version: str,
    resolver: LocationResolver | None,
) -> tuple[
    tuple[Candidate, ...],
    tuple[Fact, ...],
    tuple[Observation, ...],
    tuple[ScoringSignal, ...],
]:
    del ruleset_version  # Claimed location is a baseline fact, not a scoring vote.
    explicit = tuple(
        candidate
        for candidate in candidates
        if candidate.kind is CandidateKind.EXPLICIT_LOCATION
    )
    unlabeled_candidates, unlabeled_observations = _unlabeled_locations(
        document,
        explicit,
        resolver,
    )
    observations = list(unlabeled_observations)

    person_candidates = tuple(
        candidate
        for candidate in explicit
        if candidate.relation is LocationRelation.PERSON
    )
    related_candidates = tuple(
        candidate
        for candidate in explicit
        if candidate.relation is not LocationRelation.PERSON
    )
    for candidate in related_candidates:
        attempt = _resolve_claim_value(candidate.value, resolver)
        observations.append(
            _location_observation(
                candidate,
                attempt,
                informational_if_resolved=True,
                reason_prefix=(
                    f"Explicit {candidate.relation.value} relation is retained "
                    "separately and excluded from the candidate location claim"
                ),
            )
        )

    resolved_groups: dict[tuple[object, ...], list[Candidate]] = {}
    resolved_attempts: dict[tuple[object, ...], _ResolutionAttempt] = {}
    candidate_attempts: dict[CandidateId, _ResolutionAttempt] = {}
    for candidate in person_candidates:
        attempt = _resolve_claim_value(candidate.value, resolver)
        candidate_attempts[candidate.id] = attempt
        if attempt.scope is None:
            observations.append(_location_observation(candidate, attempt))
            continue
        key = _scope_key(attempt.scope)
        resolved_groups.setdefault(key, []).append(candidate)
        resolved_attempts[key] = attempt

    facts: tuple[Fact, ...] = ()
    if len(resolved_groups) == 1:
        key, grouped_candidates = next(iter(resolved_groups.items()))
        facts = (
            _claimed_location_fact(
                tuple(grouped_candidates),
                resolved_attempts[key],
            ),
        )
    elif len(resolved_groups) > 1:
        conflicting_candidates = tuple(
            candidate
            for grouped_candidates in resolved_groups.values()
            for candidate in grouped_candidates
        )
        for candidate in conflicting_candidates:
            observations.append(
                _location_observation(
                    candidate,
                    candidate_attempts[candidate.id],
                    force_status=ObservationStatus.AMBIGUOUS,
                    reason_prefix=(
                        "Explicit person-location descriptions resolve to "
                        "different scopes"
                    ),
                )
            )
        observations.append(_aggregate_conflicting_claim(conflicting_candidates))

    return unlabeled_candidates, facts, tuple(observations), ()


def _unlabeled_locations(
    document: RedactedDocument,
    explicit: tuple[Candidate, ...],
    resolver: LocationResolver | None,
) -> tuple[tuple[Candidate, ...], tuple[Observation, ...]]:
    if resolver is None:
        return (), ()
    explicit_spans = {
        (evidence.page_id, evidence.start_offset, evidence.end_offset)
        for candidate in explicit
        for evidence in candidate.provenance.evidence
    }
    candidates: list[Candidate] = []
    observations: list[Observation] = []
    for page in document.pages:
        for start, end, value in _whole_lines(page):
            if not value or (page.page_id, start, end) in explicit_spans:
                continue
            attempt = _resolve_claim_value(value, resolver)
            if attempt.scope is None:
                continue
            evidence = Evidence.from_page(page, start, end)
            candidate = Candidate(
                id=CandidateId(
                    f"candidate:unlabeled_location:{page.page_id}:{start}:{end}"
                ),
                kind=CandidateKind.UNLABELED_LOCATION,
                value=value,
                provenance=Provenance(
                    authority=Authority.CODE,
                    evidence=(evidence,),
                    extractor=_extractor_version(),
                    reference_data=attempt.reference_data,
                ),
                relation=LocationRelation.UNKNOWN,
                source_context=source_context_for_offset(page, start),
                relation_evidence=(evidence,),
                value_evidence=(evidence,),
            )
            candidates.append(candidate)
            observations.append(
                _location_observation(
                    candidate,
                    attempt,
                    informational_if_resolved=True,
                    observation_kind=ObservationKind.UNLABELED_LOCATION,
                    reason_prefix=(
                        "Whole-line place match has no explicit ownership relation "
                        "and is non-scoring"
                    ),
                )
            )
    return tuple(candidates), tuple(observations)


def _whole_lines(page: SourcePage) -> tuple[tuple[int, int, str], ...]:
    lines: list[tuple[int, int, str]] = []
    cursor = 0
    for raw_line in page.text.splitlines(keepends=True):
        without_newline = raw_line.rstrip("\r\n")
        leading = len(without_newline) - len(without_newline.lstrip())
        value = without_newline.strip()
        start = cursor + leading
        lines.append((start, start + len(value), value))
        cursor += len(raw_line)
    if cursor < len(page.text):
        value = page.text[cursor:].strip()
        leading = len(page.text[cursor:]) - len(page.text[cursor:].lstrip())
        start = cursor + leading
        lines.append((start, start + len(value), value))
    return tuple(lines)


def _resolve_claim_value(
    value: str,
    resolver: LocationResolver | None,
) -> _ResolutionAttempt:
    if resolver is None:
        return _ResolutionAttempt(
            None,
            ObservationStatus.UNRESOLVED,
            "No LocationResolver is configured",
            None,
        )

    components = value.split(",")
    if len(components) > 2 or any(not component.strip() for component in components):
        return _ResolutionAttempt(
            None,
            ObservationStatus.UNRESOLVED,
            (
                "Location expression is outside the supported country-only or "
                "Locality, Country grammar"
            ),
            None,
        )
    if len(components) == 2:
        return _resolve_locality_country(
            components[0].strip(), components[1].strip(), resolver
        )

    locality = resolver.resolve(value, level=ResolutionLevel.LOCALITY)
    if isinstance(locality, Resolved):
        return _resolved_attempt(locality.resolution, locality.reference_data_version)
    if isinstance(locality, Ambiguous):
        if locality.common_resolution is not None:
            return _resolved_attempt(
                locality.common_resolution,
                locality.reference_data_version,
                detail="Ambiguous localities share one common country resolution",
            )
        return _ambiguous_attempt(
            "Location text maps to localities in different countries",
            locality.reference_data_version,
        )

    country = resolver.resolve(value, level=ResolutionLevel.COUNTRY)
    if isinstance(country, Resolved):
        return _resolved_attempt(country.resolution, country.reference_data_version)
    if isinstance(country, Ambiguous) and country.common_resolution is not None:
        return _resolved_attempt(
            country.common_resolution,
            country.reference_data_version,
            detail="Country aliases share one common country resolution",
        )
    return _ResolutionAttempt(
        None,
        (
            ObservationStatus.AMBIGUOUS
            if isinstance(country, Ambiguous)
            else ObservationStatus.UNRESOLVED
        ),
        (
            "Location text maps to more than one country interpretation"
            if isinstance(country, Ambiguous)
            else "Location text is absent from the bounded offline index"
        ),
        country.reference_data_version,
    )


def _resolve_locality_country(
    locality_value: str,
    country_value: str,
    resolver: LocationResolver,
) -> _ResolutionAttempt:
    country = resolver.resolve(country_value, level=ResolutionLevel.COUNTRY)
    if not isinstance(country, Resolved):
        return _ResolutionAttempt(
            None,
            (
                ObservationStatus.AMBIGUOUS
                if isinstance(country, Ambiguous)
                else ObservationStatus.UNRESOLVED
            ),
            "Country component does not resolve uniquely",
            country.reference_data_version,
        )

    locality = resolver.resolve(locality_value, level=ResolutionLevel.LOCALITY)
    country_code = country.resolution.country_code
    if isinstance(locality, Resolved):
        if locality.resolution.country_code != country_code:
            return _ambiguous_attempt(
                "Locality and country components conflict",
                locality.reference_data_version,
            )
        return _resolved_attempt(locality.resolution, locality.reference_data_version)
    if isinstance(locality, Unresolved):
        return _ResolutionAttempt(
            None,
            ObservationStatus.UNRESOLVED,
            "Locality component is absent from the bounded offline index",
            locality.reference_data_version,
        )

    compatible = tuple(
        match for match in locality.matches if match.country_code == country_code
    )
    if len(compatible) == 1:
        match = compatible[0]
        return _resolved_attempt(
            ScopeResolution(
                level=ResolutionLevel.LOCALITY,
                canonical_name=match.canonical_name,
                country_code=match.country_code,
                region_code=match.region_code,
                supporting_record_ids=(match.record_id,),
            ),
            locality.reference_data_version,
        )
    if len(compatible) > 1:
        return _resolved_attempt(
            ScopeResolution(
                level=ResolutionLevel.COUNTRY,
                canonical_name=country.resolution.canonical_name,
                country_code=country_code,
                supporting_record_ids=tuple(
                    sorted(match.record_id for match in compatible)
                ),
            ),
            locality.reference_data_version,
            detail="Ambiguous localities share the explicit country resolution",
        )
    return _ambiguous_attempt(
        "Locality and country components conflict",
        locality.reference_data_version,
    )


def _resolved_attempt(
    scope: ScopeResolution,
    reference_data: ComponentVersion,
    *,
    detail: str | None = None,
) -> _ResolutionAttempt:
    return _ResolutionAttempt(
        scope,
        ObservationStatus.INFORMATIONAL,
        detail or f"Resolved to country {scope.country_code}",
        reference_data,
    )


def _ambiguous_attempt(
    detail: str,
    reference_data: ComponentVersion,
) -> _ResolutionAttempt:
    return _ResolutionAttempt(
        None, ObservationStatus.AMBIGUOUS, detail, reference_data
    )


def _claimed_location_fact(
    candidates: tuple[Candidate, ...],
    attempt: _ResolutionAttempt,
) -> Fact:
    if attempt.scope is None:
        raise ValueError("claimed-location fact requires a resolved scope")
    ordered = tuple(sorted(candidates, key=_candidate_sort_key))
    relation_evidence = _merged_evidence(
        evidence
        for candidate in ordered
        for evidence in _relation_evidence(candidate)
    )
    value_evidence = _merged_evidence(
        evidence
        for candidate in ordered
        for evidence in _value_evidence(candidate)
    )
    labels = {candidate.label for candidate in ordered}
    contexts = {candidate.source_context for candidate in ordered}
    return Fact(
        id=FactId(
            "fact:claimed_location:"
            f"{attempt.scope.country_code.casefold()}:"
            f"{attempt.scope.level.value}:{ordered[0].id}"
        ),
        kind=FactKind.CLAIMED_LOCATION,
        value=attempt.scope.country_code,
        subject=Subject.PERSON,
        source_candidate_ids=tuple(candidate.id for candidate in ordered),
        provenance=Provenance(
            authority=Authority.CODE,
            evidence=relation_evidence,
            extractor=_extractor_version(),
            reference_data=attempt.reference_data,
        ),
        relation=LocationRelation.PERSON,
        source_context=next(iter(contexts)) if len(contexts) == 1 else None,
        label=next(iter(labels)) if len(labels) == 1 else None,
        relation_evidence=relation_evidence,
        value_evidence=value_evidence,
        resolved_level=attempt.scope.level.value,
        resolved_name=attempt.scope.canonical_name,
        resolved_record_ids=attempt.scope.supporting_record_ids,
    )


def _location_observation(
    candidate: Candidate,
    attempt: _ResolutionAttempt,
    *,
    informational_if_resolved: bool = False,
    force_status: ObservationStatus | None = None,
    observation_kind: ObservationKind = ObservationKind.LOCATION,
    reason_prefix: str | None = None,
) -> Observation:
    status = attempt.status
    if attempt.scope is not None and not informational_if_resolved:
        status = ObservationStatus.UNRESOLVED
    if force_status is not None:
        status = force_status
    reason = f"{reason_prefix}; {attempt.detail}" if reason_prefix else attempt.detail
    values = (candidate.value,)
    if attempt.scope is not None:
        values = (*values, attempt.scope.country_code)
    relation_evidence = _relation_evidence(candidate)
    value_evidence = _value_evidence(candidate)
    return Observation(
        id=ObservationId(f"observation:{observation_kind.value}:{candidate.id}"),
        kind=observation_kind,
        status=status,
        subject_ids=(str(candidate.id),),
        values=values,
        reason=reason,
        provenance=Provenance(
            authority=Authority.CODE,
            evidence=relation_evidence,
            extractor=_extractor_version(),
            reference_data=attempt.reference_data,
        ),
        relation=candidate.relation,
        source_context=candidate.source_context,
        label=candidate.label,
        relation_evidence=relation_evidence,
        value_evidence=value_evidence,
    )


def _aggregate_conflicting_claim(candidates: tuple[Candidate, ...]) -> Observation:
    ordered = tuple(sorted(candidates, key=_candidate_sort_key))
    relation_evidence = _merged_evidence(
        evidence
        for candidate in ordered
        for evidence in _relation_evidence(candidate)
    )
    value_evidence = _merged_evidence(
        evidence
        for candidate in ordered
        for evidence in _value_evidence(candidate)
    )
    return Observation(
        id=ObservationId("observation:location_claim:aggregate"),
        kind=ObservationKind.LOCATION_CLAIM_AGGREGATE,
        status=ObservationStatus.AMBIGUOUS,
        subject_ids=tuple(str(candidate.id) for candidate in ordered),
        values=tuple(candidate.value for candidate in ordered),
        reason=(
            "Explicit person-location descriptions resolve to different scopes; "
            "the scoring claim is undetermined"
        ),
        provenance=Provenance(
            authority=Authority.CODE,
            evidence=relation_evidence,
            extractor=_extractor_version(),
        ),
        relation=LocationRelation.PERSON,
        relation_evidence=relation_evidence,
        value_evidence=value_evidence,
    )


def _relation_evidence(candidate: Candidate) -> tuple[Evidence, ...]:
    return candidate.relation_evidence or candidate.provenance.evidence


def _value_evidence(candidate: Candidate) -> tuple[Evidence, ...]:
    return candidate.value_evidence or candidate.provenance.evidence


def _merged_evidence(evidence: Iterable[Evidence]) -> tuple[Evidence, ...]:
    unique = {
        (
            item.page_id,
            item.page_number,
            item.start_offset,
            item.end_offset,
            item.excerpt,
        ): item
        for item in evidence
    }
    return tuple(sorted(unique.values(), key=_evidence_sort_key))


def _candidate_sort_key(candidate: Candidate) -> tuple[object, ...]:
    evidence = _relation_evidence(candidate)[0]
    return (
        evidence.page_number,
        evidence.start_offset,
        evidence.end_offset,
        str(candidate.id),
    )


def _evidence_sort_key(evidence: Evidence) -> tuple[object, ...]:
    return (
        evidence.page_number,
        evidence.start_offset,
        evidence.end_offset,
        evidence.excerpt,
    )


def _scope_key(scope: ScopeResolution) -> tuple[object, ...]:
    return (
        scope.country_code,
        scope.level.value,
        scope.canonical_name.casefold(),
        scope.region_code or "",
        scope.supporting_record_ids,
    )


def _extractor_version() -> ComponentVersion:
    return ComponentVersion("location-ownership", LOCATION_CLASSIFIER_VERSION)
