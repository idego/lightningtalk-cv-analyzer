from __future__ import annotations

from time import perf_counter
from typing import Any, Protocol

from cv_validator.ai.config import AISettings
from cv_validator.ai.domain import (
    AIAnalysisStatus,
    AIDocumentAnalysisOutcome,
    AIFailureReason,
    AIReportComposition,
    DocumentAnalyzerResponse,
)
from cv_validator.ai.request import (
    DocumentAnalysisRequest,
    build_document_analysis_request,
)
from cv_validator.ai.validation import (
    DocumentAnalysisValidationError,
    validate_document_analysis_response,
)
from cv_validator.domain import DeterministicAnalysisResult, Report
from cv_validator.ingestion import RedactedDocument


class DocumentAnalyzerTimeoutError(TimeoutError):
    """Safe transport timeout without request or response content."""


class DocumentAnalyzerClientError(RuntimeError):
    """Safe expected transport failure without candidate content."""

    def __init__(
        self,
        *,
        retryable: bool = False,
        http_status_class: str | None = None,
        provider_request_id: str | None = None,
    ) -> None:
        super().__init__("document analyzer client error")
        self.retryable = retryable
        self.http_status_class = http_status_class
        self.provider_request_id = provider_request_id


class DocumentAnalyzer(Protocol):
    def analyze(
        self,
        request: DocumentAnalysisRequest,
    ) -> DocumentAnalyzerResponse: ...


def analyze_report_with_ai(
    settings: AISettings,
    analyzer: DocumentAnalyzer,
    document: RedactedDocument,
    report: Report,
    report_language: str = "en",
) -> AIReportComposition:
    """Run optional AI analysis without replacing any deterministic report field."""
    if report.deterministic is None:
        raise ValueError("AI report composition requires deterministic analysis")

    outcome = run_document_analysis(
        settings,
        analyzer,
        document,
        report.deterministic,
        report_language=report_language,
    )
    return AIReportComposition(
        deterministic_report=report,
        ai_outcome=outcome,
    )


def run_document_analysis(
    settings: AISettings,
    analyzer: DocumentAnalyzer,
    document: RedactedDocument,
    deterministic: DeterministicAnalysisResult,
    report_language: str = "en",
    *,
    exclusion_intervals: tuple[tuple[str, int, int], ...] = (),
    understanding_context: dict[str, Any] | None = None,
) -> AIDocumentAnalysisOutcome:
    if not settings.enabled:
        return AIDocumentAnalysisOutcome(status=AIAnalysisStatus.DISABLED)

    request = build_document_analysis_request(
        settings,
        document,
        deterministic,
        report_language=report_language,
        exclusion_intervals=exclusion_intervals,
        understanding_context=understanding_context,
    )
    attempts = 0
    transport_retries = 0
    invalid_retries = 0
    usage: dict[str, Any] = {}
    started = perf_counter()
    while attempts < settings.absolute_attempt_limit:
        attempts += 1
        try:
            response = analyzer.analyze(request)
        except DocumentAnalyzerTimeoutError:
            if transport_retries < settings.transport_retry_limit and attempts < settings.absolute_attempt_limit:
                transport_retries += 1
                continue
            return _failed(
                AIFailureReason.TIMEOUT,
                usage=usage or None,
                failure_stage="transport",
                retryable=True,
                attempt_count=attempts,
                latency_ms=(perf_counter() - started) * 1000,
            )
        except DocumentAnalyzerClientError as exc:
            if exc.retryable and transport_retries < settings.transport_retry_limit and attempts < settings.absolute_attempt_limit:
                transport_retries += 1
                continue
            return _failed(
                AIFailureReason.CLIENT_ERROR,
                usage=usage or None,
                failure_stage="transport",
                retryable=exc.retryable,
                http_status_class=exc.http_status_class,
                provider_request_id=exc.provider_request_id,
                attempt_count=attempts,
                latency_ms=(perf_counter() - started) * 1000,
            )

        usage = _merge_usage(usage, response.usage)
        if response.refused or response.payload is None:
            return _failed(
                AIFailureReason.REFUSAL,
                response_model=response.response_model,
                usage=usage,
                failure_stage="provider_response",
                retryable=False,
                attempt_count=attempts,
                latency_ms=(perf_counter() - started) * 1000,
            )

        try:
            validated = validate_document_analysis_response(
                response.payload,
                _masked_document(document, exclusion_intervals),
                understanding_context=understanding_context,
            )
        except DocumentAnalysisValidationError as exc:
            stage = str(exc).rsplit(": ", 1)[-1]
            if invalid_retries < settings.invalid_response_retry_limit and attempts < settings.absolute_attempt_limit:
                invalid_retries += 1
                continue
            return _failed(
                AIFailureReason.INVALID_RESPONSE,
                response_model=response.response_model,
                usage=usage,
                failure_stage=stage,
                retryable=True,
                attempt_count=attempts,
                latency_ms=(perf_counter() - started) * 1000,
            )

        return AIDocumentAnalysisOutcome(
            status=AIAnalysisStatus.SUCCEEDED,
            analysis=validated,
            response_model=response.response_model,
            usage=usage,
            attempt_count=attempts,
            latency_ms=(perf_counter() - started) * 1000,
        )
    raise AssertionError("AI attempt loop exhausted without outcome")


def _masked_document(document: RedactedDocument, intervals: tuple[tuple[str, int, int], ...]) -> RedactedDocument:
    if not intervals:
        return document
    from dataclasses import replace
    from cv_validator.ingestion import SourcePage
    pages = []
    for page in document.pages:
        chars = list(page.text)
        for page_id, start, end in intervals:
            if page_id == page.page_id:
                chars[max(0, start):min(len(chars), end)] = "█" * max(0, min(len(chars), end) - max(0, start))
        pages.append(SourcePage(page.page_id, page.page_number, "".join(chars)))
    return replace(document, pages=tuple(pages))


def _failed(
    reason: AIFailureReason,
    *,
    response_model: str | None = None,
    usage: dict[str, Any] | None = None,
    failure_stage: str | None = None,
    retryable: bool | None = None,
    http_status_class: str | None = None,
    provider_request_id: str | None = None,
    attempt_count: int = 0,
    latency_ms: float | None = None,
) -> AIDocumentAnalysisOutcome:
    return AIDocumentAnalysisOutcome(
        status=AIAnalysisStatus.FAILED,
        failure_reason=reason,
        response_model=response_model,
        usage=None if usage is None else dict(usage),
        failure_stage=failure_stage,
        retryable=retryable,
        http_status_class=http_status_class,
        provider_request_id=provider_request_id,
        attempt_count=attempt_count,
        latency_ms=latency_ms,
    )


def _merge_usage(total: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    merged = dict(total)
    for key, value in current.items():
        if isinstance(value, (int, float)) and isinstance(merged.get(key, 0), (int, float)):
            merged[key] = merged.get(key, 0) + value
    return merged
