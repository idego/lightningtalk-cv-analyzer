from __future__ import annotations

from cv_validator.usage import PricingCatalog, normalize_usage


class _Usage:
    def model_dump(self):
        return {
            "input_tokens": 1_000,
            "input_tokens_details": {"cached_tokens": 400},
            "output_tokens": 200,
            "total_tokens": 1_200,
        }


def test_sdk_usage_preserves_cached_tokens_and_decimal_cost() -> None:
    usage = normalize_usage(_Usage())
    catalog = PricingCatalog.from_payload({
        "version": "test-rates-v1",
        "models": {
            "gpt-5.6-luna": {
                "input_usd_per_million": "0.20",
                "cached_input_usd_per_million": "0.02",
                "output_usd_per_million": "1.20",
            }
        },
    })

    assert usage == {
        "input_tokens": 1_000,
        "cached_input_tokens": 400,
        "output_tokens": 200,
        "total_tokens": 1_200,
    }
    assert catalog.estimate("gpt-5.6-luna", usage).estimated_cost_usd == "0.000368000"


def test_unknown_model_retains_tokens_and_marks_cost_unavailable() -> None:
    usage = normalize_usage({"input_tokens": 7, "output_tokens": 3})
    estimate = PricingCatalog("rates-v1", {}).estimate("unknown-model", usage)

    assert usage["total_tokens"] == 10
    assert estimate.estimated_cost_usd is None
    assert estimate.unavailable_reason == "pricing_unavailable_for_model"
