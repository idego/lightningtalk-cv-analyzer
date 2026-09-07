from __future__ import annotations

from cv_validator.usage import PricingCatalog, normalize_usage


class _Usage:
    def model_dump(self):
        return {
            "input_tokens": 1_000,
            "input_tokens_details": {"cached_tokens": 400},
            "output_tokens": 200,
            "output_tokens_details": {"reasoning_tokens": 75},
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
        "cache_write_input_tokens": 0,
        "output_tokens": 200,
        "reasoning_output_tokens": 75,
        "total_tokens": 1_200,
    }
    assert catalog.estimate("gpt-5.6-luna", usage).estimated_cost_usd == "0.000368000"


def test_unknown_model_retains_tokens_and_marks_cost_unavailable() -> None:
    usage = normalize_usage({"input_tokens": 7, "output_tokens": 3})
    estimate = PricingCatalog("rates-v1", {}).estimate("unknown-model", usage)

    assert usage["reasoning_output_tokens"] == 0
    assert usage["total_tokens"] == 10
    assert estimate.estimated_cost_usd is None
    assert estimate.unavailable_reason == "pricing_unavailable_for_model"


def test_cache_write_tokens_are_priced_at_write_rate() -> None:
    usage = normalize_usage({
        "input_tokens": 3_000,
        "input_tokens_details": {"cached_tokens": 1_000, "cache_write_tokens": 1_500},
        "output_tokens": 100,
        "total_tokens": 3_100,
    })
    catalog = PricingCatalog.from_payload({
        "version": "test-rates-v2",
        "models": {
            "gpt-5.6-luna": {
                "input_usd_per_million": "0.20",
                "cached_input_usd_per_million": "0.02",
                "cache_write_input_usd_per_million": "0.25",
                "output_usd_per_million": "1.20",
            }
        },
    })

    assert usage["cached_input_tokens"] == 1_000
    assert usage["cache_write_input_tokens"] == 1_500
    # 500 uncached * 0.20 + 1000 cached * 0.02 + 1500 written * 0.25 + 100 output * 1.20
    assert catalog.estimate("gpt-5.6-luna", usage).estimated_cost_usd == "0.000615000"


def test_cache_write_tokens_never_exceed_uncached_input() -> None:
    usage = normalize_usage({
        "input_tokens": 1_000,
        "input_tokens_details": {"cached_tokens": 800, "cache_write_tokens": 900},
        "output_tokens": 0,
    })

    assert usage["cache_write_input_tokens"] == 200


def test_catalog_without_write_rate_bills_writes_as_uncached_input() -> None:
    usage = normalize_usage({
        "input_tokens": 2_000,
        "input_tokens_details": {"cache_write_tokens": 2_000},
        "output_tokens": 0,
    })
    catalog = PricingCatalog.from_payload({
        "version": "legacy-rates",
        "models": {"m": {"input_usd_per_million": "1", "cached_input_usd_per_million": "0.1", "output_usd_per_million": "1"}},
    })

    assert catalog.estimate("m", usage).estimated_cost_usd == "0.002000000"
