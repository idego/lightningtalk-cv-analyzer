from __future__ import annotations

from io import BytesIO
from threading import Lock
from time import perf_counter, sleep

import pytest
from docx import Document
from fastapi.testclient import TestClient
from reportlab.pdfgen.canvas import Canvas

from cv_validator.analysis.candidates import apply_review, validate_specialists
from cv_validator.analysis.docling_converter import DoclingTextConverter
from cv_validator.analysis.docling_luna import DoclingLunaAnalysisStrategy
from cv_validator.analysis.luna_client import (
    ModelPassError,
    ModelPassResponse,
    OpenAIResponsesLunaClient,
)
from cv_validator.analysis.source import SourceBlock, SourceDocument
from cv_validator.analysis.strategy import AnalysisInput, AnalysisStrategyError, SourceFormat
from cv_validator.api.app import create_app
from cv_validator.openai_config import OpenAISettings


def field(field_id: str, value: str, block_id: str, excerpt: str | None = None) -> dict:
    return {
        "id": field_id,
        "value": value,
        "evidence": [{"block_id": block_id, "excerpt": excerpt or value}],
    }


def pdf_bytes(*lines: str) -> bytes:
    output = BytesIO()
    canvas = Canvas(output)
    y = 760
    for line in lines:
        canvas.drawString(72, y, line)
        y -= 20
    canvas.save()
    return output.getvalue()


def docx_bytes() -> bytes:
    document = Document()
    document.add_heading("Alex Example", 0)
    document.add_paragraph("Developer in Opole, Poland")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Example University"
    table.cell(0, 1).text = "Computer Science"
    output = BytesIO()
    document.save(output)
    return output.getvalue()


class FakeLuna:
    def __init__(self, payloads: dict[str, dict], *, failing: set[str] | None = None, delay: float = 0) -> None:
        self.payloads = payloads
        self.failing = failing or set()
        self.delay = delay
        self.calls: list[tuple[str, float]] = []
        self.contexts: dict[str, dict | None] = {}
        self._lock = Lock()

    def run(self, pass_name, source, context=None):
        with self._lock:
            self.calls.append((pass_name, perf_counter()))
            self.contexts[pass_name] = context
        if self.delay and pass_name != "review":
            sleep(self.delay)
        if pass_name in self.failing:
            raise ModelPassError("fake_failure")
        return ModelPassResponse(
            self.payloads.get(pass_name, {}),
            "gpt-5.6-luna",
            {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        )


def complete_payloads() -> dict[str, dict]:
    return {
        "profile": {"profile": {
            "candidate_name": field("pf-name", "Alex Example", "texts/0"),
            "declared_location": field("pf-location", "Opole, Poland", "texts/1", "Developer in Opole, Poland"),
            "headline": field("pf-headline", "Developer", "texts/1", "Developer in Opole, Poland"),
            "summary": None,
            "skills": [field("pf-skill", "Python", "texts/2", "Python MongoDB")],
            "languages": [],
        }},
        "employment": {"records": [{
            "id": "employment-1",
            "organization": field("emp-org", "Example Systems", "texts/3", "Example Systems Developer"),
            "role": field("emp-role", "Developer", "texts/3", "Example Systems Developer"),
            "start_date": field("emp-start", "2022", "texts/4", "2022 - present"),
            "end_date": field("emp-end", "present", "texts/4", "2022 - present"),
            "location": None,
            "relationship_type": None,
        }, {
            "id": "employment-tech",
            "organization": field("tech-org", "MongoDB", "texts/2", "Python MongoDB"),
            "role": None,
            "start_date": None,
            "end_date": None,
            "location": None,
            "relationship_type": None,
        }]},
        "education": {"records": []},
        "review": {
            "annotations": [{"record_id": "employment-tech", "kind": "suspected_hallucination", "reason_code": "technology_not_employer"}],
            "merge_groups": [],
            "relation_patches": [],
            "added_profile_fields": [],
            "added_candidates": [{
                "id": "review-education-1",
                "candidate_type": "education",
                "reason_code": "extractor_omission",
                "candidate": {
                    "institution": field("edu-inst", "Example University", "texts/5"),
                    "program": field("edu-program", "Computer Science", "texts/5", "Example University Computer Science"),
                    "degree": None,
                    "certificate": None,
                    "start_date": None,
                    "end_date": None,
                    "location": None,
                },
            }],
            "conflicts": [],
            "coverage_gaps": [],
            "status": "completed",
        },
    }


@pytest.mark.parametrize("source_format", [SourceFormat.PDF, SourceFormat.DOCX])
def test_docling_converts_text_pdf_and_docx_without_models(source_format) -> None:
    content = (
        pdf_bytes("Alex Example", "Developer in Opole, Poland")
        if source_format is SourceFormat.PDF
        else docx_bytes()
    )
    source = DoclingTextConverter().convert(content, f"candidate.{source_format.value}", source_format)

    assert source.blocks
    assert source.identity == DoclingTextConverter().convert(
        content, f"candidate.{source_format.value}", source_format
    ).identity
    assert [block.order for block in source.blocks] == list(range(len(source.blocks)))
    if source_format is SourceFormat.PDF:
        assert source.blocks[0].page_number == 1
        assert source.blocks[0].bbox is not None
    else:
        assert any(block.table_id and block.row_index == 0 for block in source.blocks)


def test_scan_only_pdf_fails_with_clear_text_layer_error() -> None:
    output = BytesIO()
    canvas = Canvas(output)
    canvas.rect(50, 50, 100, 100, fill=1)
    canvas.save()

    with pytest.raises(AnalysisStrategyError, match="document_text_layer_unavailable"):
        DoclingTextConverter().convert(output.getvalue(), "scan.pdf", SourceFormat.PDF)


def test_literal_and_relation_validation_is_record_isolated() -> None:
    source = SourceDocument.create(tuple(
        SourceBlock(f"b-{index}", text, order=index)
        for index, text in enumerate([
            "Example Systems", "Developer", "2022", "filler", "filler", "filler",
            "Other Company", "Designer", "2024", "Example University",
        ])
    ), "pdf")
    employment = {"records": [{
        "id": "mixed",
        "organization": field("mixed-org", "Example Systems", "b-0"),
        "role": field("mixed-role", "Designer", "b-7"),
        "start_date": field("mixed-date", "2024", "b-8"),
        "end_date": None, "location": None, "relationship_type": None,
    }, {
        "id": "valid",
        "organization": field("valid-org", "Other Company", "b-6"),
        "role": field("valid-role", "Designer", "b-7"),
        "start_date": field("valid-date", "2024", "b-8"),
        "end_date": None, "location": None, "relationship_type": None,
    }]}
    state = validate_specialists(source, {}, employment, {})

    assert [record["id"] for record in state.employment] == ["mixed", "valid"]
    assert state.employment[0]["status"] == "ambiguous"
    assert state.employment[1]["status"] == "accepted"


def test_fields_from_different_table_rows_cannot_form_one_record() -> None:
    source = SourceDocument.create((
        SourceBlock(
            "table/cell-0-0", "Example Systems", order=0,
            parent_id="table", table_id="table", row_index=0, column_index=0,
        ),
        SourceBlock(
            "table/cell-1-0", "Designer", order=1,
            parent_id="table", table_id="table", row_index=1, column_index=0,
        ),
    ), "docx")
    state = validate_specialists(source, {}, {"records": [{
        "id": "cross-row",
        "organization": field("cross-row-org", "Example Systems", "table/cell-0-0"),
        "role": field("cross-row-role", "Designer", "table/cell-1-0"),
        "start_date": None, "end_date": None, "location": None,
        "relationship_type": None,
    }]}, {})

    assert [record["id"] for record in state.employment] == ["cross-row"]
    assert state.employment[0]["relation_status"] == "ambiguous"


def test_evidence_excerpt_must_contain_the_semantic_value() -> None:
    source = SourceDocument.create((
        SourceBlock("b-0", "Example Systems — Developer", order=0),
    ), "pdf")
    state = validate_specialists(source, {}, {"records": [{
        "id": "bad-excerpt",
        "organization": field("bad-org", "Example Systems", "b-0", "Developer"),
        "role": None, "start_date": None, "end_date": None,
        "location": None, "relationship_type": None,
    }]}, {})

    assert state.employment == []
    assert {item["reason_code"] for item in state.rejected} >= {"missing_organization"}


def test_evidence_allows_only_safe_unicode_whitespace_and_typography_normalization() -> None:
    source = SourceDocument.create((
        SourceBlock("b-0", "Cafe\u0301\nExample — Engineer", order=0),
    ), "pdf")
    state = validate_specialists(source, {}, {"records": [{
        "id": "normalized",
        "organization": field("org", "Café Example", "b-0", "Café   Example - Engineer"),
        "role": field("role", "Engineer", "b-0", "Example - Engineer"),
        "start_date": None,
        "end_date": None,
        "location": None,
        "relationship_type": None,
    }]}, {})

    assert [record["id"] for record in state.employment] == ["normalized"]
    assert state.employment[0]["organization"]["evidence"][0]["excerpt"] == "Cafe\u0301\nExample — Engineer"


def test_reviewer_unknown_ids_and_invalid_added_evidence_are_rejected() -> None:
    source = SourceDocument.create((SourceBlock("b-1", "Example University", order=0),), "pdf")
    state = validate_specialists(source, {}, {}, {})
    state, review = apply_review(source, state, {
        "annotations": [{"record_id": "unknown", "kind": "uncertain_relation", "reason_code": "unknown"}],
        "relation_patches": [{"record_id": "unknown", "field_ids": ["missing"]}],
        "added_candidates": [{
            "id": "review-education-1", "candidate_type": "education",
            "candidate": {
                "institution": field("added-inst", "Invented University", "b-1", "Invented University"),
                "program": None, "degree": None, "certificate": None,
                "start_date": None, "end_date": None, "location": None,
            },
        }],
        "coverage_gaps": [], "conflicts": [], "status": "partial",
    })

    reasons = {item["reason_code"] for item in review["conflicts"]}
    assert "unknown_reviewer_record_id" in reasons
    assert "unknown_reviewer_patch_id" in reasons
    assert "reviewer_added_candidate_invalid_evidence" in reasons
    assert not state.education
    assert review["coverage_gaps"]


def test_reviewer_applies_relation_patch_by_stable_field_ids() -> None:
    source = SourceDocument.create(tuple(
        SourceBlock(f"b-{index}", text, order=index)
        for index, text in enumerate([
            "Example Systems", "Developer", "filler", "filler", "filler", "Designer",
        ])
    ), "pdf")
    state = validate_specialists(source, {}, {"records": [{
        "id": "needs-correction",
        "organization": field("target-org", "Example Systems", "b-0"),
        "role": field("wrong-role", "Designer", "b-5"),
        "start_date": None, "end_date": None, "location": None, "relationship_type": None,
    }, {
        "id": "field-source",
        "organization": field("source-org", "Example Systems", "b-0"),
        "role": field("correct-role", "Developer", "b-1"),
        "start_date": None, "end_date": None, "location": None, "relationship_type": None,
    }]}, {})

    state, review = apply_review(source, state, {
        "annotations": [{"record_id": "field-source", "kind": "duplicate", "reason_code": "field_source_only"}],
        "merge_groups": [],
        "relation_patches": [{"record_id": "needs-correction", "field_ids": ["correct-role"]}],
        "added_profile_fields": [], "added_candidates": [], "coverage_gaps": [],
        "conflicts": [], "status": "completed",
    })

    corrected = next(record for record in state.employment if record["id"] == "needs-correction")
    assert corrected["role"]["value"] == "Developer"
    assert corrected["relation_status"] == "supported"
    assert corrected["status"] == "accepted"
    assert review["relation_corrections"][0]["record_id"] == "needs-correction"
    assert review["relation_corrections"][0]["original_candidate"]["role"]["value"] == "Designer"
    assert review["relation_corrections"][0]["effective_projection"]["role"]["value"] == "Developer"


def test_reviewer_merge_is_applied_deterministically() -> None:
    source = SourceDocument.create((
        SourceBlock("b-0", "Example Systems", order=0),
        SourceBlock("b-1", "Developer", order=1),
    ), "pdf")
    state = validate_specialists(source, {}, {"records": [{
        "id": "canonical",
        "organization": field("org-1", "Example Systems", "b-0"),
        "role": None, "start_date": None, "end_date": None,
        "location": None, "relationship_type": None,
    }, {
        "id": "duplicate",
        "organization": field("org-2", "Example Systems", "b-0"),
        "role": field("role-2", "Developer", "b-1"),
        "start_date": None, "end_date": None,
        "location": None, "relationship_type": None,
    }]}, {})

    state, review = apply_review(source, state, {
        "annotations": [],
        "merge_groups": [["canonical", "duplicate"]], "relation_patches": [],
        "added_profile_fields": [], "added_candidates": [], "coverage_gaps": [],
        "conflicts": [], "status": "completed",
    })

    assert [record["id"] for record in state.employment] == ["canonical", "duplicate"]
    assert state.employment[0]["role"]["value"] == "Developer"
    assert state.employment[0]["status"] == "accepted"
    assert review["merged_ids"] == [["canonical", "duplicate"]]
    assert review["merge_projections"][0]["original_candidates"][0]["role"] is None
    assert review["merge_projections"][0]["effective_projection"]["role"]["value"] == "Developer"
    assert review["annotations"] == [{
        "record_id": "duplicate",
        "kind": "duplicate",
        "reason_code": "reviewer_duplicate_projection",
    }]


def test_reviewer_cannot_remove_evidence_supported_education_for_research_reasons() -> None:
    source = SourceDocument.create((
        SourceBlock("b-0", "Example University", order=0),
    ), "pdf")
    state = validate_specialists(source, {}, {}, {"records": [{
        "id": "education-1",
        "institution": field("institution-1", "Example University", "b-0"),
        "program": None,
        "degree": None,
        "certificate": None,
        "start_date": None,
        "end_date": None,
        "location": None,
    }]})

    state, review = apply_review(source, state, {
        "rejected_records": [{
            "id": "education-1",
            "reason_code": "accreditation_not_found",
        }],
        "annotations": [{
            "record_id": "education-1",
            "kind": "accreditation_not_found",
            "reason_code": "no_public_source",
        }],
        "merge_groups": [],
        "relation_patches": [],
        "added_profile_fields": [],
        "added_candidates": [],
        "coverage_gaps": [],
        "conflicts": [],
        "status": "completed",
    })

    assert [record["id"] for record in state.education] == ["education-1"]
    assert state.education[0]["status"] == "accepted"
    assert review["annotations"] == []
    assert {item["reason_code"] for item in review["conflicts"]} == {
        "invalid_reviewer_annotation"
    }


def test_reviewer_adds_supported_profile_and_employment_candidates() -> None:
    source = SourceDocument.create((
        SourceBlock("b-0", "Platform engineer focused on Python", order=0),
        SourceBlock("b-1", "Example Systems — Developer", order=1),
    ), "pdf")
    state = validate_specialists(source, {}, {}, {})

    state, review = apply_review(source, state, {
        "annotations": [], "merge_groups": [],
        "relation_patches": [],
        "added_profile_fields": [{
            "field_name": "summary",
            "field": field("review-summary", "Platform engineer", "b-0", "Platform engineer"),
        }],
        "added_candidates": [{
            "id": "review-employment-1", "candidate_type": "employment",
            "reason_code": "extractor_omission", "candidate": {
                "organization": field("review-org", "Example Systems", "b-1"),
                "role": field("review-role", "Developer", "b-1"),
                "start_date": None, "end_date": None, "location": None,
                "relationship_type": None,
            },
        }],
        "coverage_gaps": [], "conflicts": [], "status": "completed",
    })

    assert state.profile["summary"]["value"] == "Platform engineer"
    assert state.employment[0]["id"] == "review-employment-1"
    assert state.employment[0]["status"] == "accepted"
    assert review["added_profile_fields"] == ["summary"]
    assert review["added_candidate_ids"] == ["review-employment-1"]


def test_specialists_run_concurrently_and_reviewer_runs_after_them() -> None:
    content = pdf_bytes(
        "Alex Example", "Developer in Opole, Poland", "Python MongoDB",
        "Example Systems Developer", "2022 - present", "Example University Computer Science",
    )
    client = FakeLuna(complete_payloads(), delay=0.08)
    strategy = DoclingLunaAnalysisStrategy(client=client)
    request = AnalysisInput.from_upload(content, "candidate.pdf", "en")
    started = perf_counter()
    report = strategy.analyze(request)
    elapsed = perf_counter() - started

    calls = {name: timestamp for name, timestamp in client.calls}
    assert max(calls[name] for name in ("profile", "employment", "education")) - min(
        calls[name] for name in ("profile", "employment", "education")
    ) < 0.05
    assert calls["review"] >= max(calls[name] for name in ("profile", "employment", "education"))
    assert elapsed < 0.28
    assert report["strategy"]["name"] == "docling-luna"
    assert report["base_analysis"]["review"]["added_candidate_ids"] == ["review-education-1"]
    assert [item["id"] for item in report["base_analysis"]["education"]] == ["review-education-1"]
    assert "employment-tech" not in report["base_analysis"]["review"]["accepted_ids"]
    assert report["base_analysis"]["pass_statuses"]["profile"]["reasoning_effort"] == "none"
    assert report["base_analysis"]["pass_statuses"]["review"]["reasoning_effort"] == "low"
    assert client.contexts["review"]["mechanical"] is not None


def test_failed_specialist_does_not_remove_other_passes() -> None:
    payloads = complete_payloads()
    client = FakeLuna(payloads, failing={"employment"})
    strategy = DoclingLunaAnalysisStrategy(client=client)
    report = strategy.analyze(AnalysisInput.from_upload(
        pdf_bytes("Alex Example", "Developer in Opole, Poland", "Python MongoDB", "Example Systems Developer", "2022 - present", "Example University Computer Science"),
        "candidate.pdf", "en",
    ))

    assert report["base_analysis"]["status"] == "partial"
    assert report["base_analysis"]["profile"]["candidate_name"]["value"] == "Alex Example"
    assert report["base_analysis"]["education"][0]["added_by_reviewer"] is True
    assert report["base_analysis"]["pass_statuses"]["employment"]["attempt_count"] == 1
    assert [name for name, _ in client.calls].count("employment") == 1
    assert [name for name, _ in client.calls].count("employment_rescue") == 1
    assert [name for name, _ in client.calls].count("profile") == 1
    assert [name for name, _ in client.calls].count("education") == 1


def test_upload_persistence_ownership_and_health_with_real_strategy(tmp_path) -> None:
    client_impl = FakeLuna(complete_payloads())
    strategy = DoclingLunaAnalysisStrategy(client=client_impl)
    client = TestClient(create_app(
        db_path=tmp_path / "docling-luna.db",
        openai_settings=OpenAISettings(enabled=False),
        analysis_strategy=strategy,
    ))
    owner = {"X-Analysis-Access-Token": "owner"}
    created = client.post(
        "/analyze",
        files={"file": ("candidate.pdf", pdf_bytes(
            "Alex Example", "Developer in Opole, Poland", "Python MongoDB",
            "Example Systems Developer", "2022 - present", "Example University Computer Science",
        ), "application/pdf")},
        headers=owner,
    )

    assert client.get("/health").json()["ready"] is True
    assert created.status_code == 200
    report = created.json()
    assert report["contract_version"] == "base-analysis-v2"
    assert client.get(f"/analyses/{report['analysis_id']}", headers=owner).status_code == 200
    assert client.get(f"/analyses/{report['analysis_id']}", headers={"X-Analysis-Access-Token": "other"}).status_code == 404
    diagnostics = client.get(
        f"/analyses/{report['analysis_id']}/diagnostics",
        headers=owner,
    )
    assert diagnostics.status_code == 200
    diagnostic_payload = diagnostics.json()
    assert diagnostic_payload["analysis"]["status"] == "completed"
    assert diagnostic_payload["aggregate"]["attempts"] == 5
    assert diagnostic_payload["aggregate"]["input_tokens"] == 50
    assert {item["key"] for item in diagnostic_payload["aggregates"]["by_operation"]} == {
        "profile", "employment", "education", "education_rescue", "review",
    }
    assert diagnostic_payload["aggregates"]["by_model"][0]["attempts"] == 5
    assert all(
        event["configured_model"] == "gpt-5.6-luna"
        for event in diagnostic_payload["usage_events"]
    )
    assert client.get(
        f"/analyses/{report['analysis_id']}/diagnostics",
        headers={"X-Analysis-Access-Token": "other"},
    ).status_code == 404


def test_openai_contract_pins_model_store_and_reasoning() -> None:
    class Usage:
        def model_dump(self):
            return {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}

    class Response:
        model = "gpt-5.6-luna"
        usage = Usage()

        def __init__(self, output_text):
            self.output_text = output_text

    class Responses:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            name = kwargs["text"]["format"]["name"]
            if name == "cv_profile":
                output = {"profile": {"candidate_name": None, "declared_location": None, "headline": None, "summary": None, "skills": [], "languages": []}}
            else:
                output = {"annotations": [], "merge_groups": [], "relation_patches": [], "added_profile_fields": [], "added_candidates": [], "conflicts": [], "coverage_gaps": [], "status": "completed"}
            import json
            return Response(json.dumps(output))

    class Client:
        def __init__(self):
            self.responses = Responses()

    raw_client = Client()
    client = OpenAIResponsesLunaClient(client=raw_client)
    source = SourceDocument.create((SourceBlock("b-1", "Alex Example", order=0),), "pdf")

    client.run("profile", source)
    client.run("review", source, {})

    specialist, reviewer = raw_client.responses.calls
    assert specialist["model"] == reviewer["model"] == "gpt-5.6-luna"
    assert specialist["reasoning"] == {"effort": "none"}
    assert reviewer["reasoning"] == {"effort": "low"}
    assert specialist["store"] is reviewer["store"] is False
    assert "tools" not in specialist and "tools" not in reviewer
    assert specialist["text"]["format"]["strict"] is True
