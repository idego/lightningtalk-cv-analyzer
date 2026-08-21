from __future__ import annotations

import re

import phonenumbers

from cv_validator.domain import (
    Authority,
    Candidate,
    CandidateKind,
    ComponentVersion,
    Fact,
    FactId,
    FactKind,
    Observation,
    ObservationId,
    ObservationKind,
    ObservationStatus,
    Provenance,
    ScoringSignal,
    ScoringSignalId,
    ScoringSignalKind,
    Subject,
)
from cv_validator.ingestion import RedactedDocument

PHONE_CLASSIFIER_VERSION = "1"
PHONE_AGGREGATION_RULE = "phone-country-all-person-owned-agree:v1"

_PERSON_PHONE_LABEL = re.compile(
    r"\b(?:phone|mobile|telephone|tel|contact[ \t]+number|telefon|"
    r"telefon[ \t]+komórkowy|handy|mobil)\b[ \t]*[:#-]?[ \t]*$",
    re.IGNORECASE,
)
_NON_PERSON_PHONE_LABEL = re.compile(
    r"\b(?:fax|referee|reference|company|office)\b",
    re.IGNORECASE,
)


def classify_and_aggregate_phones(
    document: RedactedDocument,
    candidates: tuple[Candidate, ...],
    ruleset_version: str,
) -> tuple[tuple[Fact, ...], tuple[Observation, ...], tuple[ScoringSignal, ...]]:
    phone_candidates = tuple(
        candidate for candidate in candidates if candidate.kind is CandidateKind.PHONE
    )
    if not phone_candidates:
        return (), (), ()

    pages = {page.page_id: page for page in document.pages}
    facts: list[Fact] = []
    observations: list[Observation] = []
    person_candidates: list[Candidate] = []
    person_fact_by_candidate: dict[str, Fact] = {}

    for candidate in phone_candidates:
        evidence = candidate.provenance.evidence[0]
        page = pages[evidence.page_id]
        subject = _phone_subject(page.text, evidence.start_offset)
        if subject is Subject.PERSON:
            person_candidates.append(candidate)

        fact, observation = _classify_phone(candidate, subject)
        if fact is not None:
            facts.append(fact)
            if subject is Subject.PERSON:
                person_fact_by_candidate[str(candidate.id)] = fact
        if observation is not None:
            observations.append(observation)

    aggregate_subjects = person_candidates or list(phone_candidates)
    aggregate_evidence = tuple(
        evidence
        for candidate in aggregate_subjects
        for evidence in candidate.provenance.evidence
    )
    reference_data = _reference_data_version()

    if not person_candidates:
        observations.append(
            Observation(
                id=ObservationId("observation:phone_country:aggregate"),
                kind=ObservationKind.PHONE_COUNTRY_AGGREGATE,
                status=ObservationStatus.AMBIGUOUS,
                subject_ids=tuple(str(candidate.id) for candidate in phone_candidates),
                values=tuple(candidate.value for candidate in phone_candidates),
                reason="No phone is explicitly labelled as belonging to the candidate",
                provenance=Provenance(
                    authority=Authority.CODE,
                    evidence=aggregate_evidence,
                    extractor=_extractor_version(),
                    reference_data=reference_data,
                ),
            )
        )
        return tuple(facts), tuple(observations), ()

    resolved_facts = tuple(person_fact_by_candidate.values())
    resolved_countries = {fact.value for fact in resolved_facts}
    every_person_phone_resolved = len(resolved_facts) == len(person_candidates)
    if every_person_phone_resolved and len(resolved_countries) == 1:
        country = next(iter(resolved_countries))
        signal = ScoringSignal(
            id=ScoringSignalId("signal:phone_country:aggregate"),
            kind=ScoringSignalKind.PHONE_COUNTRY,
            value=country,
            supporting_fact_ids=tuple(fact.id for fact in resolved_facts),
            rule_id=PHONE_AGGREGATION_RULE,
            ruleset_version=ruleset_version,
            provenance=Provenance(
                authority=Authority.CODE,
                evidence=aggregate_evidence,
                extractor=_extractor_version(),
                reference_data=reference_data,
            ),
        )
        return tuple(facts), tuple(observations), (signal,)

    reason = (
        "Explicitly person-owned phones resolve to conflicting countries"
        if len(resolved_countries) > 1
        else "At least one explicitly person-owned phone is not conclusively resolved"
    )
    observations.append(
        Observation(
            id=ObservationId("observation:phone_country:aggregate"),
            kind=ObservationKind.PHONE_COUNTRY_AGGREGATE,
            status=ObservationStatus.AMBIGUOUS,
            subject_ids=tuple(str(candidate.id) for candidate in person_candidates),
            values=tuple(sorted(resolved_countries)),
            reason=reason,
            provenance=Provenance(
                authority=Authority.CODE,
                evidence=aggregate_evidence,
                extractor=_extractor_version(),
                reference_data=reference_data,
            ),
        )
    )
    return tuple(facts), tuple(observations), ()


def _classify_phone(
    candidate: Candidate,
    subject: Subject,
) -> tuple[Fact | None, Observation | None]:
    raw_value = candidate.value.strip()
    if raw_value.startswith("00"):
        parse_value = "+" + raw_value[2:]
    elif raw_value.startswith("+"):
        parse_value = raw_value
    else:
        return None, _phone_observation(
            candidate,
            ObservationStatus.UNRESOLVED,
            "Phone country requires a default-region assumption",
        )

    try:
        parsed = phonenumbers.parse(parse_value, None)
    except phonenumbers.NumberParseException:
        return None, _phone_observation(
            candidate,
            ObservationStatus.UNRESOLVED,
            "Phone number cannot be parsed without a default region",
        )

    if not phonenumbers.is_possible_number(parsed):
        return None, _phone_observation(
            candidate,
            ObservationStatus.INVALID,
            "libphonenumber classifies the number as not possible",
        )
    if not phonenumbers.is_valid_number(parsed):
        return None, _phone_observation(
            candidate,
            ObservationStatus.POSSIBLE,
            "libphonenumber classifies the number as possible but not valid",
        )

    region = phonenumbers.region_code_for_number(parsed)
    if not region or region == "001":
        return None, _phone_observation(
            candidate,
            ObservationStatus.AMBIGUOUS,
            "Valid phone number does not resolve to one geographic region",
        )

    fact = Fact(
        id=FactId(f"fact:phone_country:{candidate.id}"),
        kind=FactKind.PHONE_COUNTRY,
        value=region,
        subject=subject,
        source_candidate_ids=(candidate.id,),
        provenance=Provenance(
            authority=Authority.CODE,
            evidence=candidate.provenance.evidence,
            extractor=_extractor_version(),
            reference_data=_reference_data_version(),
        ),
    )
    return fact, None


def _phone_observation(
    candidate: Candidate,
    status: ObservationStatus,
    reason: str,
) -> Observation:
    return Observation(
        id=ObservationId(f"observation:phone:{status.value}:{candidate.id}"),
        kind=ObservationKind.PHONE,
        status=status,
        subject_ids=(str(candidate.id),),
        values=(candidate.value,),
        reason=reason,
        provenance=Provenance(
            authority=Authority.CODE,
            evidence=candidate.provenance.evidence,
            extractor=_extractor_version(),
            reference_data=_reference_data_version(),
        ),
    )


def _phone_subject(page_text: str, start_offset: int) -> Subject:
    line_start = page_text.rfind("\n", 0, start_offset) + 1
    prefix = page_text[line_start:start_offset]
    if _NON_PERSON_PHONE_LABEL.search(prefix):
        return Subject.UNKNOWN
    if _PERSON_PHONE_LABEL.search(prefix):
        return Subject.PERSON
    return Subject.UNKNOWN


def _extractor_version() -> ComponentVersion:
    return ComponentVersion("phone-classification", PHONE_CLASSIFIER_VERSION)


def _reference_data_version() -> ComponentVersion:
    return ComponentVersion("libphonenumber", phonenumbers.__version__)
