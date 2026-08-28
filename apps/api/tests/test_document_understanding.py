from __future__ import annotations

from copy import deepcopy

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
    sanitized = sanitize_understanding(payload)
    assert sanitized is not None and len(sanitized["sections"]) == 32
    assert sanitized["status"] == "partial"
    assert sanitized["truncation"]["sections"]["additional_count"] == 8


def test_contract_rejects_forbidden_national_id_defense_in_depth() -> None:
    payload = understanding_to_payload(_result())
    payload["sections"][0]["heading"] = "123-45-6789"
    with pytest.raises(UnderstandingContractError): sanitize_understanding(payload)


def test_legacy_null_is_valid() -> None:
    assert sanitize_understanding(None) is None
