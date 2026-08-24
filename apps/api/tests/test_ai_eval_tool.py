import importlib.util
import json
from pathlib import Path

import pytest

from cv_validator.ai.validation import (
    DocumentAnalysisValidationError,
    validate_document_analysis_response,
)
from cv_validator.ingestion import RawDocument, SourcePage
from cv_validator.ingestion.redaction import redact_national_ids


SCRIPT = Path(__file__).parents[3] / "scripts/eval_ai_document.py"
SPEC = importlib.util.spec_from_file_location("eval_ai_document", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def evidence(excerpt="source evidence", page_id="page-0001"):
    return {"page_id": page_id, "excerpt": excerpt}


def valid_result(excerpt="source evidence"):
    return {
        "schema_version": "document-analysis-schema-v3",
        "facts": {
            "contact": [{"kind": "phone", "value": "+48 123", "status": "present", "authority": "ai", "source": "document_analyzer", "evidence": [evidence(excerpt)]}],
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

    errors = MODULE.validate_result(result, {"page-0001": "source evidence"})

    assert errors == ["AI document analysis response failed validation: schema"]


def test_present_fact_requires_value_and_evidence():
    result = valid_result()
    del result["facts"]["contact"][0]["value"]
    result["facts"]["contact"][0]["evidence"] = []

    errors = MODULE.validate_result(result, {"page-0001": "source evidence"})

    assert errors == ["AI document analysis response failed validation: schema"]


def test_private_path_guard_rejects_output_outside_eval_root(tmp_path, monkeypatch):
    private_root = tmp_path / "data" / "ai-eval"
    private_root.mkdir(parents=True)
    monkeypatch.setattr(MODULE, "PRIVATE_EVAL_ROOT", private_root.resolve())

    assert MODULE.require_private_path(private_root / "result.json", "output") == (private_root / "result.json").resolve()
    with pytest.raises(ValueError, match="must stay inside"):
        MODULE.require_private_path(tmp_path / "leak.json", "output")


def test_validate_result_rejects_non_source_evidence():
    result = valid_result("invented")

    errors = MODULE.validate_result(result, {"page-0001": "source evidence"})

    assert errors == [
        "AI document analysis response failed validation: exact excerpt"
    ]


@pytest.mark.parametrize("protected_conclusion", (None, "Do not interview this candidate."))
def test_runtime_and_eval_use_the_same_canonical_validation_boundary(
    protected_conclusion,
):
    pages = {"page-0001": "source evidence"}
    result = valid_result()
    if protected_conclusion is not None:
        result["analysis_limitations"] = [protected_conclusion]
    document = redact_national_ids(
        RawDocument(
            pages=(SourcePage("page-0001", 1, pages["page-0001"]),),
            source_format="text",
        )
    )

    try:
        validate_document_analysis_response(result, document)
    except DocumentAnalysisValidationError:
        runtime_accepted = False
    else:
        runtime_accepted = True
    eval_accepted = not MODULE.validate_result(result, pages)

    assert eval_accepted is runtime_accepted


def test_score_names_finding_evidence_metric_precisely():
    case = {"expected_findings": [{"category": "timeline_overlap", "evidence_contains": "2020"}], "forbidden_output_terms": []}
    result = {"findings": [{"category": "timeline_overlap", "evidence": [evidence("2019-2020")]}]}

    metrics = MODULE.score(case, result, {"page-0001": "2019-2020"})

    assert metrics["recall"] == 1.0
    assert metrics["finding_evidence_exact_match_accuracy_page_aware"] == 1.0
    assert "evidence_accuracy" not in metrics


def test_rescore_revalidates_stored_results_without_model_call(tmp_path, monkeypatch):
    private_root = tmp_path / "data" / "ai-eval"
    private_root.mkdir(parents=True)
    source = private_root / "source.txt"
    source.write_text("source evidence", encoding="utf-8")
    observations = private_root / "observations.json"
    observations.write_text(
        json.dumps(
            {
                "contract_version": "deterministic-observations-v1",
                "deterministic_ruleset_version": "1.0.0",
                "observations": [],
            }
        ),
        encoding="utf-8",
    )
    manifest_path = private_root / "manifest.json"
    manifest = {
        "cases": [
            {
                "id": "case-1",
                "pages": [{"page_id": "page-0001", "input": "source.txt"}],
                "deterministic_observations": "observations.json",
                "expected_findings": [],
                "forbidden_output_terms": [],
            }
        ]
    }
    monkeypatch.setattr(MODULE, "PRIVATE_EVAL_ROOT", private_root.resolve())
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
    assert rescored["summary"]["finding_evidence_exact_match_accuracy_page_aware"] == 1.0


def test_page_aware_eval_input_loads_private_pages_and_versioned_observations(
    tmp_path,
    monkeypatch,
):
    private_root = tmp_path / "data" / "ai-eval"
    case_root = private_root / "case-1"
    case_root.mkdir(parents=True)
    (case_root / "page-0001.txt").write_text("First page", encoding="utf-8")
    (case_root / "page-0002.txt").write_text("Second page", encoding="utf-8")
    observations = {
        "contract_version": "deterministic-observations-v1",
        "deterministic_ruleset_version": "1.0.0",
        "observations": [],
    }
    (case_root / "observations.json").write_text(
        json.dumps(observations),
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "PRIVATE_EVAL_ROOT", private_root.resolve())
    case = {
        "id": "case-1",
        "pages": [
            {"page_id": "page-0001", "input": "case-1/page-0001.txt"},
            {"page_id": "page-0002", "input": "case-1/page-0002.txt"},
        ],
        "deterministic_observations": "case-1/observations.json",
        "expected_findings": [],
        "forbidden_output_terms": [],
    }

    loaded = MODULE.load_case_input(case, private_root / "manifest.json")

    assert loaded.pages == {
        "page-0001": "First page",
        "page-0002": "Second page",
    }
    assert loaded.deterministic_observations == observations
    assert "<!-- page: page-0001 -->" in loaded.request_text
    assert "<!-- page: page-0002 -->" in loaded.request_text
    assert "deterministic-observations-v1" in loaded.request_text


def test_eval_manifest_rejects_more_than_four_cases():
    manifest = {"cases": [{"id": str(index)} for index in range(5)]}

    with pytest.raises(ValueError, match="at most 4"):
        MODULE.validate_manifest_limits(manifest)


@pytest.mark.parametrize(
    ("backend", "requested_limit", "expected"),
    (
        (
            "responses",
            4096,
            {"max_output_tokens": 4096, "output_limit_enforcement": "enforced"},
        ),
        (
            "codex",
            None,
            {
                "max_output_tokens": None,
                "output_limit_enforcement": "not_enforced",
            },
        ),
        (
            "codex",
            4096,
            {
                "max_output_tokens": None,
                "output_limit_enforcement": "not_enforced",
            },
        ),
    ),
)
def test_eval_report_metadata_states_whether_output_limit_is_enforced(
    backend,
    requested_limit,
    expected,
):
    assert MODULE.backend_output_limit_metadata(backend, requested_limit) == expected


def test_responses_backend_requires_a_positive_enforced_output_limit():
    with pytest.raises(ValueError, match="required and must be positive"):
        MODULE.backend_output_limit_metadata("responses", None)
