from __future__ import annotations

from cv_validator.domain import DeterministicAnalysisResult
from cv_validator.extraction.candidates import extract_candidates
from cv_validator.extraction.phones import classify_and_aggregate_phones
from cv_validator.ingestion import RedactedDocument


def analyze_deterministically(
    document: RedactedDocument,
    ruleset_version: str,
) -> DeterministicAnalysisResult:
    candidates = extract_candidates(document)
    facts, observations, scoring_signals = classify_and_aggregate_phones(
        document,
        candidates,
        ruleset_version,
    )
    return DeterministicAnalysisResult(
        candidates=candidates,
        facts=facts,
        observations=observations,
        scoring_signals=scoring_signals,
    )
