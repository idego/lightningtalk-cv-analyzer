from __future__ import annotations

import json
from dataclasses import replace

import pytest

from cv_validator.ai.config import AISettings
from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.ingestion import PresentationSpan, RawDocument, SourcePage
from cv_validator.ingestion.redaction import redact_national_ids
from cv_validator.pipeline import analyze_cv_text_result
from cv_validator.serialization import deserialize_analysis_payload, serialize_analysis_payload
from cv_validator.structural.audit import audit_document
from cv_validator.structural.config import StructuralAuditConfig
from cv_validator.structural.domain import AuditStatus, StructuralAuditResult
from cv_validator.structural.sanitize import sanitize_structural_audits


@pytest.mark.parametrize("status", list(AuditStatus))
def test_contract_round_trip_supports_every_status(status):
    result = audit_document(redact_national_ids(RawDocument(pages=(SourcePage("page-0001", 1, "Experience\nAcme 01/2020 - 02/2020"),), source_format="text")), snapshot_month="2026-08")
    result = replace(result, status=status)
    payload = result.to_dict()
    assert json.loads(json.dumps(payload)) == payload
    assert StructuralAuditResult.from_dict(payload) == result


def test_legacy_payload_defaults_to_null():
    assert deserialize_analysis_payload({})["structural_audits"] is None


@pytest.mark.parametrize("field,value", [
    ("near_zero_font_points", -1), ("near_zero_opacity", 2),
    ("minimum_meaningful_alphanumeric", 0), ("max_pdf_atoms", 0),
])
def test_config_rejects_invalid_values(field, value):
    with pytest.raises(ValueError):
        StructuralAuditConfig(**{field: value})


def _audit(text: str):
    raw = RawDocument(pages=(SourcePage("page-0001", 1, text),), source_format="text")
    return audit_document(redact_national_ids(raw), snapshot_month="2026-08")


def test_timeline_invalid_month_and_start_after_end_are_retained():
    result = _audit("Experience\nBad 13/2024 - 02/2025\nReverse 05/2025 - 02/2025")
    assert [item.reason_code for item in result.timeline.observations] == ["invalid_month", "start_after_end"]


def test_timeline_localized_open_ended_snapshot_and_duration():
    result = _audit("Doświadczenie zawodowe\nAcme styczeń 2024 - obecnie")
    entry = result.timeline.entries[0]
    assert (entry.start_month, entry.end_month, entry.end_precision) == ("2024-01", "2026-08", "open_ended")
    assert result.timeline.summaries[0].non_overlapping_months == 32


def test_exact_and_possible_overlap_are_precision_aware_and_category_isolated():
    exact = _audit("Experience\nA 01/2020 - 03/2020\nB 02/2020 - 04/2020\nEducation\nC 01/2020 - 04/2020")
    assert [(item.kind, item.overlap_months) for item in exact.timeline.observations] == [("definite_overlap", 2)]
    possible = _audit("Experience\nA 2020 - 2021\nB 2021 - 2022")
    assert possible.timeline.observations[0].kind == "possible_overlap"
    assert possible.timeline.observations[0].overlap_months is None


def test_contact_and_certification_dates_cannot_create_employment_overlap():
    result = _audit("Contact\nDOB 01/2020 - 02/2020\nCertifications\nAWS 01/2020 - 03/2020")
    assert not result.timeline.observations
    assert all(entry.category == "unknown" for entry in result.timeline.entries)


def test_visibility_never_serializes_hidden_text_and_retains_redaction_metadata():
    text = "Experience\nAcme 01/2020 - present\nPESEL: 44051401458"
    page = SourcePage("page-0001", 1, text)
    start = text.index("44051401458")
    raw = RawDocument(pages=(page,), source_format="docx", presentation_spans=(PresentationSpan(page_id=page.page_id, page_number=1, text="44051401458", start_offset=start, end_offset=start+11, association="exact", explicit_hidden=True),), presentation_audited_parts=("docx_body_paragraph_runs",))
    result = audit_document(redact_national_ids(raw), snapshot_month="2026-08")
    payload = result.to_dict()
    encoded = json.dumps(payload)
    assert "44051401458" not in encoded
    assert payload["visibility"]["observations"][0]["redaction"]["present"] is True
    assert "excerpt" not in payload["visibility"]["observations"][0]


def test_visibility_grouping_ignores_bold_for_v1_compatibility():
    text = "Hidden content"
    page = SourcePage("page-0001", 1, text)
    common = dict(page_id=page.page_id, page_number=1, association="exact", font_size_points=11, explicit_hidden=True, paragraph_path="body/0/paragraph")
    differing = (
        PresentationSpan(text="Hidden ", start_offset=0, end_offset=7, bold=False, **common),
        PresentationSpan(text="content", start_offset=7, end_offset=14, bold=True, **common),
    )
    uniform = tuple(replace(span, bold=False) for span in differing)
    def payload(spans):
        raw = RawDocument(pages=(page,), source_format="docx", presentation_spans=spans, presentation_audited_parts=("docx_body_paragraph_runs",))
        return audit_document(redact_national_ids(raw), snapshot_month="2026-08").to_dict()["visibility"]
    assert payload(differing) == payload(uniform)
    assert payload(differing)["reported_observation_count"] == 1


@pytest.mark.parametrize(
    ("source_format", "audited_part"),
    [("pdf", "pdf_page_text_spans"), ("docx", "docx_body_paragraph_runs")],
)
@pytest.mark.parametrize("association", ["partial", "unmapped"])
def test_uncertain_presentation_mapping_marks_structural_audit_partial(source_format, audited_part, association):
    text = "Hidden content"
    page = SourcePage("page-0001", 1, text)
    offsets = (0, 1) if association == "partial" else (None, None)
    span = PresentationSpan(
        page_id=page.page_id,
        page_number=1,
        text=text,
        start_offset=offsets[0],
        end_offset=offsets[1],
        association=association,
        explicit_hidden=True,
    )
    raw = RawDocument(
        pages=(page,),
        source_format=source_format,
        presentation_spans=(span,),
        presentation_audited_parts=(audited_part,),
    )

    audits = audit_document(redact_national_ids(raw), snapshot_month="2026-08")

    assert audits.visibility.status is AuditStatus.PARTIAL
    assert audits.coverage.status is AuditStatus.PARTIAL
    assert audits.status is AuditStatus.PARTIAL


@pytest.mark.parametrize(
    ("source_format", "audited_part"),
    [("pdf", "pdf_page_text_spans"), ("docx", "docx_body_paragraph_runs")],
)
def test_exact_presentation_mapping_remains_completed(source_format, audited_part):
    text = "Hidden content"
    page = SourcePage("page-0001", 1, text)
    span = PresentationSpan(
        page_id=page.page_id,
        page_number=1,
        text=text,
        start_offset=0,
        end_offset=len(text),
        association="exact",
        explicit_hidden=True,
    )
    raw = RawDocument(
        pages=(page,),
        source_format=source_format,
        presentation_spans=(span,),
        presentation_audited_parts=(audited_part,),
    )

    audits = audit_document(redact_national_ids(raw), snapshot_month="2026-08")

    assert audits.visibility.status is AuditStatus.COMPLETED
    assert audits.coverage.status is AuditStatus.COMPLETED
    assert audits.status is AuditStatus.COMPLETED


def test_partial_source_block_mapping_marks_structural_coverage_partial():
    raw = RawDocument(
        pages=(SourcePage("page-0001", 1, "Experience"),),
        source_format="docx",
        presentation_audited_parts=("docx_body_paragraph_runs",),
        source_blocks_partial=True,
    )

    audits = audit_document(redact_national_ids(raw), snapshot_month="2026-08")

    assert audits.coverage.status is AuditStatus.PARTIAL
    assert audits.status is AuditStatus.PARTIAL


def test_unknown_visibility_field_fails_closed():
    payload = _audit("Experience\nA 2020 - 2021").to_dict()
    payload["visibility"]["observations"] = [{"excerpt": "secret"}]
    assert sanitize_structural_audits(payload) is None


def test_pipeline_ai_disabled_returns_structural_data_without_changing_score_boundary():
    plain = analyze_cv_text_result("Experience\nAcme Engineer Role 01/2020 - 02/2020\nBerlin Germany +49 30 123456", ai_settings=AISettings(enabled=False))
    overlap = analyze_cv_text_result("Experience\nAcme Engineer Role 01/2020 - 03/2020\nOther Engineer Role 02/2020 - 04/2020\nBerlin Germany +49 30 123456", ai_settings=AISettings(enabled=False))
    assert overlap.report.structural_audits is not None
    assert overlap.report.structural_audits.visibility.status is AuditStatus.NOT_APPLICABLE
    assert (plain.report.score, plain.report.band, plain.report.signal_count) == (overlap.report.score, overlap.report.band, overlap.report.signal_count)


def test_persistence_retry_preserves_original_structural_snapshot(tmp_path):
    settings = AISettings(enabled=False)
    result = analyze_cv_text_result("Experience\nAcme Engineer Role 01/2020 - present\nBerlin Germany phone +49 30 123456", ai_settings=settings)
    payload = serialize_analysis_payload(result, settings, analysis_id="analysis-1")
    store = PersistenceStore(PersistenceConfig(tmp_path / "audit.db"))
    store.persist_report(result.document_identity, result.report, report_payload=payload, analysis_id="analysis-1", ai_analysis=payload["ai_analysis"])
    original = store.get_analysis_payload("analysis-1")["structural_audits"]
    retry = json.loads(json.dumps(payload))
    retry["structural_audits"]["snapshot_month"] = "2099-12"
    store.replace_ai_analysis("analysis-1", retry)
    assert store.get_analysis_payload("analysis-1")["structural_audits"] == original
