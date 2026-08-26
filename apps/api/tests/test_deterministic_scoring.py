from dataclasses import replace

import pytest

from cv_validator.config import load_weights
from cv_validator.domain import (
    AgreementDirection,
    Authority,
    Band,
    ComponentVersion,
    FactKind,
    ObservationKind,
    ScoringSignalKind,
    Subject,
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
from cv_validator.scoring.engine import score_deterministic


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
                record_id="country:germany",
                level=ResolutionLevel.COUNTRY,
                canonical_name="Germany",
                matched_name="Germany",
                match_kind=MatchKind.CANONICAL,
                country_code="DE",
                country_name="Germany",
            ),
            LocationMatch(
                record_id="place:opole",
                level=ResolutionLevel.LOCALITY,
                canonical_name="Opole",
                matched_name="Opole",
                match_kind=MatchKind.CANONICAL,
                country_code="PL",
                country_name="Poland",
            ),
            LocationMatch(
                record_id="country:poland",
                level=ResolutionLevel.COUNTRY,
                canonical_name="Poland",
                matched_name="Poland",
                match_kind=MatchKind.CANONICAL,
                country_code="PL",
                country_name="Poland",
            ),
        ),
        reference_data_version=ComponentVersion("test-locations", "v1"),
    )


def _deterministic(text: str, ruleset_version: str = "1.0.0"):
    raw = RawDocument(
        pages=(SourcePage("page-0001", 1, text),),
        source_format="text",
    )
    return analyze_deterministically(
        redact_national_ids(raw),
        ruleset_version,
        location_resolver=_resolver(),
    )


def _unsafe_with_signal(deterministic, signal):
    changed = object.__new__(type(deterministic))
    object.__setattr__(changed, "candidates", deterministic.candidates)
    object.__setattr__(changed, "facts", deterministic.facts)
    object.__setattr__(changed, "observations", deterministic.observations)
    object.__setattr__(changed, "ruleset_version", deterministic.ruleset_version)
    object.__setattr__(changed, "scoring_signals", (signal,))
    return changed


def _unsafe_with_facts(deterministic, facts):
    changed = object.__new__(type(deterministic))
    object.__setattr__(changed, "candidates", deterministic.candidates)
    object.__setattr__(changed, "facts", facts)
    object.__setattr__(changed, "observations", deterministic.observations)
    object.__setattr__(changed, "ruleset_version", deterministic.ruleset_version)
    object.__setattr__(changed, "scoring_signals", deterministic.scoring_signals)
    return changed


def test_one_agreeing_phone_category_is_gray_for_insufficient_independent_evidence() -> None:
    deterministic = _deterministic(
        "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456\nEngineer"
    )

    report = score_deterministic(deterministic, load_weights())

    assert report.deterministic is deterministic
    assert report.band is Band.GRAY
    assert report.score == 50
    assert report.signal_count == 1
    assert report.supporting_count == 1
    assert report.conflicting_count == 0
    assert "insufficient independent deterministic evidence" in report.summary
    phone = next(finding for finding in report.findings if finding.signal == "phone_country")
    assert phone.direction is AgreementDirection.SUPPORTS
    assert phone.weight == 35
    assert phone.authority is Authority.CODE
    assert phone.rule_id == "phone-country-all-person-owned-agree:v1"
    assert phone.score_impact == "weighted"


def test_phone_and_person_postal_country_support_claim_with_configured_weights() -> None:
    deterministic = _deterministic(
        "Jane Example\n"
        "jane@example.com +48 732080047 Opole, Poland 45-061\n"
        "Software engineer"
    )

    report = score_deterministic(deterministic, load_weights())

    assert {
        fact.kind for fact in deterministic.facts
    } >= {FactKind.PHONE_COUNTRY, FactKind.POSTAL_COUNTRY, FactKind.CLAIMED_LOCATION}
    assert {
        signal.kind for signal in deterministic.scoring_signals
    } == {ScoringSignalKind.PHONE_COUNTRY, ScoringSignalKind.POSTAL_COUNTRY}
    assert report.score == 100
    assert report.band is Band.GREEN
    assert report.signal_count == 2
    assert report.supporting_count == 2
    assert report.conflicting_count == 0
    postal = next(
        finding for finding in report.findings if finding.signal == "address_postal"
    )
    assert postal.direction is AgreementDirection.SUPPORTS
    assert postal.weight == load_weights().signals["address_postal"].weight
    assert postal.score_impact == "weighted"
    assert report.ruleset_version.scoring_policy_version == (
        "deterministic-phone-postal-comparison-v2"
    )


def test_person_postal_conflict_uses_configured_weight_without_hardcoded_score() -> None:
    deterministic = _deterministic(
        "Jane Example\n"
        "jane@example.com +49 30 123456 Munich, Germany 45-061\n"
        "Software engineer"
    )

    report = score_deterministic(deterministic, load_weights())

    assert report.score == 54
    assert report.band is Band.AMBER
    assert report.signal_count == 2
    assert report.supporting_count == 1
    assert report.conflicting_count == 1
    postal = next(
        finding for finding in report.findings if finding.signal == "address_postal"
    )
    assert postal.observed == "PL"
    assert postal.claimed == "Munich, Germany"
    assert postal.direction is AgreementDirection.CONFLICTS


def test_shared_postal_format_abstains_and_keeps_report_gray() -> None:
    deterministic = _deterministic(
        "Jane Example\n"
        "jane@example.com +49 30 123456 Munich, Germany 10115\n"
        "Software engineer"
    )

    report = score_deterministic(deterministic, load_weights())

    assert not any(
        fact.kind is FactKind.POSTAL_COUNTRY for fact in deterministic.facts
    )
    assert not any(
        signal.kind is ScoringSignalKind.POSTAL_COUNTRY
        for signal in deterministic.scoring_signals
    )
    postal = next(
        observation
        for observation in deterministic.observations
        if observation.kind is ObservationKind.POSTAL_COMPATIBILITY
    )
    assert postal.values == ("DE", "FR", "US")
    assert report.score == 50
    assert report.band is Band.GRAY
    assert report.signal_count == 1


def test_postal_code_outside_person_contact_line_does_not_enter_scoring() -> None:
    deterministic = _deterministic(
        "Jane Example\n"
        "Current location: Munich\n"
        "Phone: +49 30 123456\n"
        "Employer address: Warsaw 45-061\n"
        "Software engineer"
    )

    report = score_deterministic(deterministic, load_weights())

    assert not any(
        fact.kind is FactKind.POSTAL_COUNTRY for fact in deterministic.facts
    )
    assert not any(
        signal.kind is ScoringSignalKind.POSTAL_COUNTRY
        for signal in deterministic.scoring_signals
    )
    assert report.score == 50
    assert report.band is Band.GRAY
    assert report.signal_count == 1


def test_postal_country_graph_rejects_tampered_country() -> None:
    deterministic = _deterministic(
        "Jane Example\n"
        "jane@example.com +48 732080047 Opole, Poland 45-061\n"
        "Software engineer"
    )
    postal = next(
        signal
        for signal in deterministic.scoring_signals
        if signal.kind is ScoringSignalKind.POSTAL_COUNTRY
    )

    with pytest.raises(ValueError, match="invalid postal scoring graph"):
        replace(
            deterministic,
            scoring_signals=tuple(
                replace(signal, value="US") if signal.id == postal.id else signal
                for signal in deterministic.scoring_signals
            ),
        )


def test_one_conflicting_phone_category_is_still_gray_not_a_negative_verdict() -> None:
    deterministic = _deterministic(
        "Jane Example\nCurrent location: Munich\nPhone: +1 415 555 0100\nEngineer"
    )

    report = score_deterministic(deterministic, load_weights())

    assert report.band is Band.GRAY
    assert report.score == 50
    assert report.signal_count == 1
    assert report.supporting_count == 0
    assert report.conflicting_count == 1
    assert "not a negative result" in report.summary
    phone = next(finding for finding in report.findings if finding.signal == "phone_country")
    assert phone.direction is AgreementDirection.CONFLICTS


def test_missing_unique_claim_is_gray_zero_even_with_phone_fact() -> None:
    deterministic = _deterministic(
        "Jane Example\nMunich\nPhone: +49 30 123456\nSoftware engineer"
    )

    report = score_deterministic(deterministic, load_weights())

    assert report.claimed_location.confidence == "undetermined"
    assert report.band is Band.GRAY
    assert report.score == 0
    assert report.signal_count == 0


def test_unique_claim_without_comparison_is_gray_at_configured_base_score() -> None:
    deterministic = _deterministic(
        "Jane Example\nCurrent location: Munich\nSoftware engineer"
    )

    report = score_deterministic(deterministic, load_weights())

    assert report.claimed_location.confidence == "high"
    assert report.band is Band.GRAY
    assert report.score == 50
    assert report.signal_count == 0


def test_scoring_policy_identity_is_separate_from_weights_version() -> None:
    report = score_deterministic(
        _deterministic(
            "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456"
        ),
        load_weights(),
    )

    assert report.ruleset_version.version == "1.0.0"
    assert (
        report.ruleset_version.scoring_policy_version
        == "deterministic-phone-postal-comparison-v2"
    )
    assert report.ruleset_version.audit_identity == (
        "weights:1.0.0;policy:deterministic-phone-postal-comparison-v2"
    )
    assert report.ruleset_version.audit_identity != (
        "weights:1.0.0;policy:legacy-prototype-v1"
    )


def test_legal_weights_version_bump_is_explicit_and_not_hardcoded() -> None:
    weights = replace(load_weights(), version="1.0.1")
    deterministic = _deterministic(
        "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456",
        ruleset_version=weights.version,
    )

    report = score_deterministic(deterministic, weights)

    assert report.ruleset_version.version == "1.0.1"
    assert report.ruleset_version.scoring_policy_version == (
        "deterministic-phone-postal-comparison-v2"
    )
    assert report.signal_count == 1


def test_weights_version_mismatch_fails_closed() -> None:
    deterministic = _deterministic(
        "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456",
        ruleset_version="1.0.1",
    )

    report = score_deterministic(deterministic, load_weights())

    assert report.band is Band.GRAY
    assert report.score == 50
    assert report.signal_count == 0


def test_unknown_phone_rule_id_is_fail_closed() -> None:
    deterministic = _deterministic(
        "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456\nEngineer"
    )
    signal = deterministic.scoring_signals[0]
    tampered = _unsafe_with_signal(
        deterministic,
        replace(signal, rule_id="unknown-rule:v1"),
    )

    report = score_deterministic(tampered, load_weights())

    assert report.band is Band.GRAY
    assert report.signal_count == 0
    assert not any(finding.signal == "phone_country" for finding in report.findings)


def test_wrong_ruleset_or_non_code_authority_is_fail_closed() -> None:
    deterministic = _deterministic(
        "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456\nEngineer"
    )
    signal = deterministic.scoring_signals[0]
    wrong_ruleset = replace(signal, ruleset_version="other")
    non_code = replace(
        signal,
        provenance=replace(signal.provenance, authority="ai"),  # type: ignore[arg-type]
    )

    for changed_signal in (wrong_ruleset, non_code):
        changed = _unsafe_with_signal(deterministic, changed_signal)
        report = score_deterministic(changed, load_weights())
        assert report.signal_count == 0
        assert report.band is Band.GRAY


def test_phone_signal_requires_person_owned_phone_facts() -> None:
    deterministic = _deterministic(
        "Jane Example\nCurrent location: Munich\n+49 30 123456\nSoftware engineer"
    )
    phone_fact = next(
        fact for fact in deterministic.facts if fact.kind is FactKind.PHONE_COUNTRY
    )
    signal_source = _deterministic(
        "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456\nEngineer"
    ).scoring_signals[0]
    signal = replace(signal_source, supporting_fact_ids=(phone_fact.id,))
    changed = _unsafe_with_signal(deterministic, signal)

    report = score_deterministic(changed, load_weights())

    assert signal.kind is ScoringSignalKind.PHONE_COUNTRY
    assert report.signal_count == 0


def test_claim_projection_requires_person_owned_code_fact_and_candidate() -> None:
    deterministic = _deterministic(
        "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456"
    )
    claim = next(
        fact for fact in deterministic.facts if fact.kind is FactKind.CLAIMED_LOCATION
    )
    changed = _unsafe_with_facts(
        deterministic,
        tuple(
            replace(fact, subject=Subject.UNKNOWN) if fact.id == claim.id else fact
            for fact in deterministic.facts
        ),
    )

    report = score_deterministic(changed, load_weights())

    assert report.claimed_location.confidence == "undetermined"
    assert report.score == 0
    assert report.signal_count == 0


def test_zero_weight_observations_are_top_level_informational_only() -> None:
    raw_id = "123-45-6789"
    deterministic = _deterministic(
        "Jane Example\nCurrent location: Munich\nPostal: 10115\n"
        f"Eligible to work in Germany\nSSN: {raw_id}\nEngineer"
    )

    report = score_deterministic(deterministic, load_weights())

    informational = {
        finding.signal: finding
        for finding in report.findings
        if finding.signal
        in {"postal_compatibility", "right_to_work", "national_id"}
    }
    assert set(informational) == {
        "postal_compatibility",
        "right_to_work",
        "national_id",
    }
    assert all(value.direction is AgreementDirection.INFORMATIONAL for value in informational.values())
    assert all(value.weight == 0 for value in informational.values())
    assert all(value.score_impact == "none" for value in informational.values())
    assert raw_id not in repr(informational)
    assert not any(
        observation.kind not in {
            ObservationKind.POSTAL_COMPATIBILITY,
            ObservationKind.RIGHT_TO_WORK,
            ObservationKind.NATIONAL_ID,
        }
        for observation in deterministic.observations
    )


def test_non_code_observation_cannot_be_projected_as_deterministic_finding() -> None:
    deterministic = _deterministic(
        "Jane Example\nCurrent location: Munich\nPostal: 10115\nEngineer"
    )
    postal = next(
        observation
        for observation in deterministic.observations
        if observation.kind is ObservationKind.POSTAL_COMPATIBILITY
    )
    changed = replace(
        deterministic,
        observations=(
            replace(
                postal,
                provenance=replace(postal.provenance, authority="ai"),  # type: ignore[arg-type]
            ),
        ),
    )

    report = score_deterministic(changed, load_weights())

    assert not any(
        finding.signal == "postal_compatibility" for finding in report.findings
    )
    assert report.signal_count == 0
