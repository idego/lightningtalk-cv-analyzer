from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

MEASUREMENT_SCHEMA_VERSION = "v1-hardening-measurement-v1"


def summarize_measurements(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        raise ValueError("at least one measurement is required")
    modes = Counter(str(item["mode"]) for item in records)
    latencies = [float(item["latency_seconds"]) for item in records]
    return {
        "schema_version": MEASUREMENT_SCHEMA_VERSION,
        "sample_count": len(records),
        "modes": dict(modes),
        "latency_seconds": {"total": sum(latencies), "mean": mean(latencies), "max": max(latencies)},
        "failures": sum(1 for item in records if item["status"] != "succeeded"),
        "tokens": {
            "input": sum(int(item.get("input_tokens") or 0) for item in records),
            "output": sum(int(item.get("output_tokens") or 0) for item in records),
        },
        "web_searches": sum(int(item.get("web_searches") or 0) for item in records),
        "cache": {
            "hits": sum(1 for item in records if item.get("cache") == "hit"),
            "misses": sum(1 for item in records if item.get("cache") == "miss"),
        },
        "estimated_cost_usd": sum(float(item.get("estimated_cost_usd") or 0) for item in records),
        "evidence_kind": sorted({str(item["evidence_kind"]) for item in records}),
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
