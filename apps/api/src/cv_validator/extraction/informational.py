from __future__ import annotations

import re

from cv_validator.domain import (
    Authority,
    Candidate,
    CandidateKind,
    ComponentVersion,
    Observation,
    ObservationId,
    ObservationKind,
    ObservationStatus,
    Provenance,
)
from cv_validator.extraction.postal import (
    POSTAL_PATTERNS,
    POSTAL_REFERENCE_VERSION,
)


INFORMATIONAL_CLASSIFIER_VERSION = "1"


def classify_informational_candidates(
    candidates: tuple[Candidate, ...],
) -> tuple[Observation, ...]:
    observations: list[Observation] = []
    for candidate in candidates:
        if candidate.kind is CandidateKind.POSTAL:
            compatible_countries = tuple(
                sorted(
                    country_code
                    for country_code, pattern in POSTAL_PATTERNS.items()
                    if re.fullmatch(pattern, candidate.value, re.IGNORECASE)
                )
            )
            observations.append(
                _observation(
                    candidate,
                    ObservationKind.POSTAL_COMPATIBILITY,
                    compatible_countries,
                    (
                        "Postal format is compatible with the listed countries; "
                        "it does not prove the candidate's physical location"
                    ),
                    reference_data=POSTAL_REFERENCE_VERSION,
                )
            )
        elif candidate.kind is CandidateKind.RIGHT_TO_WORK:
            observations.append(
                _observation(
                    candidate,
                    ObservationKind.RIGHT_TO_WORK,
                    (candidate.value,),
                    (
                        "Right-to-work statement is informational and does not "
                        "prove location or work eligibility"
                    ),
                )
            )
        elif candidate.kind is CandidateKind.NATIONAL_ID:
            observations.append(
                _observation(
                    candidate,
                    ObservationKind.NATIONAL_ID,
                    (candidate.value,),
                    "National-ID presence/type detected; raw value is not retained",
                )
            )
    return tuple(observations)


def _observation(
    candidate: Candidate,
    kind: ObservationKind,
    values: tuple[str, ...],
    reason: str,
    *,
    reference_data: ComponentVersion | None = None,
) -> Observation:
    return Observation(
        id=ObservationId(f"observation:{kind.value}:{candidate.id}"),
        kind=kind,
        status=ObservationStatus.INFORMATIONAL,
        subject_ids=(str(candidate.id),),
        values=values,
        reason=reason,
        provenance=Provenance(
            authority=Authority.CODE,
            evidence=candidate.provenance.evidence,
            extractor=ComponentVersion(
                "informational-classification",
                INFORMATIONAL_CLASSIFIER_VERSION,
            ),
            reference_data=reference_data,
        ),
    )
