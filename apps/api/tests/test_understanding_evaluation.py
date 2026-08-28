from __future__ import annotations

import json
from pathlib import Path

from cv_validator.document_understanding.service import understand_document, understanding_to_payload
from cv_validator.ingestion import RawDocument, SourcePage
from cv_validator.ingestion.redaction import redact_national_ids


def _analyze(text: str, *, source_format: str = "text", omitted_parts=()) -> dict:
    raw = RawDocument(pages=(SourcePage("page-0001", 1, text),), source_format=source_format, presentation_omitted_parts=tuple(omitted_parts))
    return understanding_to_payload(understand_document(redact_national_ids(raw), "evaluation-v1", snapshot_month="2026-08"))


def _prf(expected, actual):
    expected, actual = set(expected), set(actual); correct = len(expected & actual)
    precision = correct / len(actual) if actual else float(not expected)
    recall = correct / len(expected) if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def test_supported_pattern_evaluation_thresholds_and_reproducibility() -> None:
    fixtures = json.loads((Path(__file__).parents[1] / "fixtures" / "understanding" / "supported-patterns.json").read_text(encoding="utf-8"))
    section_expected = []; section_actual = []; record_expected = []; record_actual = []; skill_expected = []; skill_actual = []; subject_expected = []; subject_actual = []
    unsupported_positive_fields = 0
    for fixture in fixtures:
        options = {"source_format": fixture.get("source_format", "text"), "omitted_parts": fixture.get("omitted_parts", ())}
        first = _analyze(fixture["text"], **options); second = _analyze(fixture["text"], **options)
        assert first == second
        section_expected.extend((fixture["id"], value) for value in fixture["sections"])
        section_actual.extend((fixture["id"], item["kind"]) for item in first["sections"])
        record_expected.extend((fixture["id"], *value) for value in fixture["records"])
        for record in first["records"]:
            identity_name = "institution" if record["kind"] == "education" else "organization"
            identity = next(field for field in record["fields"] if field["name"] == identity_name)
            if identity["status"] != "supported" and record["kind"] == "employment":
                identity = next(field for field in record["fields"] if field["name"] == "relationship_type")
            secondary_name = "program" if record["kind"] == "education" else "role"
            dates_name = "study_dates" if record["kind"] == "education" else "employment_dates"
            secondary = next(field for field in record["fields"] if field["name"] == secondary_name)
            dates = next(field for field in record["fields"] if field["name"] == dates_name)
            if identity["status"] == "supported": record_actual.append((fixture["id"], record["kind"], identity["value"], secondary["value"], dates["value"]))
            unsupported_positive_fields += sum(field["status"] == "supported" and (not field["evidence"] or field["value"] is None) for field in record["fields"])
        skill_expected.extend((fixture["id"], value) for value in fixture["skills"])
        skill_actual.extend((fixture["id"], item["display_label"]) for item in first["skills"])
        subject_expected.extend((fixture["id"], *value) for value in fixture["subjects"])
        subject_actual.extend((fixture["id"], item["category"], item["subject"]) for item in first["code_research_subjects"])
        assert first["coverage"]["status"] == fixture["coverage"]
        assert set(first["coverage"]["omitted_parts"]) >= set(fixture.get("expected_omitted_parts", ()))
        serialized_records = json.dumps(first["records"])
        assert all(value not in serialized_records for value in fixture.get("abstain_values", ()))
        for expected in fixture.get("full_records", ()):
            record = next(item for item in first["records"] if item["kind"] == expected["kind"])
            actual_fields = {field["name"]: {"status": field["status"], "value": field["value"]} for field in record["fields"]}
            assert actual_fields == expected["fields"]
    section_precision, section_recall, _ = _prf(section_expected, section_actual)
    record_precision, _, record_exact_match_f1 = _prf(record_expected, record_actual)
    skill_precision, _, _ = _prf(skill_expected, skill_actual)
    subject_precision, subject_recall, _ = _prf(subject_expected, subject_actual)
    assert section_precision >= .98 and section_recall >= .95
    assert record_precision >= .98 and record_exact_match_f1 >= .90
    assert skill_precision >= .99
    assert subject_precision >= .98 and subject_recall >= .95
    assert unsupported_positive_fields == 0
