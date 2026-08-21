from pathlib import Path

import pytest

from cv_validator.domain import Band
from cv_validator.pipeline import analyze_cv_text

FIXTURES = Path(__file__).parent.parent / "fixtures" / "calibration"


@pytest.mark.parametrize(
    "fixture,expected_band",
    [
        ("consistent_berlin.txt", {Band.GRAY}),
        ("mismatch_us_phone.txt", {Band.GRAY}),
        ("sparse_cv.txt", {Band.GRAY}),
    ],
)
def test_e2e_bands(fixture, expected_band, location_resolver):
    text = (FIXTURES / fixture).read_text()
    report = analyze_cv_text(text, location_resolver=location_resolver)
    assert report.band in expected_band
