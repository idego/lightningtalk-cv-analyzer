"""Browser-facing projection of a stored analysis report.

The persisted report keeps full telemetry for diagnostics and feedback
materialization. The browser only renders the analysis itself, so the
response boundary drops model identifiers, token usage, latency, retry
counts, internal failure reasons, the source digest, and review internals
that no UI component reads. Stored payloads are never modified.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_REPORT_TELEMETRY_KEYS = ("versions", "usage", "limitations")
_SOURCE_INTERNAL_KEYS = ("sha256", "identity")
_PASS_STATUS_PUBLIC_KEYS = ("status", "section_status")
_REVIEW_INTERNAL_KEYS = (
    "rejected",
    "conflicts",
    "merge_projections",
    "relation_corrections",
)


def public_report_view(report: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``report`` with internal telemetry removed."""
    view = deepcopy(report)
    for key in _REPORT_TELEMETRY_KEYS:
        view.pop(key, None)
    source = view.get("source")
    if isinstance(source, dict):
        for key in _SOURCE_INTERNAL_KEYS:
            source.pop(key, None)
    base = view.get("base_analysis")
    if isinstance(base, dict):
        passes = base.get("pass_statuses")
        if isinstance(passes, dict):
            base["pass_statuses"] = {
                name: {key: value[key] for key in _PASS_STATUS_PUBLIC_KEYS if key in value}
                for name, value in passes.items()
                if isinstance(value, dict)
            }
        review = base.get("review")
        if isinstance(review, dict):
            for key in _REVIEW_INTERNAL_KEYS:
                review.pop(key, None)
    return view
