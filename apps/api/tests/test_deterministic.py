from cv_validator.domain import (
    CandidateKind,
    ObservationKind,
    ObservationStatus,
    Subject,
)
from cv_validator.extraction.deterministic import analyze_deterministically
from cv_validator.ingestion import RawDocument, SourcePage
from cv_validator.ingestion.redaction import redact_national_ids


def _analyze(text: str):
    raw = RawDocument(
        pages=(SourcePage("page-0001", 1, text),),
        source_format="text",
    )
    return analyze_deterministically(redact_national_ids(raw), "1.0.0")


def test_extracts_all_candidate_kinds_with_exact_page_evidence():
    result = _analyze(
        "Jane Example\n"
        "Phone: +48 22 123 45 67\n"
        "Email: jane@example.com\n"
        "Website: https://example.com/cv\n"
        "Date: 2024-08-21\n"
        "Postal: 00-001\n"
        "Location: Warsaw, Poland\n"
        "Experience software engineer"
    )

    kinds = {candidate.kind for candidate in result.candidates}
    assert {
        CandidateKind.PHONE,
        CandidateKind.EMAIL,
        CandidateKind.URL,
        CandidateKind.DATE,
        CandidateKind.POSTAL,
        CandidateKind.EXPLICIT_LOCATION,
    } <= kinds
    for candidate in result.candidates:
        for evidence in candidate.provenance.evidence:
            assert evidence.page_id == "page-0001"
            assert evidence.excerpt


def test_date_ranges_are_not_phone_candidates():
    for date_range in ("04/2024 - 12/2024", "2020 - 2022"):
        result = _analyze(
            "Jane Example\n"
            f"Employment: {date_range}\n"
            "Experience software engineer"
        )

        assert not any(
            candidate.kind is CandidateKind.PHONE for candidate in result.candidates
        )

    assert any(
        candidate.kind is CandidateKind.DATE
        for candidate in _analyze(
            "Jane Example\nEmployment: 04/2024 - 12/2024\n"
            "Experience software engineer"
        ).candidates
    )


def test_digits_inside_email_address_never_become_phone_evidence():
    result = _analyze(
        "Jane Example\n"
        "Email: candidate.1234567@example.com\n"
        "Experienced software engineer profile"
    )

    assert any(
        candidate.kind is CandidateKind.EMAIL for candidate in result.candidates
    )
    assert not any(
        candidate.kind is CandidateKind.PHONE for candidate in result.candidates
    )
    assert not result.facts
    assert not result.observations
    assert not result.scoring_signals


def test_explicit_phone_label_preserves_valid_german_number_with_year_like_digits():
    result = _analyze(
        "Jane Example\n"
        "Phone: +49 2020-2022\n"
        "Experienced software engineer profile"
    )

    phone_candidates = [
        candidate
        for candidate in result.candidates
        if candidate.kind is CandidateKind.PHONE
    ]
    assert [candidate.value for candidate in phone_candidates] == ["+49 2020-2022"]
    assert any(fact.value == "DE" for fact in result.facts)


def test_possible_phone_remains_observation_and_blocks_aggregate_signal():
    result = _analyze(
        "Jane Example\n"
        "Phone: +48 22 123 45 67\n"
        "Mobile: +1 200 555 0100\n"
        "Experience software engineer"
    )

    assert len(result.facts) == 1
    assert any(
        observation.status is ObservationStatus.POSSIBLE
        for observation in result.observations
    )
    assert any(
        observation.kind is ObservationKind.PHONE_COUNTRY_AGGREGATE
        and observation.status is ObservationStatus.AMBIGUOUS
        for observation in result.observations
    )
    assert result.scoring_signals == ()


def test_all_resolved_person_phones_agree_and_create_one_signal():
    result = _analyze(
        "Jane Example\n"
        "Phone: +48 22 123 45 67\n"
        "Mobile: 0048 58 123 45 67\n"
        "Experience software engineer"
    )

    assert len(result.facts) == 2
    assert {fact.value for fact in result.facts} == {"PL"}
    assert {fact.subject for fact in result.facts} == {Subject.PERSON}
    assert len(result.scoring_signals) == 1
    assert result.scoring_signals[0].value == "PL"
    assert len(result.scoring_signals[0].supporting_fact_ids) == 2


def test_conflicting_resolved_person_phones_are_ambiguous_and_non_scoring():
    result = _analyze(
        "Jane Example\n"
        "Phone: +48 22 123 45 67\n"
        "Mobile: +49 30 123456\n"
        "Experience software engineer"
    )

    assert {fact.value for fact in result.facts} == {"PL", "DE"}
    aggregate = next(
        observation
        for observation in result.observations
        if observation.kind is ObservationKind.PHONE_COUNTRY_AGGREGATE
    )
    assert aggregate.status is ObservationStatus.AMBIGUOUS
    assert result.scoring_signals == ()


def test_unlabelled_valid_phone_defaults_to_candidate_and_is_scored():
    result = _analyze(
        "Jane Example\n"
        "+48 22 123 45 67\n"
        "Experience software engineer"
    )

    assert len(result.facts) == 1
    assert result.facts[0].subject is Subject.PERSON
    assert len(result.scoring_signals) == 1
    assert result.scoring_signals[0].value == "PL"


def test_local_phone_is_unresolved_without_default_country():
    result = _analyze(
        "Jane Example\n"
        "Phone: 030 123456\n"
        "Experience software engineer"
    )

    assert result.facts == ()
    assert any(
        observation.status is ObservationStatus.UNRESOLVED
        for observation in result.observations
    )
    assert result.scoring_signals == ()


def test_every_phone_occurrence_is_retained_and_result_is_reproducible():
    text = (
        "Jane Example\n"
        "Phone: +48 22 123 45 67\n"
        "Mobile: +48 22 123 45 67\n"
        "Experience software engineer"
    )

    first = _analyze(text)
    second = _analyze(text)
    phones = [
        candidate
        for candidate in first.candidates
        if candidate.kind is CandidateKind.PHONE
    ]

    assert len(phones) == 2
    assert first == second


def test_phone_fact_preserves_exact_second_page_evidence():
    raw = RawDocument(
        pages=(
            SourcePage("page-0001", 1, "Jane Example\nExperience software engineer"),
            SourcePage("page-0002", 2, "Phone: +48 22 123 45 67\nMore profile text"),
        ),
        source_format="text",
    )
    redacted = redact_national_ids(raw)

    result = analyze_deterministically(redacted, "1.0.0")
    fact = result.facts[0]
    evidence = fact.provenance.evidence[0]

    assert evidence.page_id == "page-0002"
    assert evidence.page_number == 2
    assert evidence.excerpt == "+48 22 123 45 67"
    assert (
        redacted.pages[1].text[evidence.start_offset : evidence.end_offset]
        == evidence.excerpt
    )
