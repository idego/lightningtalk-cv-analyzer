from __future__ import annotations

from cv_validator.domain import (
    Authority,
    Candidate,
    CandidateKind,
    ComponentVersion,
    Fact,
    FactKind,
    LocationRelation,
    Subject,
)
from cv_validator.phone_policy import PHONE_CANDIDATE_EXTRACTOR, stable_evidence


LOCATION_CLASSIFIER = ComponentVersion("location-ownership", "1")
APPROVED_LOCATION_REFERENCE_NAMES = frozenset(
    {"geonames-sqlite", "test-locations"}
)


def claimed_location_graph_is_valid(
    candidates: tuple[Candidate, ...],
    fact: Fact,
) -> bool:
    if (
        fact.kind is not FactKind.CLAIMED_LOCATION
        or fact.subject is not Subject.PERSON
        or fact.relation is not LocationRelation.PERSON
        or fact.provenance.authority is not Authority.CODE
        or fact.provenance.extractor != LOCATION_CLASSIFIER
        or fact.provenance.reference_data is None
        or fact.provenance.reference_data.name
        not in APPROVED_LOCATION_REFERENCE_NAMES
        or not fact.provenance.reference_data.version.strip()
        or not fact.source_candidate_ids
        or not fact.resolved_level
        or not fact.resolved_name
        or not fact.resolved_record_ids
    ):
        return False

    candidates_by_id = {candidate.id: candidate for candidate in candidates}
    sources = tuple(
        candidates_by_id.get(candidate_id)
        for candidate_id in fact.source_candidate_ids
    )
    if any(candidate is None for candidate in sources):
        return False
    if any(
        candidate.kind is not CandidateKind.EXPLICIT_LOCATION
        or candidate.subject is not Subject.PERSON
        or candidate.relation is not LocationRelation.PERSON
        or candidate.provenance.authority is not Authority.CODE
        or candidate.provenance.extractor != PHONE_CANDIDATE_EXTRACTOR
        or not candidate.relation_evidence
        or not candidate.value_evidence
        or candidate.provenance.evidence != candidate.value_evidence
        for candidate in sources
        if candidate is not None
    ):
        return False

    expected_relation_evidence = stable_evidence(
        evidence
        for candidate in sources
        if candidate is not None
        for evidence in candidate.relation_evidence
    )
    expected_value_evidence = stable_evidence(
        evidence
        for candidate in sources
        if candidate is not None
        for evidence in candidate.value_evidence
    )
    return (
        fact.provenance.evidence == expected_relation_evidence
        and fact.relation_evidence == expected_relation_evidence
        and fact.value_evidence == expected_value_evidence
    )
