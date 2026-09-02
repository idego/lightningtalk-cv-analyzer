from __future__ import annotations

import sqlite3

import pytest
from pydantic import ValidationError

from cv_validator.api.feedback import FeedbackInput, FeedbackStore
from cv_validator.api.persistence import PersistenceConfig, PersistenceStore


def _store(tmp_path):
    db_path = tmp_path / "feedback.db"
    PersistenceStore(PersistenceConfig(db_path=db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO reports(
                   input_hash, contract_version, strategy_name, strategy_version,
                   status, created_at, analysis_id
               ) VALUES('hash','base-analysis-v2','test','v1','complete',
                        '2026-01-01T00:00:00+00:00','analysis-1')"""
        )
    return FeedbackStore(db_path), db_path


def test_targets_are_stable_and_feedback_is_idempotent(tmp_path):
    store, _ = _store(tmp_path)
    payload = {"ruleset_version": "v1", "findings": [{"id": "finding-1"}]}
    first = store.materialize("analysis-1", payload)
    second = store.materialize("analysis-1", payload)
    assert first == second
    target = next(item for item in first if item["kind"] == "review_finding")
    value = FeedbackInput(rating="not_helpful", reason="inaccurate")
    assert store.put("analysis-1", target["target_id"], "actor", value)
    assert store.put("analysis-1", target["target_id"], "actor", value)
    inbox = store.inbox()
    assert len(inbox["items"]) == 1
    assert inbox["items"][0]["comment"] is None


def test_comment_validation_and_contact_rejection():
    with pytest.raises(ValidationError):
        FeedbackInput(rating="helpful", comment="too short")
    with pytest.raises(ValidationError):
        FeedbackInput(comment="Contact me at user@example.com please")
    assert FeedbackInput(comment="This result needs more context").rating is None


def test_materializes_feedback_for_each_visible_signal(tmp_path):
    store, _ = _store(tmp_path)
    evidence = [{"source_id": "block-1", "excerpt": "Faisalabad, Pakistan"}]
    payload = {
        "base_analysis": {
            "profile": {"candidate_name": {"value": "Candidate", "evidence": evidence}},
            "review": {"coverage_gaps": []},
        },
        "mechanical": {
            "location_resolution": [{
                "subject": "declared_location",
                "status": "resolved",
                "city_country_relationship": "same",
                "evidence": evidence,
            }],
            "comparisons": [{
                "kind": "declared_vs_phone",
                "relationship": "same",
                "declared_country_codes": ["PK"],
                "phone_country_codes": ["PK"],
            }],
            "email_findings": [],
        },
    }

    targets = store.materialize("analysis-1", payload)
    locations = {(target["source_category"], target["source_key"]) for target in targets}
    assert ("worth_knowing", "location-resolved-same") in locations
    assert ("remaining", "comparison-same-0") in locations


def test_withdrawal_and_analysis_delete_remove_active_graph(tmp_path):
    store, db_path = _store(tmp_path)
    target = store.materialize("analysis-1", {"ruleset_version": "v1"})[0]
    store.put("analysis-1", target["target_id"], "actor", FeedbackInput(comment="Useful overall context"))
    assert store.withdraw("analysis-1", target["target_id"], "actor") is True
    assert store.inbox()["items"] == []
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("DELETE FROM reports WHERE analysis_id='analysis-1'")
        assert conn.execute("SELECT COUNT(*) FROM feedback_targets").fetchone()[0] == 0


def test_failure_feedback_contract_is_closed(tmp_path):
    store, _ = _store(tmp_path)
    target = store.materialize("analysis-1", {"ruleset_version":"v1","ai_analysis":{"status":"failed","failure_reason":"timeout","attempt_count":2}})
    failure = next(item for item in target if item["kind"] == "operation_failure")
    with pytest.raises(ValueError, match="failure_feedback_is_closed"):
        store.put("analysis-1", failure["target_id"], "actor", FeedbackInput(rating="not_helpful", reason="inaccurate"))
    assert store.put("analysis-1", failure["target_id"], "actor", FeedbackInput(rating="not_helpful", reason="operation_failed"))
