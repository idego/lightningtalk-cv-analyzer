from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable
from uuid import uuid4

from cv_validator.usage import (
    USD_PLN_FX_RATE,
    USD_PLN_FX_VERSION,
    PricingCatalog,
    normalize_usage,
    usd_to_pln,
)

logger = logging.getLogger("cv_validator.operations")


def configure_structured_logging() -> None:
    """Emit one JSON object per application log line in containers and tests."""

    if getattr(logger, "_cv_json_configured", False):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.handlers[:] = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger._cv_json_configured = True  # type: ignore[attr-defined]


class OperationsTelemetry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Counter[str] = Counter()
        self._latency_ms: Counter[str] = Counter()

    def request(self, route: str, status: int, duration_ms: float) -> None:
        key = f"{route}|{status}"
        with self._lock:
            self._counters[f"requests_total|{key}"] += 1
            self._latency_ms[f"request_duration_ms_total|{route}"] += round(duration_ms)

    def increment(self, name: str, **labels: str) -> None:
        suffix = "|".join(f"{key}={value}" for key, value in sorted(labels.items()))
        with self._lock:
            self._counters[f"{name}|{suffix}" if suffix else name] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"counters": dict(self._counters), "latency_ms_totals": dict(self._latency_ms)}


_SAFE_LOG_FIELDS = {
    "correlation_id",
    "analysis_id",
    "operation",
    "category",
    "provider",
    "configured_model",
    "response_model",
    "reasoning_effort",
    "attempt",
    "outcome",
    "status_code",
    "duration_ms",
    "latency_ms",
    "error_code",
    "reason",
    "raw_candidate_count",
    "evidence_valid_count",
    "accepted_count",
    "ambiguous_count",
    "rejected_count",
    "evidence_invalid_count",
    "extracted_count",
    "annotated_count",
    "corrected_count",
    "added_count",
    "suspected_hallucination_count",
    "uncertain_count",
    "research_eligible_count",
    "coverage_gaps_count",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "total_tokens",
    "cache_outcome",
}


def safe_log(event: str, **fields: Any) -> None:
    allowed = {"event": event}
    for key in _SAFE_LOG_FIELDS:
        value = fields.get(key)
        if isinstance(value, (str, int, float)):
            allowed[key] = value
    histogram = fields.get("rejection_reason_histogram")
    if isinstance(histogram, dict) and all(
        isinstance(key, str) and isinstance(value, int)
        for key, value in histogram.items()
    ):
        allowed["rejection_reason_histogram"] = histogram
    logger.info(json.dumps(allowed, sort_keys=True, separators=(",", ":")))


class AnalysisRecorder:
    """Privacy-safe sink shared by conversion, AI passes, persistence, and research."""

    def __init__(
        self,
        *,
        analysis_id: str,
        correlation_id: str,
        diagnostic_sink: Callable[[dict[str, Any]], None],
        usage_sink: Callable[[dict[str, Any]], None],
        pricing: PricingCatalog,
    ) -> None:
        self.analysis_id = analysis_id
        self.correlation_id = correlation_id
        self._diagnostic_sink = diagnostic_sink
        self._usage_sink = usage_sink
        self._pricing = pricing

    def emit(self, event: str, **fields: Any) -> None:
        payload = {
            "event": event,
            "analysis_id": self.analysis_id,
            "correlation_id": self.correlation_id,
            **{key: value for key, value in fields.items() if key in _SAFE_LOG_FIELDS or key == "rejection_reason_histogram"},
        }
        self._diagnostic_sink(payload)
        safe_log(event, **{key: value for key, value in payload.items() if key != "event"})

    def record_ai_attempt(
        self,
        *,
        operation: str,
        category: str,
        provider: str,
        configured_model: str,
        response_model: str | None,
        reasoning_effort: str,
        attempt: int,
        outcome: str,
        started_at: str,
        completed_at: str,
        latency_ms: int,
        usage: Any,
        error_code: str | None = None,
        cache_outcome: str | None = None,
        saved_usage: Any = None,
    ) -> dict[str, Any]:
        normalized = normalize_usage(usage)
        estimate = self._pricing.estimate(response_model or configured_model, normalized)
        saved = normalize_usage(saved_usage)
        saved_estimate = self._pricing.estimate(
            response_model or configured_model,
            saved,
        ) if saved_usage is not None else None
        event_key = sha256(
            "|".join((
                self.analysis_id,
                operation,
                str(attempt),
                started_at,
            )).encode("utf-8")
        ).hexdigest()
        if cache_outcome == "hit" and normalized["total_tokens"] == 0:
            billing_status = "cache_hit"
        elif normalized["total_tokens"] > 0:
            billing_status = "paid"
        elif outcome == "failed":
            billing_status = "usage_unavailable"
        else:
            billing_status = "no_usage"
        event = {
            "event_id": str(uuid4()),
            "event_key": event_key,
            "analysis_id": self.analysis_id,
            "correlation_id": self.correlation_id,
            "operation": operation,
            "category": category,
            "provider": provider,
            "configured_model": configured_model,
            "response_model": response_model,
            "reasoning_effort": reasoning_effort,
            "attempt": attempt,
            "outcome": outcome,
            "error_code": error_code,
            "started_at": started_at,
            "completed_at": completed_at,
            "latency_ms": latency_ms,
            **normalized,
            "estimated_cost_usd": estimate.estimated_cost_usd,
            "estimated_cost_pln": usd_to_pln(estimate.estimated_cost_usd),
            "pricing_version": estimate.pricing_version,
            "pricing_reason": estimate.unavailable_reason,
            "fx_rate": str(USD_PLN_FX_RATE),
            "fx_version": USD_PLN_FX_VERSION,
            "billing_status": billing_status,
            "cache_outcome": cache_outcome,
            "saved_input_tokens": saved["input_tokens"] if saved_usage is not None else 0,
            "saved_cached_input_tokens": saved["cached_input_tokens"] if saved_usage is not None else 0,
            "saved_output_tokens": saved["output_tokens"] if saved_usage is not None else 0,
            "saved_total_tokens": saved["total_tokens"] if saved_usage is not None else 0,
            "saved_cost_usd": (
                saved_estimate.estimated_cost_usd if saved_estimate is not None else None
            ),
        }
        self._usage_sink(event)
        self.emit(
            "ai_pass_completed" if outcome == "completed" else "ai_pass_failed",
            operation=operation,
            category=category,
            provider=provider,
            configured_model=configured_model,
            response_model=response_model,
            reasoning_effort=reasoning_effort,
            attempt=attempt,
            outcome=outcome,
            error_code=error_code,
            latency_ms=latency_ms,
            cache_outcome=cache_outcome,
            **normalized,
        )
        return event


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
