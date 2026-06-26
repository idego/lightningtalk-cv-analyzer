from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Band(str, Enum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"
    GRAY = "gray"


class AgreementDirection(str, Enum):
    SUPPORTS = "supports"
    CONFLICTS = "conflicts"
    NEUTRAL = "neutral"
    AMBIGUOUS = "ambiguous"
    INFORMATIONAL = "informational"


class SignalStrength(str, Enum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


@dataclass(frozen=True)
class RulesetVersion:
    version: str
    weights_path: str


@dataclass(frozen=True)
class Signal:
    name: str
    strength: SignalStrength
    observed: str
    inferred_country: str | None
    direction: AgreementDirection
    weight: float
    rationale: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Finding:
    signal: str
    strength: SignalStrength
    observed: str
    claimed: str | None
    direction: AgreementDirection
    weight: float
    rationale: str


@dataclass(frozen=True)
class ClaimedLocation:
    raw: str | None
    country_code: str | None
    region: str | None
    confidence: str  # "high", "low", "undetermined"


@dataclass(frozen=True)
class Report:
    score: int
    band: Band
    claimed_location: ClaimedLocation
    findings: tuple[Finding, ...]
    summary: str
    disclaimer: str
    ruleset_version: RulesetVersion
    signal_count: int
    supporting_count: int
    conflicting_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "band": self.band.value,
            "claimed_location": {
                "raw": self.claimed_location.raw,
                "country_code": self.claimed_location.country_code,
                "region": self.claimed_location.region,
                "confidence": self.claimed_location.confidence,
            },
            "findings": [
                {
                    "signal": f.signal,
                    "strength": f.strength.value,
                    "observed": f.observed,
                    "claimed": f.claimed,
                    "direction": f.direction.value,
                    "weight": f.weight,
                    "rationale": f.rationale,
                }
                for f in self.findings
            ],
            "summary": self.summary,
            "disclaimer": self.disclaimer,
            "ruleset_version": {
                "version": self.ruleset_version.version,
                "weights_path": self.ruleset_version.weights_path,
            },
            "signal_count": self.signal_count,
            "supporting_count": self.supporting_count,
            "conflicting_count": self.conflicting_count,
        }
