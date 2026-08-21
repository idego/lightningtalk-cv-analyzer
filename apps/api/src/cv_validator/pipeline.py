from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cv_validator.config import (
    IngestionConfig,
    WeightsConfig,
    load_ingestion_config,
    load_weights,
)
from cv_validator.domain import DeterministicAnalysisResult, Report
from cv_validator.extraction.claim import identify_claim
from cv_validator.extraction.deterministic import analyze_deterministically
from cv_validator.extraction.signals import extract_all_signals
from cv_validator.ingestion import (
    RawDocument,
    RedactedDocumentIdentity,
    SourcePage,
)
from cv_validator.ingestion.redaction import redact_national_ids
from cv_validator.ingestion.router import ingest_cv
from cv_validator.ingestion.text import validate_text_sufficiency
from cv_validator.scoring.engine import score_signals


@dataclass(frozen=True)
class PipelineResult:
    report: Report
    deterministic: DeterministicAnalysisResult
    document_identity: RedactedDocumentIdentity


def analyze_cv_text(
    text: str,
    weights: WeightsConfig | None = None,
    ingestion_config: IngestionConfig | None = None,
) -> Report:
    return analyze_cv_text_result(text, weights, ingestion_config).report


def analyze_cv_text_result(
    text: str,
    weights: WeightsConfig | None = None,
    ingestion_config: IngestionConfig | None = None,
) -> PipelineResult:
    cfg = weights or load_weights()
    parsed = RawDocument(
        pages=(SourcePage(page_id="page-0001", page_number=1, text=text),),
        source_format="text",
    )
    validate_text_sufficiency(parsed, ingestion_config or load_ingestion_config())
    return _analyze_raw(parsed, cfg)


def analyze_cv_bytes(
    content: bytes,
    filename: str,
    weights: WeightsConfig | None = None,
    ingestion_config: IngestionConfig | None = None,
) -> Report:
    return analyze_cv_bytes_result(content, filename, weights, ingestion_config).report


def analyze_cv_bytes_result(
    content: bytes,
    filename: str,
    weights: WeightsConfig | None = None,
    ingestion_config: IngestionConfig | None = None,
) -> PipelineResult:
    cfg = weights or load_weights()
    parsed = ingest_cv(content, filename=filename, config=ingestion_config)
    return _analyze_raw(parsed, cfg)


def analyze_cv_file(
    path: Path,
    weights: WeightsConfig | None = None,
    ingestion_config: IngestionConfig | None = None,
) -> Report:
    content = path.read_bytes()
    return analyze_cv_bytes(
        content,
        filename=path.name,
        weights=weights,
        ingestion_config=ingestion_config,
    )


def _analyze_raw(parsed: RawDocument, weights: WeightsConfig) -> PipelineResult:
    redacted = redact_national_ids(parsed)
    deterministic = analyze_deterministically(redacted, weights.version)
    claim = identify_claim(redacted)
    signals = extract_all_signals(redacted, claim, weights)
    report = score_signals(claim, signals, weights)
    return PipelineResult(
        report=report,
        deterministic=deterministic,
        document_identity=redacted.identity,
    )
