from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from cv_validator.domain import Report


class AIAnalysisStatus(str, Enum):
    DISABLED = "disabled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AIFailureReason(str, Enum):
    TIMEOUT = "timeout"
    REFUSAL = "refusal"
    INVALID_RESPONSE = "invalid_response"
    CLIENT_ERROR = "client_error"


@dataclass(frozen=True)
class ValidatedDocumentAnalysis:
    """Schema- and source-validated AI output, separate from code-owned facts."""

    schema_version: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class DocumentAnalyzerResponse:
    payload: Any | None
    response_model: str
    usage: dict[str, Any]
    refused: bool = False


@dataclass(frozen=True)
class AIDocumentAnalysisOutcome:
    status: AIAnalysisStatus
    analysis: ValidatedDocumentAnalysis | None = None
    failure_reason: AIFailureReason | None = None
    response_model: str | None = None
    usage: dict[str, Any] | None = None
    failure_stage: str | None = None
    retryable: bool | None = None
    http_status_class: str | None = None
    provider_request_id: str | None = None
    attempt_count: int = 0
    latency_ms: float | None = None

    def __post_init__(self) -> None:
        if self.status is AIAnalysisStatus.SUCCEEDED and self.analysis is None:
            raise ValueError("successful AI outcome requires validated analysis")
        if self.status is not AIAnalysisStatus.SUCCEEDED and self.analysis is not None:
            raise ValueError("non-successful AI outcome cannot carry analysis")
        if self.status is AIAnalysisStatus.FAILED and self.failure_reason is None:
            raise ValueError("failed AI outcome requires a safe failure reason")
        if self.attempt_count < 0:
            raise ValueError("AI attempt count must not be negative")


@dataclass(frozen=True)
class AIReportComposition:
    """AI result alongside the unchanged code-owned deterministic report."""

    deterministic_report: Report
    ai_outcome: AIDocumentAnalysisOutcome
