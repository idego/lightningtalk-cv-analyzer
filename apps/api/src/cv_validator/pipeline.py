from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cv_validator.analysis import (
    AnalysisInput,
    AnalysisStrategy,
    UnavailableAnalysisStrategy,
    validate_analysis_report,
)


@dataclass(frozen=True)
class PipelineResult:
    report: dict[str, Any]
    input_hash: str
    source_filename: str
    report_language: str


def analyze_cv_bytes_result(
    content: bytes,
    filename: str,
    *,
    strategy: AnalysisStrategy | None = None,
    report_language: str = "en",
) -> PipelineResult:
    request = AnalysisInput.from_upload(content, filename, report_language)
    selected_strategy = strategy or UnavailableAnalysisStrategy()
    payload = selected_strategy.analyze(request)
    _require_strategy_identity(payload, selected_strategy, request)
    return PipelineResult(
        report=validate_analysis_report(payload),
        input_hash=request.sha256,
        source_filename=filename,
        report_language=report_language,
    )


def analyze_cv_bytes(
    content: bytes,
    filename: str,
    *,
    strategy: AnalysisStrategy | None = None,
    report_language: str = "en",
) -> dict[str, Any]:
    return analyze_cv_bytes_result(
        content,
        filename,
        strategy=strategy,
        report_language=report_language,
    ).report


def analyze_cv_file(
    path: Path,
    *,
    strategy: AnalysisStrategy | None = None,
    report_language: str = "en",
) -> dict[str, Any]:
    return analyze_cv_bytes(
        path.read_bytes(),
        path.name,
        strategy=strategy,
        report_language=report_language,
    )


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
