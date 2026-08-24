from __future__ import annotations

from cv_validator.domain import DeterministicAnalysisResult
from cv_validator.extraction.candidates import extract_candidates
from cv_validator.extraction.eu_observations import classify_eu_observations
from cv_validator.extraction.email_providers import (
    classify_common_email_provider_typos,
)
from cv_validator.extraction.locations import classify_locations
from cv_validator.extraction.informational import classify_informational_candidates
from cv_validator.extraction.phones import classify_and_aggregate_phones
from cv_validator.ingestion import RedactedDocument
from cv_validator.location import LocationResolver


def analyze_deterministically(
    document: RedactedDocument,
    ruleset_version: str,
    *,
    location_resolver: LocationResolver | None = None,
) -> DeterministicAnalysisResult:
    candidates = extract_candidates(document)
    phone_facts, phone_observations, phone_signals = classify_and_aggregate_phones(
        document,
        candidates,
        ruleset_version,
    )
    informational_observations = classify_informational_candidates(candidates)
    email_provider_observations = classify_common_email_provider_typos(candidates)
    added_candidates, location_facts, location_observations, location_signals = (
        classify_locations(
            document,
            candidates,
            ruleset_version,
            location_resolver,
        )
    )
    result_candidates = tuple((*candidates, *added_candidates))
    facts = tuple((*phone_facts, *location_facts))
    scoring_signals = tuple((*phone_signals, *location_signals))
    eu_observations = classify_eu_observations(
        result_candidates,
        facts,
        scoring_signals,
        ruleset_version=ruleset_version,
    )
    return DeterministicAnalysisResult(
        ruleset_version=ruleset_version,
        candidates=result_candidates,
        facts=facts,
        observations=tuple(
            (
                *phone_observations,
                *informational_observations,
                *email_provider_observations,
                *location_observations,
                *eu_observations,
            )
        ),
        scoring_signals=scoring_signals,
    )
