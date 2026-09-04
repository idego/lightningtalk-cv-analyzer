from __future__ import annotations

from copy import deepcopy
from typing import Any

from cv_validator.analysis import validate_analysis_report
from cv_validator.pipeline import PipelineResult


def serialize_analysis_payload(
    result: PipelineResult,
    *,
    analysis_id: str,
) -> dict[str, Any]:
    payload = deepcopy(result.report)
    payload["analysis_id"] = analysis_id
    return validate_analysis_report(payload)


def deserialize_analysis_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_analysis_report(payload)
