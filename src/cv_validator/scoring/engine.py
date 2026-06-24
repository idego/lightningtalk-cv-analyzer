from __future__ import annotations

from cv_validator.config import WeightsConfig
from cv_validator.domain import (
    AgreementDirection,
    Band,
    ClaimedLocation,
    Finding,
    Report,
    RulesetVersion,
    Signal,
)


def score_signals(
    claim: ClaimedLocation,
    signals: list[Signal],
    weights: WeightsConfig,
) -> Report:
    scorable = [s for s in signals if s.direction not in {AgreementDirection.INFORMATIONAL, AgreementDirection.AMBIGUOUS}]
    informational = [s for s in signals if s.direction in {AgreementDirection.INFORMATIONAL, AgreementDirection.AMBIGUOUS}]

    if claim.confidence == "undetermined":
        band = Band.GRAY
        score = 0
        summary = "Claimed location could not be identified; insufficient evidence for assessment."
        findings = _build_findings(claim, signals)
        return _report(claim, score, band, findings, summary, weights, scorable)

    if len(scorable) < weights.min_signals_for_assessment:
        band = Band.GRAY
        score = weights.base_score
        summary = (
            f"Only {len(scorable)} assessable signal(s) found; insufficient evidence "
            f"(minimum {weights.min_signals_for_assessment}). Routed for human review."
        )
        findings = _build_findings(claim, signals)
        return _report(claim, score, band, findings, summary, weights, scorable)

    score = _weighted_score(scorable, weights)
    band = _classify_band(score, scorable, weights)
    summary = _build_summary(claim, score, band, scorable)
    findings = _build_findings(claim, signals + informational)
    return _report(claim, score, band, findings, summary, weights, scorable)


def _weighted_score(signals: list[Signal], weights: WeightsConfig) -> int:
    if not signals:
        return weights.base_score

    total_weight = sum(s.weight for s in signals if s.weight > 0)
    if total_weight == 0:
        return weights.base_score

    support = sum(s.weight for s in signals if s.direction == AgreementDirection.SUPPORTS)
    conflict = sum(s.weight for s in signals if s.direction == AgreementDirection.CONFLICTS)
    net = support - conflict
    normalized = weights.base_score + (net / total_weight) * 50
    return max(0, min(100, round(normalized)))


def _classify_band(score: int, signals: list[Signal], weights: WeightsConfig) -> Band:
    conflicts = [s for s in signals if s.direction == AgreementDirection.CONFLICTS]
    strong_conflicts = [s for s in conflicts if s.strength.value == "strong"]

    if len(strong_conflicts) >= 2 or (len(conflicts) >= 3 and score < weights.amber_min):
        return Band.RED
    if score >= weights.green_min and not conflicts:
        return Band.GREEN
    if score >= weights.green_min and conflicts:
        # Borderline: bias toward review
        if weights.borderline_bias_toward_review:
            return Band.AMBER
        return Band.GREEN
    if score >= weights.amber_min:
        return Band.AMBER
    if score >= weights.red_min:
        return Band.AMBER if weights.borderline_bias_toward_review else Band.RED
    return Band.RED


def _build_findings(claim: ClaimedLocation, signals: list[Signal]) -> tuple[Finding, ...]:
    claimed = claim.raw or claim.country_code or "undetermined"
    findings = [
        Finding(
            signal=s.name,
            strength=s.strength,
            observed=s.observed,
            claimed=claimed,
            direction=s.direction,
            weight=s.weight,
            rationale=s.rationale,
        )
        for s in signals
    ]
    return tuple(findings)


def _build_summary(claim: ClaimedLocation, score: int, band: Band, signals: list[Signal]) -> str:
    claim_text = claim.raw or "unknown location"
    supports = sum(1 for s in signals if s.direction == AgreementDirection.SUPPORTS)
    conflicts = sum(1 for s in signals if s.direction == AgreementDirection.CONFLICTS)
    return (
        f"Claimed location '{claim_text}' scored {score}/100 ({band.value}). "
        f"{supports} supporting and {conflicts} conflicting assessable signal(s)."
    )


def _report(
    claim: ClaimedLocation,
    score: int,
    band: Band,
    findings: tuple[Finding, ...],
    summary: str,
    weights: WeightsConfig,
    scorable: list[Signal],
) -> Report:
    supporting = sum(1 for s in scorable if s.direction == AgreementDirection.SUPPORTS)
    conflicting = sum(1 for s in scorable if s.direction == AgreementDirection.CONFLICTS)
    return Report(
        score=score,
        band=band,
        claimed_location=claim,
        findings=findings,
        summary=summary,
        disclaimer=weights.disclaimer,
        ruleset_version=RulesetVersion(version=weights.version, weights_path=weights.source_path),
        signal_count=len(scorable),
        supporting_count=supporting,
        conflicting_count=conflicting,
    )
