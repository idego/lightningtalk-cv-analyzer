from pathlib import Path

from cv_validator.config import load_weights
from cv_validator.domain import Band
from cv_validator.pipeline import analyze_cv_text


FIXTURES = Path(__file__).parent.parent / "fixtures" / "calibration"


def test_consistent_cv_is_gray_with_one_independent_category(location_resolver):
    text = (FIXTURES / "consistent_berlin.txt").read_text()
    report = analyze_cv_text(text, location_resolver=location_resolver)
    assert report.band is Band.GRAY
    assert report.signal_count == 1
    assert report.supporting_count == 1
    assert report.conflicting_count == 0
    assert "insufficient independent deterministic evidence" in report.summary


def test_mismatch_cv_is_gray_with_one_conflicting_category(location_resolver):
    text = (FIXTURES / "mismatch_us_phone.txt").read_text()
    report = analyze_cv_text(text, location_resolver=location_resolver)
    assert report.band is Band.GRAY
    assert report.signal_count == 1
    assert report.conflicting_count == 1
    assert "not a negative result" in report.summary


def test_sparse_cv_is_gray():
    text = (FIXTURES / "sparse_cv.txt").read_text()
    report = analyze_cv_text(text)
    assert report.band == Band.GRAY


def test_reproducibility(location_resolver):
    text = (FIXTURES / "consistent_berlin.txt").read_text()
    weights = load_weights()
    first = analyze_cv_text(
        text, weights=weights, location_resolver=location_resolver
    )
    second = analyze_cv_text(
        text, weights=weights, location_resolver=location_resolver
    )
    assert first.to_dict() == second.to_dict()
