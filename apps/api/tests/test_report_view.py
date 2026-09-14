from __future__ import annotations

import copy

from conftest import valid_report

from cv_validator.api.report_view import public_report_view


def test_public_view_strips_telemetry_but_keeps_rendered_fields() -> None:
    report = valid_report()
    report["analysis_id"] = "analysis-1"
    report["base_analysis"]["review"]["coverage_gaps"] = [{"field": "summary"}]
    report["base_analysis"]["review"]["annotations"] = [{"record_id": "employment-1", "kind": "duplicate", "reason_code": "x"}]
    report["base_analysis"]["pass_statuses"]["employment"] = {
        **report["base_analysis"]["pass_statuses"]["analysis"],
        "section_status": "completed_with_records",
    }
    original = copy.deepcopy(report)

    view = public_report_view(report)

    assert report == original, "stored payload must not be mutated"
    for key in ("versions", "usage", "limitations"):
        assert key not in view
    assert set(view["source"]) == {"format", "conversion_status", "block_count"}
    assert view["base_analysis"]["pass_statuses"] == {
        "analysis": {"status": "completed"},
        "employment": {"status": "completed", "section_status": "completed_with_records"},
    }
    review = view["base_analysis"]["review"]
    for key in ("rejected", "conflicts", "merge_projections", "relation_corrections"):
        assert key not in review
    assert review["coverage_gaps"] == [{"field": "summary"}]
    assert review["annotations"][0]["record_id"] == "employment-1"
    assert review["accepted_ids"] == original["base_analysis"]["review"]["accepted_ids"]
    # Rendered content is untouched.
    assert view["analysis_id"] == "analysis-1"
    assert view["base_analysis"]["profile"] == original["base_analysis"]["profile"]
    assert view["base_analysis"]["employment"] == original["base_analysis"]["employment"]
    assert view["mechanical"] == original["mechanical"]
    assert view["strategy"] == original["strategy"]
