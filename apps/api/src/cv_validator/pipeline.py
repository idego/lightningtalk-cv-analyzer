from __future__ import annotations

from dataclasses import replace
from typing import Any

from cv_validator.analysis import (
    AnalysisInput,
    AnalysisStrategy,
    validate_analysis_report,
)


def analyze_cv_bytes(
    content: bytes,
    filename: str,
    *,
    strategy: AnalysisStrategy,
    report_language: str = "en",
    analysis_id: str | None = None,
    correlation_id: str | None = None,
    recorder: Any = None,
) -> dict[str, Any]:
    request = AnalysisInput.from_upload(content, filename, report_language)
    request = replace(
        request,
        analysis_id=analysis_id,
        correlation_id=correlation_id,
        recorder=recorder,
    )
    payload = strategy.analyze(request)
    _require_strategy_identity(payload, strategy, request)
    return validate_analysis_report(payload)


def _require_strategy_identity(
    payload: dict[str, Any],
    strategy: AnalysisStrategy,
    request: AnalysisInput,
) -> None:
    strategy_payload = payload.get("strategy")
    source_payload = payload.get("source")
    if strategy_payload != {"name": strategy.name, "version": strategy.version}:
        raise ValueError("analysis strategy returned a mismatched identity")
    if not isinstance(source_payload, dict):
        raise ValueError("analysis strategy omitted source identity")
    if source_payload.get("format") != request.source_format.value:
        raise ValueError("analysis strategy returned a mismatched source format")
    if source_payload.get("sha256") != request.sha256:
        raise ValueError("analysis strategy returned a mismatched input hash")
