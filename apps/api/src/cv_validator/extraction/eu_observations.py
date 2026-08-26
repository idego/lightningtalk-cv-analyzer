from __future__ import annotations

from cv_validator.domain import (
    Authority,
    Candidate,
    ComponentVersion,
    Evidence,
    Fact,
    FactKind,
    Observation,
    ObservationId,
    ObservationKind,
    ObservationStatus,
    Provenance,
    ScoringSignal,
    ScoringSignalKind,
    Subject,
)
from cv_validator.phone_policy import PHONE_RULE_ID, phone_signal_graph_is_valid
from cv_validator.location_policy import claimed_location_graph_is_valid


EU_MEMBER_STATES_NAME = "eu-member-states"
EU_MEMBER_STATES_SNAPSHOT = "2026-08-21"
EU_MEMBER_STATES_VERSION = f"eu27-{EU_MEMBER_STATES_SNAPSHOT}"
EU_MEMBER_STATES_SOURCE_URL = (
    "https://european-union.europa.eu/principles-countries-history/"
    "eu-countries_en"
)
EU_27_ISO2 = frozenset(
    {
        "AT",
        "BE",
        "BG",
        "HR",
        "CY",
        "CZ",
        "DK",
        "EE",
        "FI",
        "FR",
        "DE",
        "GR",
        "HU",
        "IE",
        "IT",
        "LV",
        "LT",
        "LU",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SK",
        "SI",
        "ES",
        "SE",
    }
)

EU_OBSERVATION_VERSION = "1"
_CAVEAT = (
    "This informational classification does not establish nationality, "
    "identity, physical presence, work eligibility, or fraud."
)


def classify_eu_observations(
    candidates: tuple[Candidate, ...],
    facts: tuple[Fact, ...],
    scoring_signals: tuple[ScoringSignal, ...],
    *,
    ruleset_version: str,
) -> tuple[Observation, ...]:
    claim = _unique_claim(candidates, facts)
    phone = _unique_phone_aggregate(
        candidates,
        facts,
        scoring_signals,
        ruleset_version=ruleset_version,
    )
    observations: list[Observation] = []

    if claim is not None and claim.value not in EU_27_ISO2:
        observations.append(
            _observation(
                kind=ObservationKind.STATED_LOCATION_OUTSIDE_EU,
                subject_ids=(str(claim.id),),
                values=(claim.value,),
                evidence=claim.provenance.evidence,
                reason=f"The unique code-owned stated-location country is outside the EU-27 set. {_CAVEAT}",
            )
        )
        if claim.resolved_level == "locality":
            observations.append(
                _observation(
                    kind=ObservationKind.SMALL_LOCALITY_NOT_EVALUATED,
                    subject_ids=(str(claim.id),),
                    values=(claim.resolved_name or claim.value,),
                    evidence=claim.provenance.evidence,
                    reason=(
                        "V1 has no calibrated rule for locality size, so no "
                        f"size-based assessment is made. {_CAVEAT}"
                    ),
                )
            )

    if phone is not None and phone.value not in EU_27_ISO2:
        observations.append(
            _observation(
                kind=ObservationKind.PHONE_OUTSIDE_EU,
                subject_ids=tuple(str(value) for value in phone.supporting_fact_ids),
                values=(phone.value,),
                evidence=phone.provenance.evidence,
                reason=f"The aggregate person-owned phone country is outside the EU-27 set. {_CAVEAT}",
            )
        )

    if claim is not None and phone is not None:
        claim_in_eu = claim.value in EU_27_ISO2
        phone_in_eu = phone.value in EU_27_ISO2
        subject_ids = (str(claim.id), *(str(value) for value in phone.supporting_fact_ids))
        evidence = _stable_evidence((*claim.provenance.evidence, *phone.provenance.evidence))
        values = (f"claimed:{claim.value}", f"phone:{phone.value}")
        if not claim_in_eu and not phone_in_eu:
            observations.append(
                _observation(
                    kind=ObservationKind.COMBINED_LOCATION_OUTSIDE_EU,
                    subject_ids=subject_ids,
                    values=values,
                    evidence=evidence,
                    reason=(
                        "Two distinct code-owned categories, unique stated location "
                        f"and aggregate person-owned phone country, are outside the EU-27 set. {_CAVEAT}"
                    ),
                )
            )
        elif claim_in_eu and phone_in_eu:
            observations.append(
                _observation(
                    kind=ObservationKind.COMBINED_LOCATION_INSIDE_EU,
                    subject_ids=subject_ids,
                    values=values,
                    evidence=evidence,
                    reason=(
                        "The unique stated-location and aggregate person-owned "
                        f"phone countries are in the EU-27 set. {_CAVEAT}"
                    ),
                )
            )
        elif claim_in_eu != phone_in_eu:
            observations.append(
                _observation(
                    kind=ObservationKind.MIXED_EU_LOCATION_EVIDENCE,
                    subject_ids=subject_ids,
                    values=values,
                    evidence=evidence,
                    reason=(
                        "The unique stated-location and aggregate person-owned phone "
                        f"categories fall on different sides of the EU-27 set. {_CAVEAT}"
                    ),
                )
            )

    return tuple(observations)


def _unique_claim(
    candidates: tuple[Candidate, ...],
    facts: tuple[Fact, ...],
) -> Fact | None:
    claims = tuple(
        fact
        for fact in facts
        if fact.kind is FactKind.CLAIMED_LOCATION
        and fact.subject is Subject.PERSON
        and fact.provenance.authority is Authority.CODE
    )
    if len(claims) != 1:
        return None
    claim = claims[0]
    return claim if claimed_location_graph_is_valid(candidates, claim) else None


def _unique_phone_aggregate(
    candidates: tuple[Candidate, ...],
    facts: tuple[Fact, ...],
    signals: tuple[ScoringSignal, ...],
    *,
    ruleset_version: str,
) -> ScoringSignal | None:
    phones = tuple(
        signal
        for signal in signals
        if signal.kind is ScoringSignalKind.PHONE_COUNTRY
        and signal.rule_id == PHONE_RULE_ID
    )
    if len(phones) != 1:
        return None
    phone = phones[0]
    return (
        phone
        if phone_signal_graph_is_valid(
            candidates,
            facts,
            phone,
            expected_ruleset_version=ruleset_version,
        )
        else None
    )


def _observation(
    *,
    kind: ObservationKind,
    subject_ids: tuple[str, ...],
    values: tuple[str, ...],
    evidence: tuple[Evidence, ...],
    reason: str,
) -> Observation:
    return Observation(
        id=ObservationId(f"observation:{kind.value}"),
        kind=kind,
        status=ObservationStatus.INFORMATIONAL,
        subject_ids=subject_ids,
        values=values,
        reason=reason,
        provenance=Provenance(
            authority=Authority.CODE,
            evidence=evidence,
            extractor=ComponentVersion(
                "eu-location-observations", EU_OBSERVATION_VERSION
            ),
            reference_data=ComponentVersion(
                EU_MEMBER_STATES_NAME,
                EU_MEMBER_STATES_VERSION,
                EU_MEMBER_STATES_SOURCE_URL,
            ),
        ),
    )


def _stable_evidence(values: tuple[Evidence, ...]) -> tuple[Evidence, ...]:
    by_span = {
        (value.page_number, value.page_id, value.start_offset, value.end_offset): value
        for value in values
    }
    return tuple(by_span[key] for key in sorted(by_span))
