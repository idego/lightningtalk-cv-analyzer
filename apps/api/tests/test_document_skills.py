from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from cv_validator.document_understanding.service import understand_document, understanding_to_payload
from cv_validator.ingestion import RawDocument, SourcePage
from cv_validator.ingestion.redaction import redact_national_ids


def _payload(text: str, *, index_path: Path | None = None) -> dict:
    document = redact_national_ids(RawDocument(pages=(SourcePage("page-0001", 1, text),), source_format="text"))
    kwargs = {"skill_index_path": index_path} if index_path else {}
    return understanding_to_payload(understand_document(document, "test-rules", snapshot_month="2026-08", **kwargs))


def test_exact_multilingual_skill_matches_are_deduplicated_with_evidence() -> None:
    payload = _payload("Umiejętności\nPython, SQL, zarządzanie projektami\nPython")
    assert [skill["display_label"] for skill in payload["skills"]] == [
        "Python (computer programming)", "SQL", "project management"
    ]
    assert len(payload["skills"][0]["evidence"]) == 2
    assert all(skill["taxonomy"] == "esco" for skill in payload["skills"])


@pytest.mark.parametrize("text", [
    "Summary\nI go to work and use a plan.",
    "Summary\nR and C are ordinary prose tokens.",
    "Experience\nPython Developer\nExample Labs",
])
def test_skills_fail_closed_outside_explicit_skill_context(text: str) -> None:
    assert _payload(text)["skills"] == []


@pytest.mark.parametrize("label", ["C", "R", "Go"])
def test_ambiguous_short_labels_fail_closed_inside_skills(label: str) -> None:
    assert _payload(f"Skills\n{label}")["skills"] == []


def test_missing_or_invalid_index_marks_only_skill_coverage_unavailable(tmp_path: Path) -> None:
    missing = _payload("Skills\nPython", index_path=tmp_path / "missing.json")
    assert missing["skills"] == []
    assert missing["status"] == "partial"
    assert "skills_unavailable" in missing["coverage"]["omitted_parts"]
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text('{"manifest": {}, "aliases": []}', encoding="utf-8")
    invalid = _payload("Skills\nPython", index_path=invalid_path)
    assert invalid["skills"] == []
    assert "skills_unavailable" in invalid["coverage"]["omitted_parts"]


def test_skill_index_build_is_reproducible_and_rejects_checksum_mismatch(tmp_path: Path) -> None:
    script = Path(__file__).parents[1] / "scripts" / "build_esco_skill_index.py"
    spec = importlib.util.spec_from_file_location("build_esco_skill_index", script)
    module = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module)
    source = tmp_path / "skills.csv"
    source.write_text("alias,canonical_id,display_label,language\nPython,skill-1,Python,en\nPython,skill-1,Python,pl\n", encoding="utf-8")
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    kwargs = {"expected_checksum": checksum, "source_version": "test", "source_url": "https://esco.ec.europa.eu/en/use-esco/download"}
    module.build(source, first, **kwargs); module.build(source, second, **kwargs)
    assert first.read_bytes() == second.read_bytes()
    payload = json.loads(first.read_text(encoding="utf-8"))
    assert payload["manifest"]["language_alias_counts"] == {"en": 1, "pl": 1}
    with pytest.raises(SystemExit, match="input checksum mismatch"):
        module.build(source, tmp_path / "bad.json", **{**kwargs, "expected_checksum": "0" * 64})
