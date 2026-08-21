from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from cv_validator.config import WeightsConfig
from cv_validator.domain import (
    AgreementDirection,
    Authority,
    Band,
    ClaimedLocation,
    DeterministicAnalysisResult,
    FactKind,
    Finding,
    LocationRelation,
    Observation,
    ObservationKind,
    Report,
    RulesetVersion,
    ScoringSignal,
    ScoringSignalKind,
    SignalStrength,
    Subject,
)
from cv_validator.phone_policy import PHONE_RULE_ID, phone_signal_graph_is_valid
from cv_validator.location_policy import claimed_location_graph_is_valid


SCORING_POLICY_VERSION = "deterministic-phone-comparison-v1"


@dataclass(frozen=True)
class _WeightedComparison:
    direction: AgreementDirection
    weight: float
    strength: SignalStrength


def score_deterministic(
    deterministic: DeterministicAnalysisResult,
    weights: WeightsConfig,
) -> Report:
    claim = _project_claim(deterministic)
    weighted_findings: list[Finding] = []
    comparisons: list[_WeightedComparison] = []
    category_counts = Counter(
        (signal.kind, signal.rule_id) for signal in deterministic.scoring_signals
    )
    used_supporting_facts: set[object] = set()
    if claim.confidence != "undetermined":
        for signal in deterministic.scoring_signals:
            category = (signal.kind, signal.rule_id)
            supporting_facts = set(signal.supporting_fact_ids)
            if (
                category_counts[category] != 1
                or supporting_facts & used_supporting_facts
            ):
                continue
            finding = _phone_comparison_finding(
                signal,
                deterministic,
                claim,
                weights,
            )
            if finding is None:
                continue
            used_supporting_facts.update(supporting_facts)
            weighted_findings.append(finding)
            comparisons.append(
                _WeightedComparison(
                    direction=finding.direction,
                    weight=finding.weight,
                    strength=finding.strength,
                )
            )

    informational_findings = _informational_findings(
        deterministic.observations,
        claim,
    )
    findings = tuple((*weighted_findings, *informational_findings))
    if claim.confidence == "undetermined":
        return _deterministic_report(
            claim=claim,
            score=0,
            band=Band.GRAY,
            findings=findings,
            summary=(
                "Claimed location could not be identified; insufficient "
                "independent deterministic evidence. Gray is not a negative "
                "result and requires human review."
            ),
            weights=weights,
            comparisons=comparisons,
            deterministic=deterministic,
        )
    if len(comparisons) < weights.min_signals_for_assessment:
        score = weights.base_score
        return _deterministic_report(
            claim=claim,
            score=score,
            band=Band.GRAY,
            findings=findings,
            summary=(
                f"Only {len(comparisons)} independent deterministic evidence "
                f"category/categories are assessable; minimum "
                f"{weights.min_signals_for_assessment}. Gray means insufficient "
                "independent deterministic evidence, not a negative result, and "
                "requires human review. The compatible numeric score remains "
                "at the neutral configured base value and is not a verdict."
            ),
            weights=weights,
            comparisons=comparisons,
            deterministic=deterministic,
        )

    score = _weighted_comparison_score(comparisons, weights)
    band = _classify_comparison_band(score, comparisons, weights)
    return _deterministic_report(
        claim=claim,
        score=score,
        band=band,
        findings=findings,
        summary=_deterministic_summary(claim, score, band, comparisons),
        weights=weights,
        comparisons=comparisons,
        deterministic=deterministic,
    )


def _phone_comparison_finding(
    signal: ScoringSignal,
    deterministic: DeterministicAnalysisResult,
    claim: ClaimedLocation,
    weights: WeightsConfig,
) -> Finding | None:
    if (
        signal.kind is not ScoringSignalKind.PHONE_COUNTRY
        or signal.rule_id != PHONE_RULE_ID
        or signal.ruleset_version != weights.version
        or signal.provenance.authority is not Authority.CODE
        or not phone_signal_graph_is_valid(
            deterministic.candidates,
            deterministic.facts,
            signal,
            expected_ruleset_version=weights.version,
        )
    ):
        return None
    facts_by_id = {fact.id: fact for fact in deterministic.facts}
    supporting_facts = tuple(
        facts_by_id.get(fact_id) for fact_id in signal.supporting_fact_ids
    )
    if (
        not supporting_facts
        or any(fact is None for fact in supporting_facts)
        or any(
            fact.kind is not FactKind.PHONE_COUNTRY
            or fact.subject is not Subject.PERSON
            or fact.provenance.authority is not Authority.CODE
            or fact.value != signal.value
            for fact in supporting_facts
            if fact is not None
        )
    ):
        return None
    cfg = weights.signals["phone_country"]
    direction = (
        AgreementDirection.SUPPORTS
        if signal.value == claim.country_code
        else AgreementDirection.CONFLICTS
    )
    return Finding(
        signal="phone_country",
        strength=cfg.strength,
        observed=signal.value,
        claimed=claim.raw or claim.country_code,
        direction=direction,
        weight=cfg.weight,
        rationale=(
            "Aggregate explicitly person-owned phone country is compared with "
            "the code-owned claimed-location country"
        ),
        authority=Authority.CODE,
        evidence=signal.provenance.evidence,
        extractor_version=signal.provenance.extractor,
        reference_data_version=signal.provenance.reference_data,
        rule_id=signal.rule_id,
        score_impact="weighted",
        supporting_fact_ids=tuple(str(value) for value in signal.supporting_fact_ids),
    )


def _informational_findings(
    observations: tuple[Observation, ...],
    claim: ClaimedLocation,
) -> tuple[Finding, ...]:
    supported = {
        ObservationKind.POSTAL_COMPATIBILITY: "postal_compatibility",
        ObservationKind.RIGHT_TO_WORK: "right_to_work",
        ObservationKind.NATIONAL_ID: "national_id",
        ObservationKind.PHONE_OUTSIDE_EU: "phone_outside_eu",
        ObservationKind.STATED_LOCATION_OUTSIDE_EU: "stated_location_outside_eu",
        ObservationKind.COMBINED_LOCATION_OUTSIDE_EU: "combined_location_outside_eu",
        ObservationKind.MIXED_EU_LOCATION_EVIDENCE: "mixed_eu_location_evidence",
        ObservationKind.SMALL_LOCALITY_NOT_EVALUATED: "small_locality_not_evaluated",
    }
    findings: list[Finding] = []
    for observation in observations:
        if observation.provenance.authority is not Authority.CODE:
            continue
        signal_name = supported.get(observation.kind)
        if signal_name is None:
            continue
        findings.append(
            Finding(
                signal=signal_name,
                strength=SignalStrength.WEAK,
                observed=", ".join(observation.values),
                claimed=claim.raw or claim.country_code,
                direction=AgreementDirection.INFORMATIONAL,
                weight=0,
                rationale=observation.reason,
                authority=Authority.CODE,
                evidence=observation.provenance.evidence,
                extractor_version=observation.provenance.extractor,
                reference_data_version=observation.provenance.reference_data,
                score_impact="none",
                supporting_fact_ids=tuple(
                    value
                    for value in observation.subject_ids
                    if value.startswith("fact:")
                ),
            )
        )
    return tuple(findings)


def _project_claim(result: DeterministicAnalysisResult) -> ClaimedLocation:
    claims = tuple(
        fact
        for fact in result.facts
        if fact.kind is FactKind.CLAIMED_LOCATION
        and fact.relation is LocationRelation.PERSON
        and fact.subject is Subject.PERSON
        and fact.provenance.authority is Authority.CODE
        and claimed_location_graph_is_valid(result.candidates, fact)
    )
    if len(claims) != 1:
        return ClaimedLocation(None, None, None, "undetermined")
    fact = claims[0]
    candidates = {candidate.id: candidate for candidate in result.candidates}
    source = candidates.get(fact.source_candidate_ids[0])
    if source is None or source.provenance.authority is not Authority.CODE:
        return ClaimedLocation(None, None, None, "undetermined")
    return ClaimedLocation(
        raw=source.value,
        country_code=fact.value,
        region=(fact.resolved_name if fact.resolved_level == "locality" else None),
        confidence="high",
    )


def _weighted_comparison_score(
    comparisons: list[_WeightedComparison],
    weights: WeightsConfig,
) -> int:
    total_weight = sum(value.weight for value in comparisons if value.weight > 0)
    if total_weight == 0:
        return weights.base_score
    support = sum(
        value.weight
        for value in comparisons
        if value.direction is AgreementDirection.SUPPORTS
    )
    conflict = sum(
        value.weight
        for value in comparisons
        if value.direction is AgreementDirection.CONFLICTS
    )
    return max(
        0,
        min(100, round(weights.base_score + ((support - conflict) / total_weight) * 50)),
    )


def _classify_comparison_band(
    score: int,
    comparisons: list[_WeightedComparison],
    weights: WeightsConfig,
) -> Band:
    conflicts = [
        value
        for value in comparisons
        if value.direction is AgreementDirection.CONFLICTS
    ]
    strong_conflicts = [
        value for value in conflicts if value.strength is SignalStrength.STRONG
    ]
    if len(strong_conflicts) >= 2 or (
        len(conflicts) >= 3 and score < weights.amber_min
    ):
        return Band.RED
    if score >= weights.green_min and not conflicts:
        return Band.GREEN
    if score >= weights.green_min and conflicts:
        return Band.AMBER if weights.borderline_bias_toward_review else Band.GREEN
    if score >= weights.amber_min:
        return Band.AMBER
    if score >= weights.red_min:
        return Band.AMBER if weights.borderline_bias_toward_review else Band.RED
    return Band.RED


def _deterministic_summary(
    claim: ClaimedLocation,
    score: int,
    band: Band,
    comparisons: list[_WeightedComparison],
) -> str:
    supports = sum(
        1 for value in comparisons if value.direction is AgreementDirection.SUPPORTS
    )
    conflicts = sum(
        1 for value in comparisons if value.direction is AgreementDirection.CONFLICTS
    )
    return (
        f"Claimed location '{claim.raw or 'unknown location'}' scored "
        f"{score}/100 ({band.value}) from {supports} supporting and "
        f"{conflicts} conflicting independent deterministic categories."
    )


def _deterministic_report(
    *,
    claim: ClaimedLocation,
    score: int,
    band: Band,
    findings: tuple[Finding, ...],
    summary: str,
    weights: WeightsConfig,
    comparisons: list[_WeightedComparison],
    deterministic: DeterministicAnalysisResult,
) -> Report:
    return Report(
        score=score,
        band=band,
        claimed_location=claim,
        findings=findings,
        summary=summary,
        disclaimer=weights.disclaimer,
        ruleset_version=RulesetVersion(
            version=weights.version,
            weights_path=weights.source_path,
            scoring_policy_version=SCORING_POLICY_VERSION,
        ),
        signal_count=len(comparisons),
        supporting_count=sum(
            1
            for value in comparisons
            if value.direction is AgreementDirection.SUPPORTS
        ),
        conflicting_count=sum(
            1
            for value in comparisons
            if value.direction is AgreementDirection.CONFLICTS
        ),
        deterministic=deterministic,
    )
