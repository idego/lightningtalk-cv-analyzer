from __future__ import annotations

from pathlib import Path

from cv_validator.config import WeightsConfig, load_weights
from cv_validator.domain import Report
from cv_validator.extraction.claim import identify_claim
from cv_validator.extraction.signals import extract_all_signals
from cv_validator.ingestion import ParsedCV
from cv_validator.ingestion.router import ingest_cv
from cv_validator.scoring.engine import score_signals


def analyze_cv_text(text: str, weights: WeightsConfig | None = None) -> Report:
    cfg = weights or load_weights()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    from cv_validator.ingestion.regions import split_contact_and_body

    contact, body = split_contact_and_body(lines)
    parsed = ParsedCV(
        lines=tuple(lines),
        contact_region=tuple(contact),
        body_region=tuple(body),
        source_format="text",
    )
    return _analyze_parsed(parsed, cfg)


def analyze_cv_bytes(content: bytes, filename: str, weights: WeightsConfig | None = None) -> Report:
    cfg = weights or load_weights()
    parsed = ingest_cv(content, filename=filename)
    return _analyze_parsed(parsed, cfg)


def analyze_cv_file(path: Path, weights: WeightsConfig | None = None) -> Report:
    content = path.read_bytes()
    return analyze_cv_bytes(content, filename=path.name, weights=weights)


def _analyze_parsed(parsed: ParsedCV, weights: WeightsConfig) -> Report:
    claim = identify_claim(parsed)
    signals = extract_all_signals(parsed, claim, weights)
    return score_signals(claim, signals, weights)
