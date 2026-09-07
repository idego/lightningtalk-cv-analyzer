from time import perf_counter
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from cv_validator.api.app import _research_failure
from cv_validator.research.domain import CompanyResearchInvalidResponse


@pytest.mark.parametrize("reason, expected", [
    ("subject_mismatch", {"X-Research-Error-Reason": "subject_mismatch"}),
    ("private@example.test", None),
    ("PrivateCandidateName", None),
])
def test_only_known_validation_codes_reach_the_browser(reason, expected):
    with pytest.raises(HTTPException) as caught:
        _research_failure(
            Mock(), "synthetic-analysis", "company", "invalid_response", 502,
            "company_research_invalid_response", CompanyResearchInvalidResponse(reason),
            Mock(), "2026-09-07T12:00:00Z", perf_counter(),
        )
    assert caught.value.status_code == 502
    assert caught.value.detail == "company_research_invalid_response"
    assert caught.value.headers == expected
