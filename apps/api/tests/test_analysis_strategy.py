from __future__ import annotations

import hashlib

import pytest

from conftest import valid_report
from cv_validator.analysis import AnalysisStrategyUnavailable
from cv_validator.analysis.validation import (
    AnalysisReportValidationError,
    validate_analysis_report,
)
from cv_validator.pipeline import analyze_cv_bytes_result


class FakeStrategy:
    name = "docling-luna"
    version = "docling-luna-test-v1"
    ready = True

    def analyze(self, request):
        return valid_report(
            request.sha256,
            source_format=request.source_format.value,
            strategy_name=self.name,
        )


def test_pipeline_delegates_original_upload_to_strategy() -> None:
    content = b"%PDF-1.7\ntext CV"
    result = analyze_cv_bytes_result(
        content,
        "candidate.pdf",
        strategy=FakeStrategy(),
        report_language="pl",
    )

    assert result.input_hash == hashlib.sha256(content).hexdigest()
    assert result.report["strategy"]["name"] == "docling-luna"
    assert result.report["source"]["format"] == "pdf"


def test_pipeline_rejects_unsupported_file_type_before_strategy() -> None:
    with pytest.raises(Exception, match="unsupported_file_type"):
        analyze_cv_bytes_result(b"text", "candidate.txt", strategy=FakeStrategy())


def test_pipeline_has_no_silent_fallback_strategy() -> None:
    with pytest.raises(AnalysisStrategyUnavailable, match="analysis_strategy_unavailable"):
        analyze_cv_bytes_result(b"%PDF-1.7", "candidate.pdf")


def test_reviewer_added_ids_must_match_accepted_reviewer_records() -> None:
    payload = valid_report()
    payload["base_analysis"]["review"]["added_candidate_ids"] = []

    with pytest.raises(
        AnalysisReportValidationError,
        match="review.added_candidate_ids",
    ):
        validate_analysis_report(payload)


def test_reviewer_accepted_ids_must_cover_every_accepted_record() -> None:
    payload = valid_report()
    payload["base_analysis"]["review"]["accepted_ids"] = ["employment-1"]

    with pytest.raises(
        AnalysisReportValidationError,
        match="review.accepted_ids",
    ):
        validate_analysis_report(payload)


def test_reviewer_added_profile_field_must_be_supported() -> None:
    payload = valid_report()
    payload["base_analysis"]["profile"]["summary"] = None
    payload["base_analysis"]["review"]["added_profile_fields"] = ["summary"]

    with pytest.raises(
        AnalysisReportValidationError,
        match="review.added_profile_fields",
    ):
        validate_analysis_report(payload)


def test_evidence_offsets_must_be_complete_and_non_empty() -> None:
    payload = valid_report()
    evidence = payload["base_analysis"]["profile"]["candidate_name"]["evidence"][0]
    evidence.update({"start_offset": 2, "end_offset": 2})

    with pytest.raises(AnalysisReportValidationError, match="evidence.offsets"):
        validate_analysis_report(payload)
