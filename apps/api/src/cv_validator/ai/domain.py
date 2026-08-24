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
    payload: dict[str, Any] | None
    response_model: str
    usage: dict[str, int]
    refused: bool = False


@dataclass(frozen=True)
class AIDocumentAnalysisOutcome:
    status: AIAnalysisStatus
    analysis: ValidatedDocumentAnalysis | None = None
    failure_reason: AIFailureReason | None = None
    response_model: str | None = None
    usage: dict[str, int] | None = None

    def __post_init__(self) -> None:
        if self.status is AIAnalysisStatus.SUCCEEDED and self.analysis is None:
            raise ValueError("successful AI outcome requires validated analysis")
        if self.status is not AIAnalysisStatus.SUCCEEDED and self.analysis is not None:
            raise ValueError("non-successful AI outcome cannot carry analysis")
        if self.status is AIAnalysisStatus.FAILED and self.failure_reason is None:
            raise ValueError("failed AI outcome requires a safe failure reason")


@dataclass(frozen=True)
class AIReportComposition:
    """AI result alongside the unchanged code-owned deterministic report."""

    deterministic_report: Report
    ai_outcome: AIDocumentAnalysisOutcome
