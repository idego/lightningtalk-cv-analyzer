from __future__ import annotations

from cv_validator.domain import (
    Authority,
    Candidate,
    CandidateKind,
    Fact,
    FactId,
    FactKind,
    LocationRelation,
    Provenance,
    ScoringSignal,
    ScoringSignalId,
    ScoringSignalKind,
    SourceContext,
    Subject,
)
from cv_validator.ingestion import RedactedDocument
from cv_validator.location_policy import claimed_location_graph_is_valid
from cv_validator.postal_policy import (
    POSTAL_FACT_EXTRACTOR,
    POSTAL_RULE_ID,
    unique_postal_country,
)
from cv_validator.extraction.postal import POSTAL_REFERENCE_VERSION


def classify_person_postal_countries(
    document: RedactedDocument,
    candidates: tuple[Candidate, ...],
    facts: tuple[Fact, ...],
    *,
    ruleset_version: str,
) -> tuple[tuple[Fact, ...], tuple[ScoringSignal, ...]]:
    claims = tuple(
        fact
        for fact in facts
        if fact.kind is FactKind.CLAIMED_LOCATION
        and fact.subject is Subject.PERSON
        and claimed_location_graph_is_valid(candidates, fact)
    )
    if len(claims) != 1:
        return (), ()
    claim = claims[0]
    if claim.source_context is not SourceContext.DOCUMENT_START_BLOCK:
        return (), ()

    page_text = {page.page_id: page.text for page in document.pages}
    eligible: list[tuple[Candidate, str]] = []
    for candidate in candidates:
        if candidate.kind is not CandidateKind.POSTAL:
            continue
        country = unique_postal_country(candidate.value)
        if country is None or not _shares_source_line(
            page_text,
            candidate.provenance.evidence,
            claim.value_evidence,
        ):
            continue
        eligible.append((candidate, country))

    postal_facts = tuple(
        Fact(
            id=FactId(f"fact:postal_country:{candidate.id}"),
            kind=FactKind.POSTAL_COUNTRY,
            value=country,
            subject=Subject.PERSON,
            source_candidate_ids=(candidate.id,),
            provenance=Provenance(
                authority=Authority.CODE,
                evidence=candidate.provenance.evidence,
                extractor=POSTAL_FACT_EXTRACTOR,
                reference_data=POSTAL_REFERENCE_VERSION,
            ),
            relation=LocationRelation.PERSON,
            source_context=SourceContext.DOCUMENT_START_BLOCK,
            value_evidence=candidate.provenance.evidence,
        )
        for candidate, country in eligible
    )
    countries = {fact.value for fact in postal_facts}
    if not postal_facts or len(countries) != 1:
        return postal_facts, ()

    evidence = tuple(
        sorted(
            {
                evidence
                for fact in postal_facts
                for evidence in fact.provenance.evidence
            },
            key=lambda item: (
                item.page_number,
                item.start_offset,
                item.end_offset,
            ),
        )
    )
    country = next(iter(countries))
    return postal_facts, (
        ScoringSignal(
            id=ScoringSignalId("signal:postal_country:aggregate"),
            kind=ScoringSignalKind.POSTAL_COUNTRY,
            value=country,
            supporting_fact_ids=tuple(fact.id for fact in postal_facts),
            rule_id=POSTAL_RULE_ID,
            ruleset_version=ruleset_version,
            provenance=Provenance(
                authority=Authority.CODE,
                evidence=evidence,
                extractor=POSTAL_FACT_EXTRACTOR,
                reference_data=POSTAL_REFERENCE_VERSION,
            ),
            relation=LocationRelation.PERSON,
            source_context=SourceContext.DOCUMENT_START_BLOCK,
        ),
    )


def _shares_source_line(page_text, left_evidence, right_evidence) -> bool:
    for left in left_evidence:
        text = page_text.get(left.page_id)
        if text is None:
            continue
        left_line_start = text.rfind("\n", 0, left.start_offset) + 1
        left_line_end = text.find("\n", left.end_offset)
        if left_line_end < 0:
            left_line_end = len(text)
        for right in right_evidence:
            if (
                right.page_id == left.page_id
                and left_line_start <= right.start_offset
                and right.end_offset <= left_line_end
            ):
                return True
    return False
