from cv_validator.config import load_weights
from dataclasses import replace

from cv_validator.domain import (
    AgreementDirection,
    ObservationKind,
    Subject,
)
from cv_validator.extraction.deterministic import analyze_deterministically
from cv_validator.extraction.eu_observations import (
    EU_27_ISO2,
    EU_MEMBER_STATES_SOURCE_URL,
    classify_eu_observations,
)
from cv_validator.ingestion import RawDocument, SourcePage
from cv_validator.ingestion.redaction import redact_national_ids
from cv_validator.location import (
    InMemoryLocationResolver,
    LocationMatch,
    MatchKind,
    ResolutionLevel,
)
from cv_validator.domain import ComponentVersion
from cv_validator.scoring.engine import score_deterministic


_CAVEAT = (
    "does not establish nationality, identity, physical presence, work "
    "eligibility, or fraud"
)


def test_eu_reference_set_is_versioned_official_eu_27_not_eea() -> None:
    assert len(EU_27_ISO2) == 27
    assert {"GB", "CH", "NO"}.isdisjoint(EU_27_ISO2)
    assert EU_MEMBER_STATES_SOURCE_URL == (
        "https://european-union.europa.eu/principles-countries-history/"
        "eu-countries_en"
    )


def _record(
    record_id: str,
    level: ResolutionLevel,
    name: str,
    country_code: str,
    country_name: str,
) -> LocationMatch:
    return LocationMatch(
        record_id=record_id,
        level=level,
        canonical_name=name,
        matched_name=name,
        match_kind=MatchKind.CANONICAL,
        country_code=country_code,
        country_name=country_name,
    )


def _resolver() -> InMemoryLocationResolver:
    records = []
    for code, country, locality in (
        ("DE", "Germany", "Berlin"),
        ("GB", "United Kingdom", "London"),
        ("CH", "Switzerland", "Zurich"),
        ("NO", "Norway", "Oslo"),
    ):
        records.extend(
            (
                _record(f"country:{code}", ResolutionLevel.COUNTRY, country, code, country),
                _record(f"locality:{code}", ResolutionLevel.LOCALITY, locality, code, country),
            )
        )
    return InMemoryLocationResolver(
        records=records,
        reference_data_version=ComponentVersion("test-locations", "v1"),
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


def _kinds(text: str, *, with_resolver: bool = True) -> set[ObservationKind]:
    return {value.kind for value in _analyze(text, with_resolver=with_resolver).observations}


def test_uk_switzerland_and_norway_are_non_eu_not_eea_or_europe() -> None:
    cases = (
        ("London, United Kingdom", "+44 20 7946 0958"),
        ("Zurich, Switzerland", "+41 44 668 18 00"),
        ("Oslo, Norway", "+47 22 33 44 55"),
    )
    for location, phone in cases:
        result = _analyze(
            f"Candidate\nCurrent location: {location}\nPhone: {phone}\n\nExperience"
        )
        kinds = {value.kind for value in result.observations}
        assert ObservationKind.STATED_LOCATION_OUTSIDE_EU in kinds
        assert ObservationKind.PHONE_OUTSIDE_EU in kinds
        assert ObservationKind.COMBINED_LOCATION_OUTSIDE_EU in kinds
        assert all(
            _CAVEAT in value.reason
            for value in result.observations
            if value.kind
            in {
                ObservationKind.STATED_LOCATION_OUTSIDE_EU,
                ObservationKind.PHONE_OUTSIDE_EU,
                ObservationKind.COMBINED_LOCATION_OUTSIDE_EU,
                ObservationKind.SMALL_LOCALITY_NOT_EVALUATED,
            }
        )


def test_eu_member_does_not_emit_outside_eu_observations() -> None:
    kinds = _kinds(
        "Candidate\nCurrent location: Berlin, Germany\nPhone: +49 30 123456\n\nExperience"
    )
    assert not kinds & {
        ObservationKind.STATED_LOCATION_OUTSIDE_EU,
        ObservationKind.PHONE_OUTSIDE_EU,
        ObservationKind.COMBINED_LOCATION_OUTSIDE_EU,
        ObservationKind.MIXED_EU_LOCATION_EVIDENCE,
    }


def test_one_non_eu_category_never_emits_combined() -> None:
    claim_only = _kinds(
        "Candidate\nCurrent location: London, United Kingdom\n\nExperience"
    )
    phone_only = _kinds("Candidate\nPhone: +44 20 7946 0958\n\nExperience")

    assert ObservationKind.STATED_LOCATION_OUTSIDE_EU in claim_only
    assert ObservationKind.PHONE_OUTSIDE_EU in phone_only
    assert ObservationKind.COMBINED_LOCATION_OUTSIDE_EU not in claim_only
    assert ObservationKind.COMBINED_LOCATION_OUTSIDE_EU not in phone_only


def test_two_distinct_non_eu_categories_emit_combined() -> None:
    kinds = _kinds(
        "Candidate\nCurrent location: London, United Kingdom\n"
        "Phone: +44 20 7946 0958\n\nExperience"
    )
    assert ObservationKind.COMBINED_LOCATION_OUTSIDE_EU in kinds
    assert ObservationKind.MIXED_EU_LOCATION_EVIDENCE not in kinds


def test_eu_and_non_eu_categories_emit_mixed_not_combined() -> None:
    kinds = _kinds(
        "Candidate\nCurrent location: Berlin, Germany\n"
        "Phone: +44 20 7946 0958\n\nExperience"
    )
    assert ObservationKind.MIXED_EU_LOCATION_EVIDENCE in kinds
    assert ObservationKind.COMBINED_LOCATION_OUTSIDE_EU not in kinds


def test_unresolved_or_ambiguous_category_cannot_support_combined() -> None:
    unresolved = _kinds(
        "Candidate\nCurrent location: London, United Kingdom\n"
        "Phone: +44 20 7946 0958\n\nExperience",
        with_resolver=False,
    )
    ambiguous_phone = _kinds(
        "Candidate\nCurrent location: London, United Kingdom\n"
        "Phone: +44 20 7946 0958\nPhone: +49 30 123456\n\nExperience"
    )
    assert ObservationKind.COMBINED_LOCATION_OUTSIDE_EU not in unresolved
    assert ObservationKind.COMBINED_LOCATION_OUTSIDE_EU not in ambiguous_phone
    assert ObservationKind.LOCATION in unresolved
    assert ObservationKind.PHONE_OUTSIDE_EU in unresolved
    assert ObservationKind.PHONE_COUNTRY_AGGREGATE in ambiguous_phone
    assert ObservationKind.STATED_LOCATION_OUTSIDE_EU in ambiguous_phone


def test_tampered_phone_fact_cannot_support_outside_eu_projection() -> None:
    deterministic = _analyze(
        "Candidate\nCurrent location: London, United Kingdom\n"
        "Phone: +44 20 7946 0958\n\nExperience"
    )
    phone_fact = next(
        fact for fact in deterministic.facts if fact.value == "GB" and fact.kind.value == "phone_country"
    )
    changed_facts = tuple(
        replace(fact, subject=Subject.UNKNOWN) if fact.id == phone_fact.id else fact
        for fact in deterministic.facts
    )

    observations = classify_eu_observations(
        deterministic.candidates,
        changed_facts,
        deterministic.scoring_signals,
        ruleset_version=deterministic.ruleset_version,
    )
    kinds = {observation.kind for observation in observations}

    assert ObservationKind.STATED_LOCATION_OUTSIDE_EU in kinds
    assert ObservationKind.PHONE_OUTSIDE_EU not in kinds
    assert ObservationKind.COMBINED_LOCATION_OUTSIDE_EU not in kinds


def test_resolved_non_eu_locality_is_explicitly_not_evaluated_for_size() -> None:
    result = _analyze("Candidate\nCurrent location: Oslo, Norway\n\nExperience")
    observation = next(
        value
        for value in result.observations
        if value.kind is ObservationKind.SMALL_LOCALITY_NOT_EVALUATED
    )
    assert "no calibrated rule" in observation.reason
    assert "small" not in observation.reason.lower()
    assert observation.provenance.reference_data == ComponentVersion(
        "eu-member-states",
        "eu27-2026-08-21",
        EU_MEMBER_STATES_SOURCE_URL,
    )


def test_outside_eu_observations_are_zero_weight_top_level_findings() -> None:
    deterministic = _analyze(
        "Candidate\nCurrent location: London, United Kingdom\n"
        "Phone: +44 20 7946 0958\n\nExperience"
    )
    report = score_deterministic(deterministic, load_weights())
    outside = {
        finding.signal: finding
        for finding in report.findings
        if finding.signal
        in {
            "stated_location_outside_eu",
            "phone_outside_eu",
            "combined_location_outside_eu",
            "small_locality_not_evaluated",
        }
    }
    assert set(outside) == {
        "stated_location_outside_eu",
        "phone_outside_eu",
        "combined_location_outside_eu",
        "small_locality_not_evaluated",
    }
    assert all(value.direction is AgreementDirection.INFORMATIONAL for value in outside.values())
    assert all(value.weight == 0 and value.score_impact == "none" for value in outside.values())
    assert all(_CAVEAT in value.rationale for value in outside.values())
    assert all(value.supporting_fact_ids for value in outside.values())
    assert all(value.evidence for value in outside.values())
    combined = outside["combined_location_outside_eu"]
    assert len(combined.supporting_fact_ids) == 2
    serialized = report.to_dict()
    serialized_combined = next(
        value
        for value in serialized["findings"]
        if value["signal"] == "combined_location_outside_eu"
    )
    assert serialized_combined["supporting_fact_ids"] == list(
        combined.supporting_fact_ids
    )
    assert serialized_combined["reference_data_version"] == {
        "name": "eu-member-states",
        "version": "eu27-2026-08-21",
        "source_url": EU_MEMBER_STATES_SOURCE_URL,
    }
