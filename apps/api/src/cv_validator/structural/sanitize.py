from __future__ import annotations

from typing import Any

from cv_validator.structural.domain import StructuralAuditResult

_TOP = {"contract_version", "status", "snapshot_month", "coverage", "timeline", "visibility"}
_VISIBILITY_OBSERVATION = {"id", "kind", "status", "confidence", "source_location", "trigger_codes", "character_count", "word_count", "redaction", "threshold_version"}


def sanitize_structural_audits(payload: Any) -> dict[str, Any] | None:
    if payload is None:
        return None
    if not isinstance(payload, dict) or set(payload) != _TOP:
        return None
    try:
        observations = payload["visibility"]["observations"]
        if not isinstance(observations, list) or any(set(item) != _VISIBILITY_OBSERVATION for item in observations):
            return None
        return StructuralAuditResult.from_dict(payload).to_dict()
    except (KeyError, TypeError, ValueError):
        return None
