from __future__ import annotations

from pathlib import Path

from cv_validator.config import (
    IngestionConfig,
    WeightsConfig,
    load_ingestion_config,
    load_weights,
)
from cv_validator.domain import Report
from cv_validator.extraction.claim import identify_claim
from cv_validator.extraction.signals import extract_all_signals
from cv_validator.ingestion import ParsedCV, SourcePage
from cv_validator.ingestion.router import ingest_cv
from cv_validator.ingestion.text import validate_text_sufficiency
from cv_validator.scoring.engine import score_signals


def analyze_cv_text(
    text: str,
    weights: WeightsConfig | None = None,
    ingestion_config: IngestionConfig | None = None,
) -> Report:
    cfg = weights or load_weights()
    parsed = ParsedCV(
        pages=(SourcePage(page_id="page-0001", page_number=1, text=text),),
        source_format="text",
    )
    validate_text_sufficiency(parsed, ingestion_config or load_ingestion_config())
    return _analyze_parsed(parsed, cfg)


def analyze_cv_bytes(
    content: bytes,
    filename: str,
    weights: WeightsConfig | None = None,
    ingestion_config: IngestionConfig | None = None,
) -> Report:
    cfg = weights or load_weights()
    parsed = ingest_cv(content, filename=filename, config=ingestion_config)
    return _analyze_parsed(parsed, cfg)


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


def _analyze_parsed(parsed: ParsedCV, weights: WeightsConfig) -> Report:
    claim = identify_claim(parsed)
    signals = extract_all_signals(parsed, claim, weights)
    return score_signals(claim, signals, weights)
