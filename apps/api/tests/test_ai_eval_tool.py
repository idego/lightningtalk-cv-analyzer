import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[3] / "scripts/eval_ai_document.py"
SPEC = importlib.util.spec_from_file_location("eval_ai_document", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def evidence(excerpt="source evidence"):
    return {"page_id": "p1", "excerpt": excerpt}


def valid_result(excerpt="source evidence"):
    return {
        "schema_version": "document-analysis-schema-v2",
        "facts": {
            "contact": [{"kind": "phone", "value": "+48 123", "status": "present", "evidence": [evidence(excerpt)]}],
            "education": [],
            "employment": [],
        },
        "findings": [],
        "unknowns": [],
        "research_candidates": [],
        "checklist": [{"id": item, "checked": True, "issue_count": 0} for item in sorted(MODULE.CHECK_IDS)],
        "analysis_limitations": ["Flattened input."],
    }


def test_validate_result_uses_full_json_schema():
    result = valid_result()
    result["facts"]["contact"][0]["unexpected"] = True

    errors = MODULE.validate_result(result, "source evidence")

    assert any("Additional properties are not allowed" in error for error in errors)


def test_present_fact_requires_value_and_evidence():
    result = valid_result()
    del result["facts"]["contact"][0]["value"]
    result["facts"]["contact"][0]["evidence"] = []

    errors = MODULE.validate_result(result, "source evidence")

    assert any("'value' is a required property" in error for error in errors)
    assert any("should be non-empty" in error or "is too short" in error for error in errors)


def test_private_path_guard_rejects_output_outside_eval_root(tmp_path, monkeypatch):
    private_root = tmp_path / "data" / "ai-eval"
    private_root.mkdir(parents=True)
    monkeypatch.setattr(MODULE, "PRIVATE_EVAL_ROOT", private_root.resolve())

    assert MODULE.require_private_path(private_root / "result.json", "output") == (private_root / "result.json").resolve()
    with pytest.raises(ValueError, match="must stay inside"):
        MODULE.require_private_path(tmp_path / "leak.json", "output")


def test_validate_result_rejects_non_source_evidence():
    result = valid_result("invented")

    errors = MODULE.validate_result(result, "source evidence")

    assert any("exact excerpt from flattened input" in error for error in errors)


def test_score_names_finding_evidence_metric_precisely():
    case = {"expected_findings": [{"category": "timeline_overlap", "evidence_contains": "2020"}], "forbidden_output_terms": []}
    result = {"findings": [{"category": "timeline_overlap", "evidence": [evidence("2019-2020")]}]}

    metrics = MODULE.score(case, result, "2019-2020")

    assert metrics["recall"] == 1.0
    assert metrics["finding_evidence_exact_match_accuracy_flattened_input"] == 1.0
    assert "evidence_accuracy" not in metrics


def test_rescore_revalidates_stored_results_without_model_call(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("source evidence", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest = {"cases": [{"id": "case-1", "input": "source.txt", "expected_findings": [], "forbidden_output_terms": []}]}
    report = {
        "cases": [{
            "case_id": "case-1",
            "latency_seconds": 1.0,
            "estimated_cost_usd": None,
            "validation_errors": ["stale"],
            "metrics": {},
            "result": valid_result(),
        }]
    }

    rescored = MODULE.rescore_report(report, manifest, manifest_path)

    assert rescored["cases"][0]["validation_errors"] == []
    assert rescored["summary"]["valid_case_count"] == 1
    assert rescored["summary"]["recall_is_not_precision"] is True
    assert rescored["summary"]["finding_evidence_exact_match_accuracy_flattened_input"] == 1.0
