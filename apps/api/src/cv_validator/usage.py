from __future__ import annotations

import json
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping


DEFAULT_PRICING_VERSION = "openai-pricing-2026-09-02"
USD_PLN_FX_RATE = Decimal("3.75")
USD_PLN_FX_VERSION = "usd-pln-fixed-3.75-v1"
DEFAULT_PRICING: dict[str, Any] = {
    "version": DEFAULT_PRICING_VERSION,
    "models": {
        "gpt-5.6-luna": {
            "input_usd_per_million": "0.20",
            "cached_input_usd_per_million": "0.02",
            "output_usd_per_million": "1.20",
            "long_context_threshold": 272000,
            "long_context_input_multiplier": "2",
            "long_context_output_multiplier": "1.5",
        }
    },
}


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, Mapping) else {}
    return {}


def _non_negative_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def normalize_usage(value: Any) -> dict[str, int]:
    """Normalize Responses API usage without assuming optional detail fields."""

    usage = _mapping(value)
    details = _mapping(usage.get("input_tokens_details"))
    output_details = _mapping(usage.get("output_tokens_details"))
    input_tokens = _non_negative_int(usage.get("input_tokens"))
    cached_input_tokens = min(
        input_tokens,
        _non_negative_int(
            details.get("cached_tokens", usage.get("cached_input_tokens"))
        ),
    )
    output_tokens = _non_negative_int(usage.get("output_tokens"))
    reasoning_output_tokens = min(
        output_tokens,
        _non_negative_int(output_details.get("reasoning_tokens")),
    )
    total_tokens = _non_negative_int(usage.get("total_tokens"))
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
        "total_tokens": total_tokens,
    }


@dataclass(frozen=True)
class CostEstimate:
    estimated_cost_usd: str | None
    pricing_version: str
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class PricingCatalog:
    version: str
    models: Mapping[str, Mapping[str, Any]]

    @classmethod
    def from_payload(cls, payload: Any) -> "PricingCatalog":
        if not isinstance(payload, Mapping):
            raise ValueError("invalid_pricing_catalog")
        version = payload.get("version")
        models = payload.get("models")
        if not isinstance(version, str) or not version.strip() or not isinstance(models, Mapping):
            raise ValueError("invalid_pricing_catalog")
        return cls(version.strip(), models)

    def estimate(self, model: str | None, usage: Any) -> CostEstimate:
        normalized = normalize_usage(usage)
        if not model or model not in self.models:
            return CostEstimate(None, self.version, "pricing_unavailable_for_model")
        rates = self.models[model]
        try:
            input_rate = Decimal(str(rates["input_usd_per_million"]))
            cached_rate = Decimal(str(rates["cached_input_usd_per_million"]))
            output_rate = Decimal(str(rates["output_usd_per_million"]))
            threshold = int(rates.get("long_context_threshold", 0))
            input_multiplier = Decimal(str(rates.get("long_context_input_multiplier", "1")))
            output_multiplier = Decimal(str(rates.get("long_context_output_multiplier", "1")))
        except (KeyError, TypeError, ValueError, InvalidOperation):
            return CostEstimate(None, self.version, "invalid_pricing_configuration")
        if normalized["input_tokens"] <= threshold or threshold <= 0:
            input_multiplier = Decimal("1")
            output_multiplier = Decimal("1")
        cached = normalized["cached_input_tokens"]
        uncached = max(normalized["input_tokens"] - cached, 0)
        million = Decimal(1_000_000)
        cost = (
            Decimal(uncached) * input_rate * input_multiplier
            + Decimal(cached) * cached_rate * input_multiplier
            + Decimal(normalized["output_tokens"]) * output_rate * output_multiplier
        ) / million
        return CostEstimate(format(cost.quantize(Decimal("0.000000001")), "f"), self.version)


def usd_to_pln(cost_usd: str | None) -> str | None:
    if cost_usd is None:
        return None
    try:
        cost = Decimal(cost_usd) * USD_PLN_FX_RATE
    except (InvalidOperation, TypeError):
        return None
    return format(cost.quantize(Decimal("0.000000001")), "f")


def load_pricing_catalog() -> PricingCatalog:
    path = os.environ.get("CV_VALIDATOR_PRICING_PATH")
    if not path:
        return PricingCatalog.from_payload(DEFAULT_PRICING)
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_pricing_catalog") from exc
    return PricingCatalog.from_payload(payload)
