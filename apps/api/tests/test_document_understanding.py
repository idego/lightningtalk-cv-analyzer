from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from cv_validator.document_understanding.contract import (
    UnderstandingContractError, sanitize_understanding,
)
from cv_validator.document_understanding.service import understand_document, understanding_to_payload
from cv_validator.domain import FactKind, ScoringSignalKind
from cv_validator.extraction.deterministic import analyze_deterministically
from cv_validator.ingestion import PresentationSpan, RawDocument, SourcePage
from cv_validator.ingestion.redaction import redact_national_ids
from cv_validator.structural import audit_document
from cv_validator.research.company import build_company_research_request
from cv_validator.research.cache import company_cache_descriptor


SYNTHETIC_CV = """Contact
Location: Warsaw, Poland
Phone: +48 123 456 789
Experience
01/2020 - 02/2022
Example Labs
Software Engineer
Education
09/2015 - 06/2019
Example University
Bachelor of Science"""


def _result(text: str = SYNTHETIC_CV, *, spans=()):
    raw = RawDocument(
        pages=(SourcePage("page-0001", 1, text),), source_format="text" if not spans else "pdf",
        presentation_spans=spans,
    )
    return understand_document(redact_national_ids(raw), "test-rules", snapshot_month="2026-08")


def test_understanding_is_stable_and_does_not_extend_verdict_enums() -> None:
    first = _result(); second = _result()
    assert understanding_to_payload(first) == understanding_to_payload(second)
    assert {item.value for item in FactKind} == {"phone_country", "postal_country", "claimed_location"}
    assert {item.value for item in ScoringSignalKind} == {"phone_country", "postal_country"}


def test_visible_deterministic_and_structural_v1_projections_are_byte_compatible() -> None:
    result = _result()
    baseline_deterministic = analyze_deterministically(result.document, "test-rules")
    baseline_structural = audit_document(result.document, snapshot_month="2026-08")
    assert result.deterministic.to_dict() == baseline_deterministic.to_dict()
    assert result.structural_audits.to_dict() == baseline_structural.to_dict()


def test_structural_projection_matches_frozen_pre_consolidation_golden_bytes() -> None:
    golden = Path(__file__).parents[1] / "fixtures" / "understanding" / "legacy-structural-v1-golden.json"
    expected = golden.read_bytes().rstrip(b"\n")
    actual = json.dumps(_result().structural_audits.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert actual == expected


def test_materializes_conservative_records_and_code_subjects() -> None:
    payload = understanding_to_payload(_result())
    assert [record["kind"] for record in payload["records"]] == ["employment", "education"]
    assert [(item["category"], item["subject"]) for item in payload["code_research_subjects"]] == [
        ("company", "Example Labs"), ("education", "Example University")
    ]
    assert all(item["field_name"] in {"organization", "institution"} for item in payload["code_research_subjects"])


def test_hidden_only_phone_is_quarantined_before_deterministic_materialization() -> None:
    text = "Contact\nPhone: +48 123 456 789\nLocation: Warsaw, Poland"
    start = text.index("+48")
    span = PresentationSpan("page-0001", 1, text[start:start+15], start, start+15, association="exact", explicit_hidden=True)
    result = _result(text, spans=(span,))
    assert all(candidate.kind.value != "phone" for candidate in result.deterministic.candidates)


def test_self_employment_relationship_is_not_a_company_subject() -> None:
    result = _result("Experience\n01/2020 - Present\nFreelance\nSoftware Engineer")
    payload = understanding_to_payload(result)
    assert payload["records"][0]["fields"][2]["value"] == "Freelance"
    assert payload["code_research_subjects"] == []


def test_contract_rejects_unknown_internal_and_invalid_evidence_fields() -> None:
    payload = understanding_to_payload(_result())
    for key in ("document", "annotation_index", "presentation_spans"):
        malformed = deepcopy(payload); malformed[key] = {}
        with pytest.raises(UnderstandingContractError): sanitize_understanding(malformed)
    malformed = deepcopy(payload); malformed["sections"][0]["evidence"][0]["association"] = "unmapped"
    with pytest.raises(UnderstandingContractError): sanitize_understanding(malformed)


def test_contract_truncates_parent_first_and_preserves_cross_references() -> None:
    payload = understanding_to_payload(_result())
    base = payload["sections"][0]
    payload["sections"] = [{**base, "id": f"section-{i:03d}", "start_line_id": f"line-{i:03d}", "end_line_id": f"line-{i:03d}"} for i in range(40)]
    payload["records"] = []; payload["timeline_record_links"] = []; payload["code_research_subjects"] = []
    payload["truncation"]["sections"] = {"reported_count": 40, "additional_count": 0, "truncated": False}
    for name in ("records", "timeline_record_links", "code_research_subjects"):
        payload["truncation"][name] = {"reported_count": 0, "additional_count": 0, "truncated": False}
    sanitized = sanitize_understanding(payload)
    assert sanitized is not None and len(sanitized["sections"]) == 32
    assert sanitized["status"] == "partial"
    assert sanitized["truncation"]["sections"]["additional_count"] == 8


@pytest.mark.parametrize("collection,limit", [
    ("sections", 32), ("date_ranges", 100), ("records", 100), ("skills", 200),
    ("ambiguous_spans", 100), ("timeline_record_links", 100), ("code_research_subjects", 50),
])
def test_contract_truncates_every_bounded_collection(collection: str, limit: int) -> None:
    payload = understanding_to_payload(_result(SYNTHETIC_CV + "\nSkills\nPython"))
    timeline_ids = {entry.id for entry in _result(SYNTHETIC_CV + "\nSkills\nPython").structural_audits.timeline.entries}
    section, date_range, record, skill = payload["sections"][0], payload["date_ranges"][0], payload["records"][0], payload["skills"][0]
    evidence = section["evidence"]
    factories = {
        "sections": lambda i: {**section, "id": f"section-many-{i}", "start_line_id": f"line-many-{i}", "end_line_id": f"line-many-{i}"},
        "date_ranges": lambda i: {**date_range, "id": f"date-many-{i}"},
        "records": lambda i: {**record, "id": f"record-many-{i}"},
        "skills": lambda i: {**skill, "id": f"skill-many-{i}"},
        "ambiguous_spans": lambda i: {"id": f"ambiguous-many-{i}", "category": "entry", "reason_code": "synthetic_ambiguity", "evidence": evidence},
        "timeline_record_links": lambda i: {"timeline_entry_id": next(iter(timeline_ids)), "record_id": record["id"]},
        "code_research_subjects": lambda i: {"id": f"subject-many-{i}", "category": "company", "subject": next(field["value"] for field in record["fields"] if field["name"] == "organization"), "record_id": record["id"], "field_name": "organization"},
    }
    payload[collection] = [factories[collection](index) for index in range(limit + 1)]
    payload["truncation"][collection] = {"reported_count": limit + 1, "additional_count": 0, "truncated": False}
    if collection in {"sections", "date_ranges", "records"}:
        for dependent in ("records", "timeline_record_links", "code_research_subjects"):
            if dependent == collection:
                continue
            payload[dependent] = []
            payload["truncation"][dependent] = {"reported_count": 0, "additional_count": 0, "truncated": False}
    sanitized = sanitize_understanding(payload, timeline_entry_ids=timeline_ids)
    assert sanitized is not None and len(sanitized[collection]) == limit
    assert sanitized["truncation"][collection] == {"reported_count": limit, "additional_count": 1, "truncated": True}


def test_contract_rejects_forbidden_national_id_defense_in_depth() -> None:
    payload = understanding_to_payload(_result())
    payload["sections"][0]["heading"] = "123-45-6789"
    with pytest.raises(UnderstandingContractError): sanitize_understanding(payload)


def test_legacy_null_is_valid() -> None:
    assert sanitize_understanding(None) is None


def test_complete_polish_english_section_catalog_is_detected_in_source_order() -> None:
    headings = ["Contact", "Podsumowanie", "Work Experience", "Wykształcenie", "Technical Skills", "Certyfikaty", "Projects", "Języki obce", "Publications", "Nagrody", "Volunteering", "Referencje"]
    payload = understanding_to_payload(_result("\nDetail\n".join(headings)))
    assert [item["kind"] for item in payload["sections"]] == ["contact", "summary", "employment", "education", "skills", "certifications", "projects", "languages", "publications", "awards", "volunteering", "references"]


@pytest.mark.parametrize("relationship", [
    "Freelance", "Freelancer", "Self employed", "Self employment",
    "Self-employed", "Self-employment", "Samozatrudnienie",
    "Samozatrudniony", "Wolny strzelec",
])
def test_every_self_employment_variant_is_relationship_only(relationship: str) -> None:
    payload = understanding_to_payload(_result(
        f"Experience\n01/2020 - Present\n{relationship}\nSoftware Engineer"
    ))
    assert payload["records"][0]["fields"][0]["status"] == "unknown"
    assert payload["records"][0]["fields"][2]["value"] == relationship
    assert payload["code_research_subjects"] == []


def test_hidden_relation_label_cannot_own_visible_value() -> None:
    text = "Contact\nLocation: Warsaw, Poland\nExperience\n01/2020 - Present\nExample Labs\nSoftware Engineer"
    start = text.index("Location")
    span = PresentationSpan("page-0001", 1, "Location", start, start + 8, association="exact", explicit_hidden=True)
    result = _result(text, spans=(span,))
    claimed = [candidate for candidate in result.deterministic.candidates if candidate.kind.value == "claimed_location"]
    assert claimed == []


def test_hidden_date_does_not_reach_shared_date_or_structural_projection() -> None:
    text = "Experience\n01/2020 - 02/2022\nExample Labs\nSoftware Engineer"
    start = text.index("01/2020")
    span = PresentationSpan("page-0001", 1, "01/2020 - 02/2022", start, start + 17, association="exact", explicit_hidden=True)
    result = _result(text, spans=(span,))
    assert result.date_ranges == ()
    assert result.structural_audits.timeline.entries == ()


def test_partly_hidden_unrelated_token_preserves_visible_record_evidence() -> None:
    text = "Education\n09/2015 - 06/2019\nExample University\nBachelor of Science\nDecoration"
    start = text.index("Decoration")
    span = PresentationSpan("page-0001", 1, "Decor", start, start + 5, association="exact", explicit_hidden=True)
    payload = understanding_to_payload(_result(text, spans=(span,)))
    assert [(record["kind"], record["fields"][0]["value"]) for record in payload["records"]] == [
        ("education", "Example University")
    ]


def test_date_anchor_stays_with_preceding_entry_and_identical_dates_do_not_join() -> None:
    text = "Experience\nExample Labs Ltd\nSoftware Engineer\n01/2020 - 02/2022\nOther Company Ltd\nProduct Manager\n01/2020 - 02/2022"
    payload = understanding_to_payload(_result(text))
    records = payload["records"]
    assert [next(field["value"] for field in record["fields"] if field["name"] == "organization") for record in records] == [
        "Example Labs Ltd", "Other Company Ltd"
    ]
    assert len({record["date_range_ids"][0] for record in records}) == 2
    assert {link["record_id"] for link in payload["timeline_record_links"]} == {record["id"] for record in records}


@pytest.mark.parametrize("text", [
    "Experience\n01/2020 - 02/2022\nExample Labs Ltd\nSoftware Engineer",
    "Experience\nExample Labs Ltd\nSoftware Engineer\n01/2020 - 02/2022",
    "Education\n09/2015 - 06/2019\nExample University\nBachelor of Science",
    "Education\nExample University\nBachelor of Science\n09/2015 - 06/2019",
])
def test_date_first_and_date_last_entries_keep_explicit_links(text: str) -> None:
    payload = understanding_to_payload(_result(text))
    assert len(payload["records"]) == 1
    assert len(payload["records"][0]["date_range_ids"]) == 1
    assert payload["timeline_record_links"][0]["record_id"] == payload["records"][0]["id"]


@pytest.mark.parametrize("value", ["Product Owner", "Team Coordinator", "Customer Success"])
def test_generic_title_case_role_does_not_become_company(value: str) -> None:
    payload = understanding_to_payload(_result(f"Experience\n{value}\n01/2020 - 02/2022"))
    assert payload["records"] == []
    assert payload["code_research_subjects"] == []


def test_hidden_company_label_cannot_own_visible_value_or_research_subject() -> None:
    text = "Experience\nCompany: Example Labs Ltd\nRole: Software Engineer\n01/2020 - 02/2022"
    start = text.index("Company")
    span = PresentationSpan("page-0001", 1, "Company", start, start + 7, association="exact", explicit_hidden=True)
    payload = understanding_to_payload(_result(text, spans=(span,)))
    assert payload["records"] == []
    assert payload["code_research_subjects"] == []


@pytest.mark.parametrize("hidden_part", ["Company", "Example Labs Ltd"])
def test_indented_hidden_company_field_is_quarantined_at_original_offsets(hidden_part: str) -> None:
    text = "Experience\n  Company: Example Labs Ltd\nRole: Software Engineer\n01/2020 - 02/2022"
    start = text.index(hidden_part)
    span = PresentationSpan("page-0001", 1, hidden_part, start, start + len(hidden_part), association="exact", explicit_hidden=True)
    payload = understanding_to_payload(_result(text, spans=(span,)))
    serialized = json.dumps(payload)
    assert payload["records"] == []
    assert payload["code_research_subjects"] == []
    assert hidden_part not in serialized
    assert all(hidden_part not in evidence["excerpt"] for item in payload["ambiguous_spans"] for evidence in item["evidence"])


def test_title_case_unknown_heading_stops_employment_without_breaking_inline_uppercase_rows() -> None:
    result = _result("Experience\nExample Labs Ltd\nRole: Engineer\n01/2020 - 02/2022\nTraining\n03/2022 - 04/2022\nA 05/2022 - 06/2022")
    payload = understanding_to_payload(result)
    assert [item["kind"] for item in payload["sections"]] == ["employment", "other"]
    assert [entry.category for entry in result.structural_audits.timeline.entries] == ["employment", "unknown", "unknown"]
    assert len(payload["records"]) == 1


def test_candidate_dates_use_shared_named_month_range_annotations() -> None:
    result = _result("Experience\nJan 2020 - Feb 2022\nCompany: Example Labs Ltd\nRole: Engineer")
    assert result.date_ranges[0].source_literal == "Jan 2020 - Feb 2022"
    dates = [candidate for candidate in result.deterministic.candidates if candidate.kind.value == "date"]
    assert [candidate.value for candidate in dates] == ["Jan 2020", "Feb 2022"]
    assert [(item.provenance.evidence[0].start_offset, item.provenance.evidence[0].end_offset) for item in dates] == [
        (result.date_ranges[0].evidence[0].start_offset, result.date_ranges[0].evidence[0].start_offset + len("Jan 2020")),
        (result.date_ranges[0].evidence[0].end_offset - len("Feb 2022"), result.date_ranges[0].evidence[0].end_offset),
    ]


def test_label_and_value_keep_separate_evidence_through_research_projection() -> None:
    payload = understanding_to_payload(_result(
        "Experience\nCompany: Example Labs Ltd | Role: Software Engineer | 01/2020 - 02/2022"
    ))
    record = payload["records"][0]
    organization = next(field for field in record["fields"] if field["name"] == "organization")
    role = next(field for field in record["fields"] if field["name"] == "role")
    assert [item["association"] for item in organization["evidence"]] == ["exact", "exact"]
    assert [item["excerpt"] for item in organization["evidence"]] == ["Company", "Example Labs Ltd"]
    assert role["value"] == "Software Engineer"
    assert record["date_range_ids"]
    assert payload["code_research_subjects"][0]["subject"] == "Example Labs Ltd"
    request = build_company_research_request({"document_understanding": payload, "ai_analysis": {"status": "failed"}})
    descriptor = company_cache_descriptor(request)
    assert request.input_facts == ({"organization": "Example Labs Ltd"},)
    assert descriptor.normalized_subjects == ("example labs ltd",)
    assert "Company" not in descriptor.normalized_subjects


def test_quarantined_evidence_never_serializes_and_marks_coverage_partial() -> None:
    text = "Education\nExample University\nBachelor of Science\nHIDDEN_DECORATION"
    start = text.index("HIDDEN_DECORATION")
    span = PresentationSpan("page-0001", 1, "HIDDEN_DECORATION", start, len(text), association="exact", explicit_hidden=True)
    payload = understanding_to_payload(_result(text, spans=(span,)))
    assert payload["coverage"]["status"] == "partial"
    assert "HIDDEN_DECORATION" not in json.dumps(payload)


def test_unknown_heading_stops_timeline_category_inheritance() -> None:
    result = _result("Experience\nExample Labs Ltd\nSoftware Engineer\n01/2020 - 02/2022\nINTERESTS\n03/2022 - 04/2022")
    assert result.structural_audits.timeline.entries[-1].category == "unknown"
    assert any(section.kind.value == "other" for section in result.sections)


def test_ingestion_omitted_surfaces_make_understanding_coverage_partial() -> None:
    raw = RawDocument(
        pages=(SourcePage("page-0001", 1, "Skills\nPython"),),
        source_format="docx",
        presentation_omitted_parts=("docx_headers", "docx_footnotes", "docx_comments", "docx_drawings", "docx_embedded_files"),
    )
    payload = understanding_to_payload(understand_document(redact_national_ids(raw), "test", snapshot_month="2026-08"))
    assert payload["coverage"]["status"] == "partial"
    assert set(payload["coverage"]["omitted_parts"]) >= {"docx_headers", "docx_footnotes_endnotes", "docx_comments", "docx_drawings", "docx_embedded_files"}


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(records=[None]),
    lambda p: p.update(skills=[{"id": "broken"}]),
    lambda p: p["truncation"]["sections"].update(truncated=1),
    lambda p: p["truncation"]["sections"].update(reported_count=True),
])
def test_malformed_nested_shapes_fail_with_contract_error(mutation) -> None:
    payload = understanding_to_payload(_result())
    mutation(payload)
    with pytest.raises(UnderstandingContractError):
        sanitize_understanding(payload, timeline_entry_ids={entry.id for entry in _result().structural_audits.timeline.entries})
