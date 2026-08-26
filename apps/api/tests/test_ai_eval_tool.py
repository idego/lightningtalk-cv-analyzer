import importlib.util
import json
import os
from pathlib import Path

import pytest

from cv_validator.ai.validation import (
    DocumentAnalysisValidationError,
    validate_document_analysis_response,
)
from cv_validator.ai.request import SCHEMA_VERSION
from cv_validator.ingestion import RawDocument, SourcePage
from cv_validator.ingestion.redaction import redact_national_ids


REPO_ROOT = (
    Path(os.environ["CV_VALIDATOR_REPO_ROOT"])
    if "CV_VALIDATOR_REPO_ROOT" in os.environ
    else Path(__file__).parents[3]
)
SCRIPT = REPO_ROOT / "scripts/eval_ai_document.py"
SPEC = importlib.util.spec_from_file_location("eval_ai_document", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def evidence(excerpt="source evidence", page_id="page-0001"):
    return {"page_id": page_id, "excerpt": excerpt}


def model_evidence(page_id="page-0001", line_id="page-0001-line-0001"):
    return {"page_id": page_id, "line_id": line_id}


def valid_result():
    return {
        "schema_version": SCHEMA_VERSION,
        "facts": {
            "contact": [{"kind": "phone", "value": "source evidence", "status": "present", "evidence": [model_evidence()]}],
            "education": [],
            "employment": [],
        },
        "findings": [],
        "unknowns": [],
        "analysis_limitations": ["Flattened input."],
    }


def test_validate_result_uses_full_json_schema():
    result = valid_result()
    result["facts"]["contact"][0]["unexpected"] = True

    errors = MODULE.validate_result(result, {"page-0001": "source evidence"})

    assert errors == ["AI document analysis response failed validation: schema"]


def test_schema_invalid_fact_shape_fails_closed_without_eval_crash():
    result = valid_result()
    result["facts"] = ["malformed"]

    materialized, errors = MODULE.validate_and_materialize_result(
        result,
        {"page-0001": "source evidence"},
    )
    metrics = MODULE.score(
        {"expected_findings": [], "forbidden_output_terms": []},
        materialized,
        {"page-0001": "source evidence"},
        errors,
    )

    assert errors == ["AI document analysis response failed validation: schema"]
    assert metrics["schema_validity"] == 0.0


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


def test_validate_result_rejects_unknown_source_line():
    result = valid_result()
    result["facts"]["contact"][0]["evidence"][0]["line_id"] = (
        "page-0001-line-9999"
    )

    errors = MODULE.validate_result(result, {"page-0001": "source evidence"})

    assert errors == []
    materialized, errors = MODULE.validate_and_materialize_result(
        result,
        {"page-0001": "source evidence"},
    )
    assert errors == []
    assert materialized["validation_warnings"]


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


def test_score_reports_exactness_for_all_evidence_sections():
    case = {"expected_findings": [], "forbidden_output_terms": []}
    result = valid_result()
    result["findings"] = [
        {
            "category": "document_artifact",
            "evidence": [evidence("source evidence")],
        }
    ]
    result["facts"]["contact"][0]["evidence"] = [evidence("invented fact")]
    result["research_candidates"] = [
        {
            "category": "company",
            "evidence": evidence("source evidence"),
        }
    ]

    metrics = MODULE.score(case, result, {"page-0001": "source evidence"})

    assert metrics["finding_evidence_exact_match_count"] == 1
    assert metrics["finding_evidence_item_count"] == 1
    assert metrics["all_evidence_exact_match_count"] == 2
    assert metrics["all_evidence_item_count"] == 3
    assert metrics["invalid_evidence_item_count"] == 1
    assert metrics["all_evidence_exact_match_accuracy_page_aware"] == pytest.approx(
        2 / 3
    )


def test_one_finding_cannot_satisfy_two_expected_findings():
    case = {
        "expected_findings": [
            {"category": "timeline_overlap", "evidence_contains": "2020"},
            {"category": "timeline_overlap", "evidence_contains": "2021"},
        ],
        "forbidden_output_terms": [],
    }
    result = {
        "findings": [
            {
                "category": "timeline_overlap",
                "status": "conflicting",
                "evidence": [evidence("2020-2021")],
            }
        ]
    }

    metrics = MODULE.score(case, result, {"page-0001": "2020-2021"})

    assert metrics["matched_expected_count"] == 1
    assert metrics["recall"] == 0.5
    assert metrics["unexpected_finding_indices"] == []


def test_expected_missing_finding_can_match_status_without_arbitrary_excerpt():
    case = {
        "expected_findings": [
            {"category": "missing_contact_data", "status": "missing"}
        ],
        "forbidden_output_terms": [],
    }
    result = {
        "findings": [
            {
                "category": "missing_contact_data",
                "status": "missing",
                "evidence": [evidence("contact block")],
            }
        ]
    }

    metrics = MODULE.score(case, result, {"page-0001": "contact block"})

    assert metrics["recall"] == 1.0
    assert metrics["unexpected_finding_count"] == 0


def test_invalid_raw_line_reference_does_not_crash_scoring():
    case = {
        "expected_findings": [
            {"category": "timeline_overlap", "evidence_contains": "2020"}
        ],
        "forbidden_output_terms": [],
    }
    result = {
        "findings": [
            {
                "category": "timeline_overlap",
                "evidence": [
                    {
                        "page_id": "page-0001",
                        "line_id": "page-0001-line-9999",
                        "excerpt": None,
                    }
                ],
            }
        ]
    }

    metrics = MODULE.score(case, result, {"page-0001": "2020"})

    assert metrics["recall"] == 0.0
    assert metrics["invalid_evidence_item_count"] == 1


def test_raw_model_line_reference_is_valid_but_not_exact_before_materialization():
    case = {"expected_findings": [], "forbidden_output_terms": []}
    result = valid_result()

    metrics = MODULE.score(case, result, {"page-0001": "source evidence"})

    assert metrics["line_reference_valid_count"] == 1
    assert metrics["line_reference_item_count"] == 1
    assert metrics["all_evidence_exact_match_count"] == 1
    assert metrics["invalid_evidence_item_count"] == 0


def test_raw_model_line_reference_must_belong_to_the_cited_page():
    case = {"expected_findings": [], "forbidden_output_terms": []}
    result = valid_result()
    result["facts"]["contact"][0]["evidence"][0]["page_id"] = "page-0002"

    metrics = MODULE.score(
        case,
        result,
        {"page-0001": "source evidence", "page-0002": "other evidence"},
    )

    assert metrics["all_evidence_exact_match_count"] == 0
    assert metrics["line_reference_valid_count"] == 0
    assert metrics["invalid_evidence_item_count"] == 1


def test_finding_metrics_are_independent_of_invalid_fact_field_support():
    case = {
        "expected_findings": [
            {"category": "timeline_overlap", "evidence_contains": "2020"}
        ],
        "forbidden_output_terms": [],
    }
    result = valid_result()
    result["facts"]["education"] = [
        {
            "kind": "education",
            "institution": {
                "value": "Example University",
                "line_ids": ["page-0001-line-0001"],
            },
            "program": {
                "value": "Unsupported program",
                "line_ids": ["page-0001-line-0002"],
            },
            "study_dates": {"value": None, "line_ids": []},
            "status": "present",
        }
    ]
    result["findings"] = [
        {
            "category": "timeline_overlap",
            "status": "conflicting",
            "evidence": [model_evidence(line_id="page-0001-line-0002")],
        }
    ]

    metrics = MODULE.score(
        case,
        result,
        {"page-0001": "Example University\n2020-2021"},
    )

    assert metrics["recall"] == 1.0
    assert metrics["finding_line_reference_validity"] == 1.0
    assert metrics["fact_field_support"] == 0.5


def test_validate_then_score_preserves_raw_field_denominator():
    pages = {"page-0001": "Example University\n2020 overlap"}
    result = valid_result()
    result["facts"]["contact"] = []
    result["facts"]["education"] = [
        {
            "kind": "education",
            "institution": {
                "value": "Example University",
                "line_ids": ["page-0001-line-0001"],
            },
            "program": {
                "value": "Unsupported program",
                "line_ids": ["page-0001-line-9999"],
            },
            "study_dates": {"value": None, "line_ids": []},
            "status": "present",
        }
    ]
    result["findings"] = [
        {
            "category": "timeline_overlap",
            "status": "conflicting",
            "observation": "A timeline overlap is present.",
            "reason": "The cited entries overlap.",
            "importance": "attention",
                "confidence": "high",
                "limitation": "Only the supplied CV was analyzed.",
                "material_effect": "none",
                "affected_fact": "not_applicable",
                "evidence": [model_evidence(line_id="page-0001-line-0002")],
        }
    ]
    case = {
        "expected_findings": [
            {"category": "timeline_overlap", "evidence_contains": "2020"}
        ],
        "forbidden_output_terms": [],
    }

    materialized, errors = MODULE.validate_and_materialize_result(result, pages)
    metrics = MODULE.score(case, materialized, pages, errors)

    assert errors == []
    assert materialized["_eval_diagnostics"]["fact_field_support"] == {
        "fact_field_supported_count": 1,
        "fact_field_count": 2,
        "fact_field_support": 0.5,
    }
    assert metrics["fact_field_support"] == 0.5
    assert metrics["recall"] == 1.0
    assert metrics["finding_line_reference_validity"] == 1.0

    rescored_input = MODULE.dematerialize_code_owned_excerpts(materialized, pages)
    rescored, rescore_errors = MODULE.validate_and_materialize_result(
        rescored_input,
        pages,
    )
    assert rescore_errors == []
    assert rescored["_eval_diagnostics"]["fact_field_support"][
        "fact_field_support"
    ] == 0.5


def test_baseline_gate_rejects_unreviewed_additions_and_bad_metrics():
    report = {
        "validation_errors": [],
        "metrics": {
            "recall": 1.0,
            "unsupported_finding_count": 0,
            "unexpected_finding_count": 1,
            "unexpected_finding_indices": [1],
            "finding_evidence_exact_match_accuracy_page_aware": 1.0,
            "invalid_evidence_item_count": 0,
            "line_reference_validity": 1.0,
            "forbidden_output_hits": [],
        },
    }

    assert MODULE.baseline_is_acceptable([report]) is False

    report["manual_review"] = [
        {
            "case_id": "case-1",
            "finding_index": 1,
            "classification": "przydatne „warto wiedzieć”",
        }
    ]
    assert MODULE.baseline_is_acceptable([report]) is True

    report["metrics"]["recall"] = 0.5
    assert MODULE.baseline_is_acceptable([report]) is False


@pytest.mark.parametrize(
    "classification",
    ("duplikat", "nadinterpretacja", "artefakt parsowania/flatteningu"),
)
def test_baseline_gate_rejects_low_quality_reviewed_additions(classification):
    report = {
        "validation_errors": [],
        "metrics": {
            "recall": 1.0,
            "unsupported_finding_count": 0,
            "unexpected_finding_count": 1,
            "unexpected_finding_indices": [0],
            "finding_evidence_exact_match_accuracy_page_aware": 1.0,
            "invalid_evidence_item_count": 0,
            "line_reference_validity": 1.0,
            "forbidden_output_hits": [],
        },
        "manual_review": [
            {
                "case_id": "case-1",
                "finding_index": 0,
                "classification": classification,
            }
        ],
    }

    assert MODULE.baseline_is_acceptable([report]) is False


def test_baseline_gate_accepts_only_bounded_non_attention_noise():
    def report_with_noise(case_id, finding_index=None, importance="worth_knowing"):
        unexpected = [] if finding_index is None else [finding_index]
        report = {
            "validation_errors": [],
            "metrics": {
                "recall": 1.0,
                "unsupported_finding_count": 0,
                "unexpected_finding_count": len(unexpected),
                "unexpected_finding_indices": unexpected,
                "finding_evidence_exact_match_accuracy_page_aware": 1.0,
                "invalid_evidence_item_count": 0,
                "line_reference_validity": 1.0,
                "forbidden_output_hits": [],
            },
            "result": {
                "findings": [
                    {"importance": importance}
                    for _ in range((finding_index or 0) + 1)
                ]
            },
        }
        if finding_index is not None:
            report["manual_review"] = [
                {
                    "case_id": case_id,
                    "finding_index": finding_index,
                    "classification": "noise",
                }
            ]
        return report

    accepted = [
        report_with_noise("case-1", 0),
        report_with_noise("case-2", 0),
        report_with_noise("case-3"),
        report_with_noise("case-4"),
    ]
    assert MODULE.baseline_is_acceptable(accepted) is True

    over_budget = accepted.copy()
    over_budget[2] = report_with_noise("case-3", 0)
    assert MODULE.baseline_is_acceptable(over_budget) is False

    attention_noise = accepted.copy()
    attention_noise[0] = report_with_noise("case-1", 0, "attention")
    assert MODULE.baseline_is_acceptable(attention_noise) is False


def test_summary_uses_micro_recall_and_micro_evidence_accuracy():
    reports = [
        {
            "validation_errors": [],
            "latency_seconds": 1.0,
            "estimated_cost_usd": 0.01,
            "metrics": {
                "expected_count": 2,
                "matched_expected_count": 1,
                "recall": 0.5,
                "unsupported_finding_count": 0,
                "unexpected_finding_count": 0,
                "unexpected_finding_indices": [],
                "finding_evidence_exact_match_count": 1,
                "finding_evidence_item_count": 1,
                "all_evidence_exact_match_count": 2,
                "all_evidence_item_count": 2,
                "invalid_evidence_item_count": 0,
                "finding_evidence_exact_match_accuracy_page_aware": 1.0,
                "all_evidence_exact_match_accuracy_page_aware": 1.0,
                "forbidden_output_hits": [],
            },
        },
        {
            "validation_errors": ["invalid"],
            "latency_seconds": 1.0,
            "estimated_cost_usd": 0.01,
            "metrics": {
                "expected_count": 0,
                "matched_expected_count": 0,
                "recall": 1.0,
                "unsupported_finding_count": 0,
                "unexpected_finding_count": 0,
                "unexpected_finding_indices": [],
                "finding_evidence_exact_match_count": 1,
                "finding_evidence_item_count": 3,
                "all_evidence_exact_match_count": 1,
                "all_evidence_item_count": 3,
                "invalid_evidence_item_count": 2,
                "finding_evidence_exact_match_accuracy_page_aware": 1 / 3,
                "all_evidence_exact_match_accuracy_page_aware": 1 / 3,
                "forbidden_output_hits": [],
            },
        },
    ]

    summary = MODULE.summarize(reports)

    assert summary["expected_finding_micro_recall"] == 0.5
    assert summary["accepted_expected_finding_micro_recall"] == 0.5
    assert summary["finding_evidence_exact_match_accuracy_page_aware"] == 0.5
    assert summary["all_evidence_exact_match_accuracy_page_aware"] == pytest.approx(
        3 / 5
    )


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
    saved_result, errors = MODULE.validate_and_materialize_result(
        valid_result(), {"page-0001": "source evidence"}
    )
    assert errors == []
    report = {
        "cases": [{
            "case_id": "case-1",
            "latency_seconds": 1.0,
            "estimated_cost_usd": None,
            "validation_errors": ["stale"],
            "metrics": {},
            "result": saved_result,
        }]
    }

    rescored = MODULE.rescore_report(report, manifest, manifest_path)

    assert rescored["cases"][0]["validation_errors"] == []
    assert rescored["summary"]["valid_case_count"] == 1
    assert rescored["summary"]["recall_is_not_precision"] is True
    assert rescored["summary"]["finding_evidence_exact_match_accuracy_page_aware"] == 1.0


def test_rescore_does_not_trust_a_tampered_materialized_excerpt(
    tmp_path,
    monkeypatch,
):
    private_root = tmp_path / "data" / "ai-eval"
    private_root.mkdir(parents=True)
    (private_root / "source.txt").write_text("source evidence", encoding="utf-8")
    (private_root / "observations.json").write_text(
        json.dumps(
            {
                "contract_version": "deterministic-observations-v1",
                "deterministic_ruleset_version": "1.0.0",
                "observations": [],
            }
        ),
        encoding="utf-8",
    )
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
    manifest_path = private_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(MODULE, "PRIVATE_EVAL_ROOT", private_root.resolve())
    saved_result, errors = MODULE.validate_and_materialize_result(
        valid_result(), {"page-0001": "source evidence"}
    )
    assert errors == []
    saved_result["facts"]["contact"][0]["evidence"][0]["excerpt"] = "tampered"
    report = {
        "cases": [
            {
                "case_id": "case-1",
                "latency_seconds": 1.0,
                "estimated_cost_usd": None,
                "validation_errors": [],
                "metrics": {},
                "result": saved_result,
            }
        ]
    }

    rescored = MODULE.rescore_report(report, manifest, manifest_path)

    assert rescored["cases"][0]["validation_errors"] == [
        "AI document analysis response failed validation: schema"
    ]


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
    assert "<!-- line: page-0001-line-0001 -->" in loaded.request_text
    assert "<!-- line: page-0002-line-0001 -->" in loaded.request_text
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
