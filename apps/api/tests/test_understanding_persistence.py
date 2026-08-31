from __future__ import annotations

from copy import deepcopy
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from cv_validator.ai.config import AISettings
from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.pipeline import analyze_cv_text_result
from cv_validator.serialization import deserialize_analysis_payload, serialize_analysis_payload


TEXT = "Experience\nExample Labs\nSoftware Engineer\n01/2020 - 02/2022\nEducation\nExample University\nBachelor of Science\n09/2015 - 06/2019"


def _saved(tmp_path):
    settings = AISettings(enabled=False); result = analyze_cv_text_result(TEXT, ai_settings=settings)
    payload = serialize_analysis_payload(result, settings, analysis_id="understanding-1")
    store = PersistenceStore(PersistenceConfig(tmp_path / "understanding.db"))
    store.persist_report(result.document_identity, result.report, report_payload=payload, analysis_id="understanding-1", ai_analysis=payload["ai_analysis"], access_token="token")
    return store, payload


def test_sqlite_foreign_keys_are_enabled_for_candidate_owned_research(tmp_path):
    store = PersistenceStore(PersistenceConfig(tmp_path / "foreign-keys.db"))

    with store._connect() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO company_research (
                    analysis_id, research_version, status, prompt_version,
                    schema_version, configured_model, response_model,
                    accessed_at, usage_json, result_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "missing-analysis",
                    "research-v1",
                    "completed",
                    "prompt-v1",
                    "schema-v1",
                    "model",
                    None,
                    "2026-08-31T00:00:00+00:00",
                    "{}",
                    "{}",
                    "2026-08-31T00:00:00+00:00",
                ),
            )


def test_understanding_initial_save_reload_and_retry_are_byte_stable(tmp_path):
    store, payload = _saved(tmp_path)
    expected = json.dumps(payload["document_understanding"], sort_keys=True, separators=(",", ":")).encode()
    reloaded = store.get_analysis_payload("understanding-1")
    assert json.dumps(reloaded["document_understanding"], sort_keys=True, separators=(",", ":")).encode() == expected
    retry = deepcopy(payload); retry["document_understanding"] = None
    store.replace_ai_analysis("understanding-1", retry)
    assert json.dumps(store.get_analysis_payload("understanding-1")["document_understanding"], sort_keys=True, separators=(",", ":")).encode() == expected
    reopened = PersistenceStore(store.config)
    assert reopened.get_analysis_payload("understanding-1")["document_understanding"] == payload["document_understanding"]


def test_understanding_is_removed_with_analysis_deletion(tmp_path):
    store, _ = _saved(tmp_path)
    assert store.delete_analysis("understanding-1", "token") is True
    assert store.get_analysis_payload("understanding-1") is None


def test_understanding_obeys_report_retention_without_a_parallel_store(tmp_path):
    store, _ = _saved(tmp_path)
    old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    with store._connect() as connection:
        connection.execute("UPDATE reports SET created_at = ? WHERE analysis_id = ?", (old, "understanding-1"))
        connection.execute("UPDATE audit_log SET created_at = ? WHERE analysis_id = ?", (old, "understanding-1"))
    store.set_retention_days(1)
    assert store.get_analysis_payload("understanding-1") is None


def test_legacy_and_malformed_nested_understanding_load_fail_safely():
    assert deserialize_analysis_payload({})["document_understanding"] is None
    malformed = {"document_understanding": {"contract_version": "document-understanding-v1", "records": [None]}}
    assert deserialize_analysis_payload(malformed)["document_understanding"] is None


def test_multiple_employment_dates_abstain_and_serialize_without_duplicate_ids():
    text = """Experience
Company: Example Company Ltd
Role: Software Engineer
Jan 2020 - Feb 2022
Mar 2022 - Apr 2024"""
    settings = AISettings(enabled=False)
    result = analyze_cv_text_result(text, ai_settings=settings)
    payload = serialize_analysis_payload(result, settings, analysis_id="ambiguous-employment")
    understanding = payload["document_understanding"]

    assert understanding["records"] == []
    findings = [item for item in understanding["ambiguous_spans"] if item["reason_code"] == "multiple_date_anchors"]
    assert len(findings) == 1
    assert len({item["id"] for item in understanding["ambiguous_spans"]}) == len(understanding["ambiguous_spans"])
    assert deserialize_analysis_payload(json.loads(json.dumps(payload)))["document_understanding"] == understanding
