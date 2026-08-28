from __future__ import annotations

from cv_validator.research.company import MAX_ORGANIZATIONS, build_company_research_request
from cv_validator.research.education import build_education_research_request


def _understanding(subjects, records=()):
    return {"document_understanding": {"code_research_subjects": list(subjects), "records": list(records)}}


def test_company_code_subjects_work_without_document_ai_and_precede_ai() -> None:
    stored = _understanding([
        {"category": "company", "subject": "Code One Ltd", "record_id": "record-1"},
        {"category": "company", "subject": "Code Two Ltd", "record_id": "record-2"},
    ])
    stored["ai_analysis"] = {"status": "failed", "facts": {"employment": []}, "research_candidates": [
        {"category": "company", "query_subject": "Code One Ltd"},
        {"category": "company", "query_subject": "AI Three Ltd"},
    ]}
    # An AI addition remains independently evidence-bound through its validated fact.
    stored["ai_analysis"]["facts"]["employment"] = [{"organization": "AI Three Ltd"}]
    assert build_company_research_request(stored).input_facts == (
        {"organization": "Code One Ltd"}, {"organization": "Code Two Ltd"}, {"organization": "AI Three Ltd"}
    )


def test_company_limit_is_allocated_to_code_before_ai() -> None:
    subjects = [{"category": "company", "subject": f"Code Company {index} Ltd", "record_id": str(index)} for index in range(MAX_ORGANIZATIONS)]
    stored = _understanding(subjects)
    stored["ai_analysis"] = {"facts": {"employment": [{"organization": "AI Extra Ltd"}]}, "research_candidates": [{"category": "company", "query_subject": "AI Extra Ltd"}]}
    request = build_company_research_request(stored)
    assert len(request.input_facts) == MAX_ORGANIZATIONS
    assert all(fact["organization"].startswith("Code") for fact in request.input_facts)


def test_education_code_subject_uses_supported_program_without_ai() -> None:
    record = {"id": "education-1", "fields": [
        {"name": "institution", "status": "supported", "value": "Example University"},
        {"name": "program", "status": "supported", "value": "Computer Science"},
    ]}
    stored = _understanding([{"category": "education", "subject": "Example University", "record_id": "education-1"}], [record])
    stored["ai_analysis"] = {"status": "failed"}
    assert build_education_research_request(stored).input_facts == (
        {"institution": "Example University", "program": "Computer Science"},
    )
