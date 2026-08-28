from cv_validator.document_understanding.reconciliation import reconcile_records


def _code(program_status="unknown", program=None):
    return {"records": [{"id": "education-1", "kind": "education", "fields": [
        {"name": "institution", "status": "supported", "value": "Example University"},
        {"name": "program", "status": program_status, "value": program},
    ]}]}


def test_ai_omission_never_removes_code_record():
    assert reconcile_records(_code(), {"facts": {"education": [], "employment": []}})[0]["id"] == "education-1"


def test_ai_can_fill_missing_optional_field_without_overwriting_code():
    result = reconcile_records(_code(), {"facts": {"education": [{"institution": "Example University", "program": "Computer Science"}], "employment": []}})[0]
    assert result["fields"][1]["status"] == "unknown"
    assert result["ai_enrichments"] == [{"name": "program", "value": "Computer Science", "authority": "ai"}]


def test_ai_conflict_preserves_code_and_exposes_uncertainty():
    result = reconcile_records(_code("supported", "Mathematics"), {"facts": {"education": [{"institution": "Example University", "program": "Computer Science"}], "employment": []}})[0]
    assert result["fields"][1]["value"] == "Mathematics"
    assert result["conflicts"] == [{"name": "program", "code_value": "Mathematics", "ai_value": "Computer Science"}]


def test_distinct_supported_ai_record_is_additive():
    result = reconcile_records(_code(), {"facts": {"education": [{"institution": "Other University", "program": None}], "employment": []}})
    assert [item["authority"] for item in result] == ["code", "ai"]
