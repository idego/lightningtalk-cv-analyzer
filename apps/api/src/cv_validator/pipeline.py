from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cv_validator.ai.application import DocumentAnalyzer, run_document_analysis
from cv_validator.ai.config import AISettings
from cv_validator.ai.domain import (
    AIAnalysisStatus,
    AIDocumentAnalysisOutcome,
)
from cv_validator.config import (
    IngestionConfig,
    WeightsConfig,
    load_ingestion_config,
    load_weights,
)
from cv_validator.domain import DeterministicAnalysisResult, Report
from cv_validator.extraction.deterministic import analyze_deterministically
from cv_validator.ingestion import (
    RawDocument,
    RedactedDocument,
    RedactedDocumentIdentity,
    SourcePage,
)
from cv_validator.ingestion.redaction import redact_national_ids
from cv_validator.ingestion.router import ingest_cv
from cv_validator.ingestion.text import validate_text_sufficiency
from cv_validator.scoring.engine import score_deterministic
from cv_validator.location import LocationResolver


@dataclass(frozen=True)
class PipelineResult:
    report: Report
    deterministic: DeterministicAnalysisResult
    document_identity: RedactedDocumentIdentity
    ai_outcome: AIDocumentAnalysisOutcome
    report_language: str = "en"
    redacted_document: RedactedDocument | None = None


def analyze_cv_text(
    text: str,
    weights: WeightsConfig | None = None,
    ingestion_config: IngestionConfig | None = None,
    *,
    location_resolver: LocationResolver | None = None,
    ai_settings: AISettings | None = None,
    document_analyzer: DocumentAnalyzer | None = None,
) -> Report:
    return analyze_cv_text_result(
        text,
        weights,
        ingestion_config,
        location_resolver=location_resolver,
        ai_settings=ai_settings,
        document_analyzer=document_analyzer,
    ).report


def analyze_cv_text_result(
    text: str,
    weights: WeightsConfig | None = None,
    ingestion_config: IngestionConfig | None = None,
    *,
    location_resolver: LocationResolver | None = None,
    ai_settings: AISettings | None = None,
    document_analyzer: DocumentAnalyzer | None = None,
    report_language: str = "en",
) -> PipelineResult:
    cfg = weights or load_weights()
    parsed = RawDocument(
        pages=(SourcePage(page_id="page-0001", page_number=1, text=text),),
        source_format="text",
    )
    validate_text_sufficiency(parsed, ingestion_config or load_ingestion_config())
    return _analyze_raw(
        parsed,
        cfg,
        location_resolver,
        ai_settings,
        document_analyzer,
        report_language,
    )


def analyze_cv_bytes(
    content: bytes,
    filename: str,
    weights: WeightsConfig | None = None,
    ingestion_config: IngestionConfig | None = None,
    *,
    location_resolver: LocationResolver | None = None,
    ai_settings: AISettings | None = None,
    document_analyzer: DocumentAnalyzer | None = None,
) -> Report:
    return analyze_cv_bytes_result(
        content,
        filename,
        weights,
        ingestion_config,
        location_resolver=location_resolver,
        ai_settings=ai_settings,
        document_analyzer=document_analyzer,
    ).report


def analyze_cv_bytes_result(
    content: bytes,
    filename: str,
    weights: WeightsConfig | None = None,
    ingestion_config: IngestionConfig | None = None,
    *,
    location_resolver: LocationResolver | None = None,
    ai_settings: AISettings | None = None,
    document_analyzer: DocumentAnalyzer | None = None,
    report_language: str = "en",
) -> PipelineResult:
    cfg = weights or load_weights()
    parsed = ingest_cv(content, filename=filename, config=ingestion_config)
    return _analyze_raw(
        parsed,
        cfg,
        location_resolver,
        ai_settings,
        document_analyzer,
        report_language,
    )


def analyze_cv_file(
    path: Path,
    weights: WeightsConfig | None = None,
    ingestion_config: IngestionConfig | None = None,
    *,
    location_resolver: LocationResolver | None = None,
    ai_settings: AISettings | None = None,
    document_analyzer: DocumentAnalyzer | None = None,
) -> Report:
    content = path.read_bytes()
    return analyze_cv_bytes(
        content,
        filename=path.name,
        weights=weights,
        ingestion_config=ingestion_config,
        location_resolver=location_resolver,
        ai_settings=ai_settings,
        document_analyzer=document_analyzer,
    )


def _analyze_raw(
    parsed: RawDocument,
    weights: WeightsConfig,
    location_resolver: LocationResolver | None,
    ai_settings: AISettings | None,
    document_analyzer: DocumentAnalyzer | None,
    report_language: str = "en",
) -> PipelineResult:
    redacted = redact_national_ids(parsed)
    deterministic = analyze_deterministically(
        redacted,
        weights.version,
        location_resolver=location_resolver,
    )
    report = score_deterministic(deterministic, weights)
    selected_ai_settings = ai_settings or AISettings()
    if selected_ai_settings.enabled:
        if document_analyzer is None:
            from cv_validator.ai.openai_client import (
                OpenAIResponsesDocumentAnalyzer,
            )

            document_analyzer = OpenAIResponsesDocumentAnalyzer(
                selected_ai_settings
            )
        ai_outcome = run_document_analysis(
            selected_ai_settings,
            document_analyzer,
            redacted,
            deterministic,
            report_language=report_language,
        )
    else:
        ai_outcome = AIDocumentAnalysisOutcome(
            status=AIAnalysisStatus.DISABLED
        )
    return PipelineResult(
        report=report,
        deterministic=deterministic,
        document_identity=redacted.identity,
        ai_outcome=ai_outcome,
        report_language=report_language,
        redacted_document=redacted,
    )
