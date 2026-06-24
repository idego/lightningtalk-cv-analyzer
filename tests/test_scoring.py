from pathlib import Path

import pytest

from cv_validator.config import load_weights
from cv_validator.domain import Band
from cv_validator.pipeline import analyze_cv_text
from cv_validator.scoring.engine import score_signals
from cv_validator.domain import AgreementDirection, Signal, SignalStrength


FIXTURES = Path(__file__).parent.parent / "fixtures" / "calibration"


def test_consistent_cv_scores_high():
    text = (FIXTURES / "consistent_berlin.txt").read_text()
    report = analyze_cv_text(text)
    assert report.band in {Band.GREEN, Band.AMBER}
    assert report.conflicting_count == 0


def test_mismatch_cv_flags_conflict():
    text = (FIXTURES / "mismatch_us_phone.txt").read_text()
    report = analyze_cv_text(text)
    assert report.conflicting_count >= 1
    assert report.band in {Band.AMBER, Band.RED}


def test_sparse_cv_is_gray():
    text = (FIXTURES / "sparse_cv.txt").read_text()
    report = analyze_cv_text(text)
    assert report.band == Band.GRAY


def test_reproducibility():
    text = (FIXTURES / "consistent_berlin.txt").read_text()
    weights = load_weights()
    first = analyze_cv_text(text, weights=weights)
    second = analyze_cv_text(text, weights=weights)
    assert first.to_dict() == second.to_dict()


def test_strong_conflict_dominates_weak_pool():
    weights = load_weights()
    weak_support_total = sum(
        cfg.weight for name, cfg in weights.signals.items() if cfg.strength.value == "weak"
    )
    strong_phone = weights.signals["phone_country"].weight
    assert strong_phone > weak_support_total


def test_borderline_bias_toward_review():
    weights = load_weights()
    signals = [
        Signal("phone_country", SignalStrength.STRONG, "US", "US", AgreementDirection.CONFLICTS, 35, ""),
        Signal("email_tld", SignalStrength.WEAK, ".de", "DE", AgreementDirection.SUPPORTS, 3, ""),
    ]
    from cv_validator.domain import ClaimedLocation

    claim = ClaimedLocation("Berlin, Germany", "DE", None, "high")
    report = score_signals(claim, signals, weights)
    assert report.band in {Band.AMBER, Band.RED}
