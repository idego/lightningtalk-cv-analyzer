from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class SourceFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"


class AnalysisStrategyError(RuntimeError):
    """A safe strategy failure that can be exposed as a bounded API error."""


class AnalysisStrategyUnavailable(AnalysisStrategyError):
    """No document-analysis strategy is installed in this checkout."""


@dataclass(frozen=True)
class AnalysisInput:
    content: bytes = field(repr=False)
    filename: str
    source_format: SourceFormat
    report_language: str
    sha256: str
    analysis_id: str | None = None
    correlation_id: str | None = None
    recorder: Any = field(default=None, repr=False, compare=False)

    @classmethod
    def from_upload(
        cls,
        content: bytes,
        filename: str,
        report_language: str,
    ) -> AnalysisInput:
        suffix = filename.rsplit(".", 1)[-1].casefold() if "." in filename else ""
        try:
            source_format = SourceFormat(suffix)
        except ValueError as exc:
            raise AnalysisStrategyError("unsupported_file_type") from exc
        if not content:
            raise AnalysisStrategyError("empty_upload")
        if report_language not in {"en", "pl"}:
            raise AnalysisStrategyError("unsupported_report_language")
        return cls(
            content=content,
            filename=filename,
            source_format=source_format,
            report_language=report_language,
            sha256=hashlib.sha256(content).hexdigest(),
        )


class AnalysisStrategy(Protocol):
    name: str
    version: str

    @property
    def ready(self) -> bool: ...

    @property
    def readiness_reason(self) -> str | None: ...

    def analyze(self, request: AnalysisInput) -> dict[str, Any]: ...


@dataclass(frozen=True)
class UnavailableAnalysisStrategy:
    name: str = "unavailable"
    version: str = "analysis-strategy-unavailable-v1"

    @property
    def ready(self) -> bool:
        return False

    @property
    def readiness_reason(self) -> str:
        return "analysis_strategy_unavailable"

    def analyze(self, request: AnalysisInput) -> dict[str, Any]:
        del request
        raise AnalysisStrategyUnavailable("analysis_strategy_unavailable")
