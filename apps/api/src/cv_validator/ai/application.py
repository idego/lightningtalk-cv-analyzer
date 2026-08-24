from __future__ import annotations

from typing import Protocol

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
) -> AIReportComposition:
    """Run optional AI analysis without replacing any deterministic report field."""
    if report.deterministic is None:
        raise ValueError("AI report composition requires deterministic analysis")

    outcome = run_document_analysis(
        settings,
        analyzer,
        document,
        report.deterministic,
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
) -> AIDocumentAnalysisOutcome:
    if not settings.enabled:
        return AIDocumentAnalysisOutcome(status=AIAnalysisStatus.DISABLED)

    request = build_document_analysis_request(settings, document, deterministic)
    try:
        response = analyzer.analyze(request)
    except DocumentAnalyzerTimeoutError:
        return _failed(AIFailureReason.TIMEOUT)
    except DocumentAnalyzerClientError:
        return _failed(AIFailureReason.CLIENT_ERROR)

    if response.refused or response.payload is None:
        return _failed(
            AIFailureReason.REFUSAL,
            response_model=response.response_model,
            usage=response.usage,
        )

    try:
        validated = validate_document_analysis_response(response.payload, document)
    except DocumentAnalysisValidationError:
        return _failed(
            AIFailureReason.INVALID_RESPONSE,
            response_model=response.response_model,
            usage=response.usage,
        )

    return AIDocumentAnalysisOutcome(
        status=AIAnalysisStatus.SUCCEEDED,
        analysis=validated,
        response_model=response.response_model,
        usage=dict(response.usage),
    )


def _failed(
    reason: AIFailureReason,
    *,
    response_model: str | None = None,
    usage: dict[str, int] | None = None,
) -> AIDocumentAnalysisOutcome:
    return AIDocumentAnalysisOutcome(
        status=AIAnalysisStatus.FAILED,
        failure_reason=reason,
        response_model=response_model,
        usage=None if usage is None else dict(usage),
    )
