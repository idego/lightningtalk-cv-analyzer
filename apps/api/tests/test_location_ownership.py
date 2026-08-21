from cv_validator.domain import (
    CandidateKind,
    ComponentVersion,
    FactKind,
    LocationRelation,
    ObservationKind,
    ObservationStatus,
    SourceContext,
)
from cv_validator.extraction.deterministic import analyze_deterministically
from cv_validator.ingestion import RawDocument, SourcePage
from cv_validator.ingestion.redaction import redact_national_ids
from cv_validator.location import (
    InMemoryLocationResolver,
    LocationMatch,
    MatchKind,
    ResolutionLevel,
)


def _resolver() -> InMemoryLocationResolver:
    return InMemoryLocationResolver(
        records=(
            LocationMatch(
                record_id="place:munich",
                level=ResolutionLevel.LOCALITY,
                canonical_name="Munich",
                matched_name="Munich",
                match_kind=MatchKind.CANONICAL,
                country_code="DE",
                country_name="Germany",
            ),
            LocationMatch(
                record_id="place:berlin-de",
                level=ResolutionLevel.LOCALITY,
                canonical_name="Berlin",
                matched_name="Berlin",
                match_kind=MatchKind.CANONICAL,
                country_code="DE",
                country_name="Germany",
            ),
            LocationMatch(
                record_id="place:berlin-us",
                level=ResolutionLevel.LOCALITY,
                canonical_name="Berlin",
                matched_name="Berlin",
                match_kind=MatchKind.CANONICAL,
                country_code="US",
                country_name="United States",
            ),
            LocationMatch(
                record_id="place:paris-fr",
                level=ResolutionLevel.LOCALITY,
                canonical_name="Paris",
                matched_name="Paris",
                match_kind=MatchKind.CANONICAL,
                country_code="FR",
                country_name="France",
            ),
            LocationMatch(
                record_id="place:paris-us",
                level=ResolutionLevel.LOCALITY,
                canonical_name="Paris",
                matched_name="Paris",
                match_kind=MatchKind.CANONICAL,
                country_code="US",
                country_name="United States",
            ),
            LocationMatch(
                record_id="place:springfield-us-1",
                level=ResolutionLevel.LOCALITY,
                canonical_name="Springfield",
                matched_name="Springfield",
                match_kind=MatchKind.CANONICAL,
                country_code="US",
                country_name="United States",
            ),
            LocationMatch(
                record_id="place:springfield-us-2",
                level=ResolutionLevel.LOCALITY,
                canonical_name="Springfield",
                matched_name="Springfield",
                match_kind=MatchKind.CANONICAL,
                country_code="US",
                country_name="United States",
            ),
            LocationMatch(
                record_id="country:germany",
                level=ResolutionLevel.COUNTRY,
                canonical_name="Germany",
                matched_name="Germany",
                match_kind=MatchKind.CANONICAL,
                country_code="DE",
                country_name="Germany",
            ),
            LocationMatch(
                record_id="country:france",
                level=ResolutionLevel.COUNTRY,
                canonical_name="France",
                matched_name="France",
                match_kind=MatchKind.CANONICAL,
                country_code="FR",
                country_name="France",
            ),
            LocationMatch(
                record_id="country:united-states",
                level=ResolutionLevel.COUNTRY,
                canonical_name="United States",
                matched_name="United States",
                match_kind=MatchKind.CANONICAL,
                country_code="US",
                country_name="United States",
            ),
        ),
        reference_data_version=ComponentVersion("test-locations", "2026-08-21"),
    )


def _analyze(text: str, *, with_resolver: bool = True):
    document = redact_national_ids(
        RawDocument(
            pages=(SourcePage("page-0001", 1, text),),
            source_format="text",
        )
    )
    return analyze_deterministically(
        document,
        "1.0.0",
        location_resolver=_resolver() if with_resolver else None,
    )


def test_explicit_person_location_creates_fact_but_no_scoring_signal() -> None:
    result = _analyze(
        "Jane Example\nCurrent location: Munich\nSoftware engineer profile"
    )

    fact = next(fact for fact in result.facts if fact.kind is FactKind.CLAIMED_LOCATION)
    candidate = next(
        candidate
        for candidate in result.candidates
        if candidate.kind is CandidateKind.EXPLICIT_LOCATION
    )

    assert candidate.relation is LocationRelation.PERSON
    assert fact.relation is LocationRelation.PERSON
    assert fact.value == "DE"
    assert result.scoring_signals == ()
    assert fact.provenance.reference_data == ComponentVersion(
        "test-locations",
        "2026-08-21",
    )
    assert tuple(item.excerpt for item in fact.relation_evidence) == (
        "Current location: Munich",
    )
    assert tuple(item.excerpt for item in fact.value_evidence) == ("Munich",)
    assert fact.provenance.evidence == fact.relation_evidence
    assert candidate.label == "Current location"


def test_non_person_location_labels_remain_separate_non_scoring_observations() -> None:
    result = _analyze(
        "Jane Example\n"
        "Employer location: Munich\n"
        "Client location: Munich\n"
        "Project location: Munich\n"
        "Office location: Munich\n"
        "Education location: Munich\n"
        "Software engineer profile"
    )

    locations = tuple(
        observation
        for observation in result.observations
        if observation.kind is ObservationKind.LOCATION
    )
    assert {observation.relation for observation in locations} == {
        LocationRelation.EMPLOYER,
        LocationRelation.CLIENT,
        LocationRelation.PROJECT,
        LocationRelation.OFFICE,
        LocationRelation.EDUCATION,
    }
    assert all(observation.status is ObservationStatus.INFORMATIONAL for observation in locations)
    assert not any(fact.kind is FactKind.CLAIMED_LOCATION for fact in result.facts)
    assert result.scoring_signals == ()


def test_closed_polish_non_person_labels_preserve_ownership() -> None:
    result = _analyze(
        "Jan Przykład\n"
        "Lokalizacja pracodawcy: Munich\n"
        "Lokalizacja klienta: Munich\n"
        "Lokalizacja projektu: Munich\n"
        "Lokalizacja biura: Munich\n"
        "Lokalizacja uczelni: Munich\n"
        "Profil inżyniera oprogramowania"
    )

    relations = {
        observation.relation
        for observation in result.observations
        if observation.kind is ObservationKind.LOCATION
    }
    assert relations == {
        LocationRelation.EMPLOYER,
        LocationRelation.CLIENT,
        LocationRelation.PROJECT,
        LocationRelation.OFFICE,
        LocationRelation.EDUCATION,
    }


def test_explicit_person_country_resolves_after_locality_miss() -> None:
    result = _analyze(
        "Jane Example\nLocation: Germany\nSoftware engineer profile"
    )

    fact = next(fact for fact in result.facts if fact.kind is FactKind.CLAIMED_LOCATION)
    assert fact.value == "DE"
    assert fact.resolved_level == "country"


def test_ambiguous_explicit_person_location_is_non_scoring() -> None:
    result = _analyze("Jane Example\nAddress: Paris\nSoftware engineer profile")

    observation = next(
        observation
        for observation in result.observations
        if observation.kind is ObservationKind.LOCATION
    )
    assert observation.relation is LocationRelation.PERSON
    assert observation.status is ObservationStatus.AMBIGUOUS
    assert not any(fact.kind is FactKind.CLAIMED_LOCATION for fact in result.facts)
    assert result.scoring_signals == ()


def test_resolved_claim_is_not_invalidated_by_a_separate_ambiguous_claim() -> None:
    result = _analyze(
        "Jane Example\nLocation: Munich\nAddress: Paris\nSoftware engineer profile"
    )

    fact = next(fact for fact in result.facts if fact.kind is FactKind.CLAIMED_LOCATION)
    assert fact.value == "DE"
    ambiguous = next(
        observation
        for observation in result.observations
        if observation.kind is ObservationKind.LOCATION
        and observation.status is ObservationStatus.AMBIGUOUS
    )
    assert ambiguous.values == ("Paris",)
    assert not any(
        observation.kind is ObservationKind.LOCATION_CLAIM_AGGREGATE
        for observation in result.observations
    )


def test_missing_runtime_resolver_fails_closed_without_legacy_fallback() -> None:
    result = _analyze(
        "Jane Example\nLocation: Munich\nSoftware engineer profile",
        with_resolver=False,
    )

    observation = next(
        observation
        for observation in result.observations
        if observation.kind is ObservationKind.LOCATION
    )
    assert observation.status is ObservationStatus.UNRESOLVED
    assert "resolver" in observation.reason.casefold()
    assert not any(fact.kind is FactKind.CLAIMED_LOCATION for fact in result.facts)


def test_unlabeled_place_in_document_start_block_is_unknown_and_non_scoring() -> None:
    result = _analyze(
        "Jane Example\nMunich\n+49 30 123456\n\nExperience\nEngineer"
    )

    candidate = next(
        candidate
        for candidate in result.candidates
        if candidate.kind is CandidateKind.UNLABELED_LOCATION
    )
    observation = next(
        observation
        for observation in result.observations
        if observation.kind is ObservationKind.UNLABELED_LOCATION
    )
    assert candidate.relation is LocationRelation.UNKNOWN
    assert candidate.source_context is SourceContext.DOCUMENT_START_BLOCK
    assert candidate.provenance.evidence[0].excerpt == "Munich"
    assert observation.relation is LocationRelation.UNKNOWN
    assert observation.status is ObservationStatus.INFORMATIONAL
    assert not any(fact.kind is FactKind.CLAIMED_LOCATION for fact in result.facts)


def test_unlabeled_place_outside_start_block_remains_unknown_and_non_scoring() -> None:
    result = _analyze(
        "Jane Example\nSoftware engineer\n\nExperience\nMunich\nEngineer"
    )

    candidate = next(
        candidate
        for candidate in result.candidates
        if candidate.kind is CandidateKind.UNLABELED_LOCATION
    )
    assert candidate.relation is LocationRelation.UNKNOWN
    assert candidate.source_context is SourceContext.DOCUMENT_BODY
    assert not any(fact.kind is FactKind.CLAIMED_LOCATION for fact in result.facts)


def test_start_block_without_blank_line_remains_positional_unknown_context() -> None:
    result = _analyze("Jane Example\nSoftware engineer\nMunich")

    candidate = next(
        candidate
        for candidate in result.candidates
        if candidate.kind is CandidateKind.UNLABELED_LOCATION
    )
    assert candidate.source_context is SourceContext.DOCUMENT_START_BLOCK
    assert candidate.relation is LocationRelation.UNKNOWN


def test_based_in_requires_anchored_label_pattern_not_narrative_substring() -> None:
    result = _analyze(
        "Jane Example\nI delivered systems based in Munich for a client\n"
        "Software engineer profile"
    )

    assert not any(
        candidate.kind is CandidateKind.EXPLICIT_LOCATION
        for candidate in result.candidates
    )
    assert not any(fact.kind is FactKind.CLAIMED_LOCATION for fact in result.facts)


def test_full_address_that_does_not_exactly_resolve_remains_observation() -> None:
    result = _analyze(
        "Jane Example\nAddress: 12 Example Street, Munich\n"
        "Software engineer profile"
    )

    candidate = next(
        candidate
        for candidate in result.candidates
        if candidate.kind is CandidateKind.EXPLICIT_LOCATION
    )
    observation = next(
        observation
        for observation in result.observations
        if observation.kind is ObservationKind.LOCATION
    )
    assert candidate.label == "Address"
    assert candidate.relation is LocationRelation.PERSON
    assert observation.status is ObservationStatus.UNRESOLVED
    assert not any(fact.kind is FactKind.CLAIMED_LOCATION for fact in result.facts)


def test_generic_location_label_outside_start_block_is_unknown() -> None:
    result = _analyze(
        "Jane Example\nSoftware engineer\n\nExperience\nLocation: Munich"
    )

    candidate = next(
        candidate
        for candidate in result.candidates
        if candidate.kind is CandidateKind.EXPLICIT_LOCATION
    )
    observation = next(
        observation
        for observation in result.observations
        if observation.kind is ObservationKind.LOCATION
    )
    assert candidate.relation is LocationRelation.UNKNOWN
    assert candidate.source_context is SourceContext.DOCUMENT_BODY
    assert observation.relation is LocationRelation.UNKNOWN
    assert observation.status is ObservationStatus.INFORMATIONAL
    assert not any(fact.kind is FactKind.CLAIMED_LOCATION for fact in result.facts)


def test_person_specific_location_label_works_outside_start_block() -> None:
    result = _analyze(
        "Jane Example\nSoftware engineer\n\nProfile\nCurrent location: Munich"
    )

    fact = next(fact for fact in result.facts if fact.kind is FactKind.CLAIMED_LOCATION)
    assert fact.value == "DE"
    assert fact.source_context is SourceContext.DOCUMENT_BODY


def test_locality_country_expression_resolves_only_compatible_locality() -> None:
    result = _analyze(
        "Jane Example\nCurrent location: Berlin, Germany\nSoftware engineer"
    )

    fact = next(fact for fact in result.facts if fact.kind is FactKind.CLAIMED_LOCATION)
    assert fact.value == "DE"
    assert fact.resolved_level == "locality"
    assert fact.resolved_name == "Berlin"
    assert fact.resolved_record_ids == ("place:berlin-de",)


def test_locality_country_expression_rejects_country_conflict() -> None:
    result = _analyze(
        "Jane Example\nCurrent location: Berlin, France\nSoftware engineer"
    )

    observation = next(
        observation
        for observation in result.observations
        if observation.kind is ObservationKind.LOCATION
    )
    assert observation.status is ObservationStatus.AMBIGUOUS
    assert "conflict" in observation.reason.casefold()
    assert not any(fact.kind is FactKind.CLAIMED_LOCATION for fact in result.facts)


def test_same_country_ambiguous_locality_creates_country_level_fact() -> None:
    result = _analyze(
        "Jane Example\nCurrent location: Springfield\nSoftware engineer"
    )

    fact = next(fact for fact in result.facts if fact.kind is FactKind.CLAIMED_LOCATION)
    assert fact.value == "US"
    assert fact.resolved_level == "country"
    assert fact.resolved_record_ids == (
        "place:springfield-us-1",
        "place:springfield-us-2",
    )


def test_cross_country_ambiguous_locality_stays_observation() -> None:
    result = _analyze("Jane Example\nCurrent location: Paris\nSoftware engineer")

    observation = next(
        observation
        for observation in result.observations
        if observation.kind is ObservationKind.LOCATION
    )
    assert observation.status is ObservationStatus.AMBIGUOUS
    assert not any(fact.kind is FactKind.CLAIMED_LOCATION for fact in result.facts)


def test_repeated_identical_person_claims_merge_evidence_without_conflict() -> None:
    result = _analyze(
        "Current location: Munich\nJane Example\n\nProfile\nCurrent location: Munich"
    )

    facts = tuple(fact for fact in result.facts if fact.kind is FactKind.CLAIMED_LOCATION)
    assert len(facts) == 1
    fact = facts[0]
    assert len(fact.source_candidate_ids) == 2
    assert tuple(item.excerpt for item in fact.relation_evidence) == (
        "Current location: Munich",
        "Current location: Munich",
    )
    assert tuple(item.start_offset for item in fact.relation_evidence) == tuple(
        sorted(item.start_offset for item in fact.relation_evidence)
    )
    assert not any(
        observation.kind is ObservationKind.LOCATION_CLAIM_AGGREGATE
        for observation in result.observations
    )


def test_different_resolved_person_claims_create_conflict_without_fact() -> None:
    result = _analyze(
        "Current location: Munich\nJane Example\n\nProfile\nCurrent location: France"
    )

    assert not any(fact.kind is FactKind.CLAIMED_LOCATION for fact in result.facts)
    aggregate = next(
        observation
        for observation in result.observations
        if observation.kind is ObservationKind.LOCATION_CLAIM_AGGREGATE
    )
    assert aggregate.status is ObservationStatus.AMBIGUOUS
    assert "different" in aggregate.reason.casefold()


def test_more_than_two_location_components_are_not_token_guessed() -> None:
    result = _analyze(
        "Jane Example\nHome address: 12 Example Street, Berlin, Germany\n"
        "Software engineer"
    )

    observation = next(
        observation
        for observation in result.observations
        if observation.kind is ObservationKind.LOCATION
    )
    assert observation.status is ObservationStatus.UNRESOLVED
    assert not any(fact.kind is FactKind.CLAIMED_LOCATION for fact in result.facts)
