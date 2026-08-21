from __future__ import annotations

from collections.abc import Iterable

import phonenumbers

from cv_validator.domain import (
    Authority,
    Candidate,
    CandidateKind,
    ComponentVersion,
    Evidence,
    Fact,
    FactKind,
    ScoringSignal,
    ScoringSignalKind,
    Subject,
)


PHONE_RULE_ID = "phone-country-all-person-owned-agree:v1"
PHONE_CANDIDATE_EXTRACTOR = ComponentVersion("contact-candidates", "1")
PHONE_CLASSIFIER = ComponentVersion("phone-classification", "1")
PHONE_REFERENCE_DATA = ComponentVersion("libphonenumber", "9.0.37")


def phone_signal_graph_is_valid(
    candidates: tuple[Candidate, ...],
    facts: tuple[Fact, ...],
    signal: ScoringSignal,
    *,
    expected_ruleset_version: str,
) -> bool:
    if (
        signal.kind is not ScoringSignalKind.PHONE_COUNTRY
        or signal.rule_id != PHONE_RULE_ID
        or signal.provenance.authority is not Authority.CODE
        or signal.provenance.extractor != PHONE_CLASSIFIER
        or signal.provenance.reference_data != PHONE_REFERENCE_DATA
        or (
            signal.ruleset_version != expected_ruleset_version
        )
        or not signal.supporting_fact_ids
        or len(signal.supporting_fact_ids) != len(set(signal.supporting_fact_ids))
    ):
        return False

    candidates_by_id = {candidate.id: candidate for candidate in candidates}
    facts_by_id = {fact.id: fact for fact in facts}
    person_phone_candidates = tuple(
        candidate
        for candidate in candidates
        if candidate.kind is CandidateKind.PHONE
        and candidate.subject is Subject.PERSON
    )
    person_phone_facts = tuple(
        fact
        for fact in facts
        if fact.kind is FactKind.PHONE_COUNTRY
        and fact.subject is Subject.PERSON
    )
    if (
        set(signal.supporting_fact_ids)
        != {fact.id for fact in person_phone_facts}
    ):
        return False
    supporting_facts: list[Fact] = []
    used_source_candidates: set[object] = set()
    for fact_id in signal.supporting_fact_ids:
        fact = facts_by_id.get(fact_id)
        if fact is None or not _phone_fact_is_valid(fact, candidates_by_id):
            return False
        if fact.value != signal.value:
            return False
        source_ids = set(fact.source_candidate_ids)
        if source_ids & used_source_candidates:
            return False
        used_source_candidates.update(source_ids)
        supporting_facts.append(fact)

    if used_source_candidates != {
        candidate.id for candidate in person_phone_candidates
    }:
        return False

    return signal.provenance.evidence == stable_evidence(
        evidence
        for fact in supporting_facts
        for evidence in fact.provenance.evidence
    )


def stable_evidence(values: Iterable[Evidence]) -> tuple[Evidence, ...]:
    by_span = {
        (value.page_number, value.page_id, value.start_offset, value.end_offset): value
        for value in values
    }
    return tuple(by_span[key] for key in sorted(by_span))


def _phone_fact_is_valid(
    fact: Fact,
    candidates_by_id: dict[object, Candidate],
) -> bool:
    if (
        fact.kind is not FactKind.PHONE_COUNTRY
        or fact.subject is not Subject.PERSON
        or fact.provenance.authority is not Authority.CODE
        or fact.provenance.extractor != PHONE_CLASSIFIER
        or fact.provenance.reference_data != PHONE_REFERENCE_DATA
        or not fact.source_candidate_ids
        or len(fact.source_candidate_ids) != len(set(fact.source_candidate_ids))
    ):
        return False
    source_candidates = tuple(
        candidates_by_id.get(candidate_id)
        for candidate_id in fact.source_candidate_ids
    )
    if any(candidate is None for candidate in source_candidates):
        return False
    if any(
        candidate.kind is not CandidateKind.PHONE
        or candidate.subject is not Subject.PERSON
        or candidate.provenance.authority is not Authority.CODE
        or candidate.provenance.extractor != PHONE_CANDIDATE_EXTRACTOR
        for candidate in source_candidates
        if candidate is not None
    ):
        return False
    if len(source_candidates) != 1:
        return False
    source_candidate = source_candidates[0]
    if source_candidate is None or _resolved_phone_country(source_candidate.value) != fact.value:
        return False
    return fact.provenance.evidence == stable_evidence(
        evidence
        for candidate in source_candidates
        if candidate is not None
        for evidence in candidate.provenance.evidence
    )


def _resolved_phone_country(value: str) -> str | None:
    raw_value = value.strip()
    if raw_value.startswith("00"):
        parse_value = "+" + raw_value[2:]
    elif raw_value.startswith("+"):
        parse_value = raw_value
    else:
        return None
    try:
        parsed = phonenumbers.parse(parse_value, None)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    region = phonenumbers.region_code_for_number(parsed)
    return region if region and region != "001" else None
