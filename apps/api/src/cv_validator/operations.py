from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from time import perf_counter
from typing import Any

logger = logging.getLogger("cv_validator.operations")


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


def safe_log(event: str, **fields: Any) -> None:
    allowed = {"event": event}
    for key in ("correlation_id", "analysis_id", "category", "outcome", "status_code", "duration_ms", "error_code", "reason"):
        value = fields.get(key)
        if isinstance(value, (str, int, float)):
            allowed[key] = value
    logger.info(json.dumps(allowed, sort_keys=True, separators=(",", ":")))


def timer() -> float:
    return perf_counter()
