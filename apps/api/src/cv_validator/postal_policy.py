from __future__ import annotations

import re

from cv_validator.domain import (
    Authority,
    Candidate,
    CandidateKind,
    ComponentVersion,
    Fact,
    FactKind,
    LocationRelation,
    ScoringSignal,
    ScoringSignalKind,
    SourceContext,
    Subject,
)
from cv_validator.extraction.postal import POSTAL_PATTERNS, POSTAL_REFERENCE_VERSION


POSTAL_RULE_ID = "postal-country-person-contact:v1"
POSTAL_FACT_EXTRACTOR = ComponentVersion("postal-country-classification", "1")


def unique_postal_country(value: str) -> str | None:
    countries = tuple(
        country
        for country, pattern in POSTAL_PATTERNS.items()
        if re.fullmatch(pattern, value, re.IGNORECASE)
    )
    return countries[0] if len(countries) == 1 else None


def postal_signal_graph_is_valid(
    candidates: tuple[Candidate, ...],
    facts: tuple[Fact, ...],
    signal: ScoringSignal,
    *,
    expected_ruleset_version: str,
) -> bool:
    if (
        signal.kind is not ScoringSignalKind.POSTAL_COUNTRY
        or signal.rule_id != POSTAL_RULE_ID
        or signal.ruleset_version != expected_ruleset_version
        or signal.provenance.authority is not Authority.CODE
        or signal.provenance.extractor != POSTAL_FACT_EXTRACTOR
        or signal.provenance.reference_data != POSTAL_REFERENCE_VERSION
        or signal.relation is not LocationRelation.PERSON
        or signal.source_context is not SourceContext.DOCUMENT_START_BLOCK
        or not signal.supporting_fact_ids
    ):
        return False

    candidates_by_id = {candidate.id: candidate for candidate in candidates}
    facts_by_id = {fact.id: fact for fact in facts}
    supported = tuple(facts_by_id.get(fact_id) for fact_id in signal.supporting_fact_ids)
    if any(fact is None for fact in supported):
        return False

    evidence = []
    for fact in supported:
        if fact is None or (
            fact.kind is not FactKind.POSTAL_COUNTRY
            or fact.value != signal.value
            or fact.subject is not Subject.PERSON
            or fact.relation is not LocationRelation.PERSON
            or fact.source_context is not SourceContext.DOCUMENT_START_BLOCK
            or fact.provenance.authority is not Authority.CODE
            or fact.provenance.extractor != POSTAL_FACT_EXTRACTOR
            or fact.provenance.reference_data != POSTAL_REFERENCE_VERSION
            or len(fact.source_candidate_ids) != 1
        ):
            return False
        candidate = candidates_by_id.get(fact.source_candidate_ids[0])
        if candidate is None or (
            candidate.kind is not CandidateKind.POSTAL
            or candidate.provenance.authority is not Authority.CODE
            or unique_postal_country(candidate.value) != fact.value
            or fact.provenance.evidence != candidate.provenance.evidence
            or fact.value_evidence != candidate.provenance.evidence
        ):
            return False
        evidence.extend(fact.provenance.evidence)

    stable_evidence = tuple(
        sorted(
            set(evidence),
            key=lambda item: (
                item.page_number,
                item.start_offset,
                item.end_offset,
            ),
        )
    )
    return signal.provenance.evidence == stable_evidence
