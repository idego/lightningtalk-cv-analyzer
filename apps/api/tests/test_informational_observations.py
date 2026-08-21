from cv_validator.domain import (
    CandidateKind,
    ObservationKind,
    ObservationStatus,
)
from cv_validator.extraction.deterministic import analyze_deterministically
from cv_validator.ingestion import RawDocument, SourcePage
from cv_validator.ingestion.redaction import MASK_CHARACTER, redact_national_ids


def _analyze(text: str):
    raw = RawDocument(
        pages=(SourcePage("page-0001", 1, text),),
        source_format="text",
    )
    return analyze_deterministically(redact_national_ids(raw), "1.0.0")


def test_shared_postal_format_lists_every_compatible_country_without_scoring() -> None:
    result = _analyze("Jane Example\nPostal code: 10115\nSoftware engineer profile")

    candidate = next(
        value for value in result.candidates if value.kind is CandidateKind.POSTAL
    )
    observation = next(
        value
        for value in result.observations
        if value.kind is ObservationKind.POSTAL_COMPATIBILITY
    )
    assert candidate.provenance.evidence[0].excerpt == "10115"
    assert observation.status is ObservationStatus.INFORMATIONAL
    assert observation.subject_ids == (str(candidate.id),)
    assert observation.values == ("DE", "FR", "US")
    assert observation.provenance.evidence == candidate.provenance.evidence
    assert observation.provenance.reference_data.name == "postal-patterns"
    assert result.scoring_signals == ()


def test_distinct_postal_format_stays_zero_weight_observation() -> None:
    result = _analyze("Jan Przykład\nKod pocztowy: 00-001\nInżynier oprogramowania")

    observation = next(
        value
        for value in result.observations
        if value.kind is ObservationKind.POSTAL_COMPATIBILITY
    )
    assert observation.values == ("PL",)
    assert "does not prove" in observation.reason
    assert result.scoring_signals == ()


def test_right_to_work_keeps_the_complete_source_line_as_informational() -> None:
    source_line = "Eligible to work in Germany without sponsorship"
    result = _analyze(f"Jane Example\n{source_line}\nSoftware engineer profile")

    candidate = next(
        value
        for value in result.candidates
        if value.kind is CandidateKind.RIGHT_TO_WORK
    )
    observation = next(
        value
        for value in result.observations
        if value.kind is ObservationKind.RIGHT_TO_WORK
    )
    assert candidate.value == source_line
    assert candidate.provenance.evidence[0].excerpt == source_line
    assert observation.provenance.evidence[0].excerpt == source_line
    assert observation.status is ObservationStatus.INFORMATIONAL
    assert "eligibility" in observation.reason
    assert result.scoring_signals == ()


def test_national_id_presence_observation_contains_only_redacted_evidence() -> None:
    raw_id = "123-45-6789"
    result = _analyze(
        f"Jane Example\nSSN: {raw_id}\nSoftware engineer profile"
    )

    candidate = next(
        value
        for value in result.candidates
        if value.kind is CandidateKind.NATIONAL_ID
    )
    observation = next(
        value
        for value in result.observations
        if value.kind is ObservationKind.NATIONAL_ID
    )
    assert observation.values == (candidate.value,)
    assert set(observation.provenance.evidence[0].excerpt) == {MASK_CHARACTER}
    assert raw_id not in repr(observation)
    assert observation.status is ObservationStatus.INFORMATIONAL
    assert result.scoring_signals == ()
