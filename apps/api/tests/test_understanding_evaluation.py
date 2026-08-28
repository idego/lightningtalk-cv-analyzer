from __future__ import annotations

import json
from pathlib import Path

from cv_validator.document_understanding.service import understand_document, understanding_to_payload
from cv_validator.ingestion import RawDocument, SourcePage
from cv_validator.ingestion.redaction import redact_national_ids


def _analyze(text: str) -> dict:
    raw = RawDocument(pages=(SourcePage("page-0001", 1, text),), source_format="text")
    return understanding_to_payload(understand_document(redact_national_ids(raw), "evaluation-v1", snapshot_month="2026-08"))


def _prf(expected, actual):
    expected, actual = set(expected), set(actual); correct = len(expected & actual)
    precision = correct / len(actual) if actual else float(not expected)
    recall = correct / len(expected) if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def test_supported_pattern_evaluation_thresholds_and_reproducibility() -> None:
    fixtures = json.loads((Path(__file__).parents[1] / "fixtures" / "understanding" / "supported-patterns.json").read_text(encoding="utf-8"))
    section_expected = []; section_actual = []; identity_expected = []; identity_actual = []; skill_expected = []; skill_actual = []
    unsupported_positive_fields = 0
    for fixture in fixtures:
        first = _analyze(fixture["text"]); second = _analyze(fixture["text"])
        assert first == second
        section_expected.extend((fixture["id"], value) for value in fixture["sections"])
        section_actual.extend((fixture["id"], item["kind"]) for item in first["sections"])
        identity_expected.extend((fixture["id"], *value) for value in fixture["identities"])
        for record in first["records"]:
            identity_name = "institution" if record["kind"] == "education" else "organization"
            identity = next(field for field in record["fields"] if field["name"] == identity_name)
            if identity["status"] == "supported": identity_actual.append((fixture["id"], record["kind"], identity["value"]))
            unsupported_positive_fields += sum(field["status"] == "supported" and (not field["evidence"] or field["value"] is None) for field in record["fields"])
        skill_expected.extend((fixture["id"], value) for value in fixture["skills"])
        skill_actual.extend((fixture["id"], item["display_label"]) for item in first["skills"])
    section_precision, section_recall, _ = _prf(section_expected, section_actual)
    identity_precision, _, entry_f1 = _prf(identity_expected, identity_actual)
    skill_precision, _, _ = _prf(skill_expected, skill_actual)
    assert section_precision >= .98 and section_recall >= .95
    assert identity_precision >= .98 and entry_f1 >= .90
    assert skill_precision >= .99
    assert unsupported_positive_fields == 0
