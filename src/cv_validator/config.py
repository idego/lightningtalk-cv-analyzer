from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from cv_validator.domain import SignalStrength


@dataclass(frozen=True)
class SignalWeightConfig:
    name: str
    strength: SignalStrength
    weight: float


@dataclass(frozen=True)
class WeightsConfig:
    version: str
    signals: dict[str, SignalWeightConfig]
    green_min: int
    amber_min: int
    red_min: int
    min_signals_for_assessment: int
    borderline_bias_toward_review: bool
    base_score: int
    disclaimer: str
    source_path: str


def _default_weights_path() -> Path:
    env_path = os.environ.get("CV_VALIDATOR_WEIGHTS_PATH")
    if env_path:
        return Path(env_path)
    return Path(__file__).resolve().parents[2] / "weights.yaml"


def load_weights(path: Path | None = None) -> WeightsConfig:
    weights_path = path or _default_weights_path()
    raw: dict[str, Any] = yaml.safe_load(weights_path.read_text(encoding="utf-8"))

    signals: dict[str, SignalWeightConfig] = {}
    for name, cfg in raw["signals"].items():
        signals[name] = SignalWeightConfig(
            name=name,
            strength=SignalStrength(cfg["strength"]),
            weight=float(cfg["weight"]),
        )

    bands = raw["bands"]
    scoring = raw["scoring"]
    return WeightsConfig(
        version=str(raw["version"]),
        signals=signals,
        green_min=int(bands["green_min"]),
        amber_min=int(bands["amber_min"]),
        red_min=int(bands["red_min"]),
        min_signals_for_assessment=int(scoring["min_signals_for_assessment"]),
        borderline_bias_toward_review=bool(scoring["borderline_bias_toward_review"]),
        base_score=int(scoring["base_score"]),
        disclaimer=str(raw["disclaimer"]).strip(),
        source_path=str(weights_path),
    )
