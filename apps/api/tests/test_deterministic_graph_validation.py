from dataclasses import replace

import pytest

from cv_validator.config import load_weights
from cv_validator.domain import (
    ComponentVersion,
    DeterministicAnalysisResult,
    FactId,
    FactKind,
    ScoringSignalId,
    ScoringSignalKind,
    Subject,
)
from cv_validator.extraction.eu_observations import classify_eu_observations
from cv_validator.scoring.engine import score_deterministic

from test_deterministic_scoring import _deterministic


def _unsafe_result(
    base: DeterministicAnalysisResult,
    *,
    facts=None,
    scoring_signals=None,
) -> DeterministicAnalysisResult:
    result = object.__new__(DeterministicAnalysisResult)
    object.__setattr__(result, "candidates", base.candidates)
    object.__setattr__(result, "facts", facts if facts is not None else base.facts)
    object.__setattr__(result, "observations", base.observations)
    object.__setattr__(result, "ruleset_version", base.ruleset_version)
    object.__setattr__(
        result,
        "scoring_signals",
        scoring_signals if scoring_signals is not None else base.scoring_signals,
    )
    return result


def _forged_partial_phone_signal(base: DeterministicAnalysisResult):
    phone = next(
        fact
        for fact in base.facts
        if fact.kind is FactKind.PHONE_COUNTRY and fact.value == "DE"
    )
    template = _deterministic(
        "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456"
    ).scoring_signals[0]
    return replace(
        template,
        id=ScoringSignalId("signal:phone_country:forged-partial"),
        kind=ScoringSignalKind.PHONE_COUNTRY,
        value="DE",
        supporting_fact_ids=(phone.id,),
        ruleset_version=base.ruleset_version,
        provenance=replace(template.provenance, evidence=phone.provenance.evidence),
    )


def test_duplicate_scoring_category_is_rejected_by_graph_invariant() -> None:
    base = _deterministic(
        "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456"
    )
    signal = base.scoring_signals[0]
    duplicate = replace(signal, id=ScoringSignalId("signal:phone_country:duplicate"))

    with pytest.raises(ValueError, match="duplicate scoring category"):
        replace(base, scoring_signals=(signal, duplicate))


def test_scorer_defensively_ignores_unsafe_duplicate_category() -> None:
    base = _deterministic(
        "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456"
    )
    signal = base.scoring_signals[0]
    duplicate = replace(signal, id=ScoringSignalId("signal:phone_country:duplicate"))
    unsafe = _unsafe_result(base, scoring_signals=(signal, duplicate))

    report = score_deterministic(unsafe, load_weights())

    assert report.band.value == "gray"
    assert report.score == 50
    assert report.signal_count == 0
    assert report.supporting_count == 0
    assert report.conflicting_count == 0


@pytest.mark.parametrize(
    "fact_change",
    (
        {"provenance_extractor": ComponentVersion("phone-classification", "other")},
        {"reference_data": ComponentVersion("other-phone-data", "1")},
        {"subject": Subject.UNKNOWN},
    ),
)
def test_phone_fact_requires_exact_allowlisted_provenance(
    fact_change,
) -> None:
    base = _deterministic(
        "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456"
    )
    phone = next(fact for fact in base.facts if fact.kind is FactKind.PHONE_COUNTRY)
    changes = dict(fact_change)
    if extractor := changes.pop("provenance_extractor", None):
        changes["provenance"] = replace(phone.provenance, extractor=extractor)
    if reference := changes.pop("reference_data", None):
        changes["provenance"] = replace(phone.provenance, reference_data=reference)
    changed_phone = replace(phone, **changes)
    changed_facts = tuple(
        changed_phone if fact.id == phone.id else fact for fact in base.facts
    )

    with pytest.raises(ValueError, match="invalid phone scoring graph"):
        replace(base, facts=changed_facts)


def test_fact_and_signal_evidence_must_match_their_exact_sources() -> None:
    base = _deterministic(
        "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456"
    )
    claim = next(fact for fact in base.facts if fact.kind is FactKind.CLAIMED_LOCATION)
    phone = next(fact for fact in base.facts if fact.kind is FactKind.PHONE_COUNTRY)
    bad_phone = replace(
        phone,
        provenance=replace(phone.provenance, evidence=claim.provenance.evidence),
    )
    changed_facts = tuple(
        bad_phone if fact.id == phone.id else fact for fact in base.facts
    )

    with pytest.raises(ValueError, match="invalid phone scoring graph"):
        replace(base, facts=changed_facts)

    signal = base.scoring_signals[0]
    bad_signal = replace(
        signal,
        provenance=replace(signal.provenance, evidence=claim.provenance.evidence),
    )
    with pytest.raises(ValueError, match="invalid phone scoring graph"):
        replace(base, scoring_signals=(bad_signal,))


def test_phone_country_is_recomputed_from_exact_candidate_value() -> None:
    base = _deterministic(
        "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456"
    )
    phone = next(fact for fact in base.facts if fact.kind is FactKind.PHONE_COUNTRY)
    changed_phone = replace(phone, value="US")
    changed_facts = tuple(
        changed_phone if fact.id == phone.id else fact for fact in base.facts
    )
    changed_signal = replace(base.scoring_signals[0], value="US")

    with pytest.raises(ValueError, match="invalid phone scoring graph"):
        replace(
            base,
            facts=changed_facts,
            scoring_signals=(changed_signal,),
        )

    unsafe = _unsafe_result(
        base,
        facts=changed_facts,
        scoring_signals=(changed_signal,),
    )
    assert score_deterministic(unsafe, load_weights()).signal_count == 0


@pytest.mark.parametrize(
    "text",
    (
        (
            "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456\n"
            "Mobile: +1 415 555 0100"
        ),
        (
            "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456\n"
            "Mobile: 030 123456"
        ),
        (
            "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456\n"
            "Mobile: +1 200 555 0100"
        ),
        (
            "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456\n"
            "Mobile: +1 123456"
        ),
    ),
)
def test_partial_aggregate_cannot_omit_conflicting_unresolved_or_possible_phone(
    text,
) -> None:
    base = _deterministic(text)
    forged = _forged_partial_phone_signal(base)

    with pytest.raises(ValueError, match="invalid phone scoring graph"):
        replace(base, scoring_signals=(forged,))

    unsafe = _unsafe_result(base, scoring_signals=(forged,))
    report = score_deterministic(unsafe, load_weights())
    assert report.signal_count == 0
    assert report.band.value == "gray"


def test_renamed_claim_fact_and_duplicate_signal_are_rejected_everywhere() -> None:
    base = _deterministic(
        "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456"
    )
    claim = next(fact for fact in base.facts if fact.kind is FactKind.CLAIMED_LOCATION)
    forged_phone = replace(
        claim,
        id=FactId("fact:phone_country:forged-from-claim"),
        kind=FactKind.PHONE_COUNTRY,
        subject=Subject.PERSON,
        value="US",
    )
    facts = (*base.facts, forged_phone)
    signal = base.scoring_signals[0]
    forged_signal = replace(
        signal,
        id=ScoringSignalId("signal:phone_country:forged"),
        value="US",
        supporting_fact_ids=(forged_phone.id,),
    )

    with pytest.raises(ValueError):
        replace(base, facts=facts, scoring_signals=(signal, forged_signal))

    unsafe = _unsafe_result(
        base,
        facts=facts,
        scoring_signals=(signal, forged_signal),
    )
    report = score_deterministic(unsafe, load_weights())
    eu_kinds = {
        observation.kind.value
        for observation in classify_eu_observations(
            unsafe.candidates,
            unsafe.facts,
            unsafe.scoring_signals,
            ruleset_version=unsafe.ruleset_version,
        )
    }

    assert report.band.value == "gray"
    assert report.score == 50
    assert report.signal_count == 0
    assert "phone_outside_eu" not in eu_kinds
    assert "combined_location_outside_eu" not in eu_kinds


def test_phone_fact_renamed_as_claim_is_rejected_by_score_and_outside_eu() -> None:
    base = _deterministic(
        "Jane Example\nCurrent location: Munich\nPhone: +49 30 123456"
    )
    real_claim = next(
        fact for fact in base.facts if fact.kind is FactKind.CLAIMED_LOCATION
    )
    phone = next(fact for fact in base.facts if fact.kind is FactKind.PHONE_COUNTRY)
    forged_claim = replace(
        phone,
        id=FactId("fact:claimed_location:forged-from-phone"),
        kind=FactKind.CLAIMED_LOCATION,
        value="US",
        relation=real_claim.relation,
        resolved_level="country",
        resolved_name="United States",
        resolved_record_ids=("country:US",),
    )
    facts = tuple(
        forged_claim if fact.id == real_claim.id else fact for fact in base.facts
    )

    with pytest.raises(ValueError, match="invalid claimed-location graph"):
        replace(base, facts=facts)

    unsafe = _unsafe_result(base, facts=facts)
    report = score_deterministic(unsafe, load_weights())
    outside = classify_eu_observations(
        unsafe.candidates,
        unsafe.facts,
        unsafe.scoring_signals,
        ruleset_version=unsafe.ruleset_version,
    )

    assert report.claimed_location.confidence == "undetermined"
    assert report.score == 0
    assert report.signal_count == 0
    assert "stated_location_outside_eu" not in {
        observation.kind.value for observation in outside
    }
