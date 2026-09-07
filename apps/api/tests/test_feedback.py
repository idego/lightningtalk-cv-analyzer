from __future__ import annotations

import sqlite3

import pytest
from conftest import valid_report
from pydantic import ValidationError

from cv_validator.api.feedback import FeedbackInput, FeedbackStore, TriageInput
from cv_validator.api.persistence import PersistenceConfig, PersistenceStore


def _store(tmp_path):
    db_path = tmp_path / "feedback.db"
    PersistenceStore(PersistenceConfig(db_path=db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO reports(
                   input_hash, contract_version, strategy_name, strategy_version,
                   status, created_at, analysis_id, owner_user_id
               ) VALUES('hash','base-analysis-v2','test','v1','complete',
                        '2026-01-01T00:00:00+00:00','analysis-1','owner-1')"""
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
    manifest_target = next(
        item for item in store.manifest("analysis-1", "actor")["targets"]
        if item["target_id"] == target["target_id"]
    )
    assert manifest_target["response"]["rating"] == "not_helpful"
    assert manifest_target["response"]["reason"] == "inaccurate"
    assert "rating" not in manifest_target
    inbox = store.inbox()
    assert len(inbox["items"]) == 1
    assert inbox["items"][0]["comment"] is None


def test_feedback_keeps_displayed_context_and_can_be_deleted_by_maintainer(tmp_path):
    store, _ = _store(tmp_path)
    target = store.materialize("analysis-1", {})[0]
    value = FeedbackInput(
        comment="The education section is incomplete",
        context_label="CV overview",
        context_text="Education\nUniversity of Gdansk · Computer Science",
        context_report={"analysis_id": "analysis-1", "base_analysis": {"education": [{"id": "edu-1"}]}},
    )
    store.put("analysis-1", target["target_id"], "actor", value, actor_email="Recruiter@Idego.pl")

    item = store.inbox()["items"][0]
    assert item["context_label"] == "CV overview"
    assert item["context_text"] == "Education\nUniversity of Gdansk · Computer Science"
    assert item["context_report"] == {"analysis_id": "analysis-1", "base_analysis": {"education": [{"id": "edu-1"}]}}
    assert item["actor_email"] == "recruiter@idego.pl"
    assert store.delete_response(target["target_id"], item["actor_hash"]) is True
    assert store.inbox()["items"] == []


def test_comment_validation_and_contact_rejection():
    with pytest.raises(ValidationError):
        FeedbackInput(comment="Contact me at user@example.com please")
    with pytest.raises(ValidationError):
        FeedbackInput()
    value = FeedbackInput(comment="Wrong")
    assert value.rating is None
    assert value.comment == "Wrong"


def test_helpful_feedback_does_not_require_a_comment():
    value = FeedbackInput(rating="helpful")
    assert value.rating.value == "helpful"
    assert value.comment is None


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
    assert ("remaining", "comparison-same-0") not in locations


def test_withdrawal_and_analysis_delete_preserves_feedback_graph(tmp_path):
    store, db_path = _store(tmp_path)
    target = store.materialize("analysis-1", {"ruleset_version": "v1"})[0]
    store.put("analysis-1", target["target_id"], "actor", FeedbackInput(comment="Useful overall context"))
    assert store.withdraw("analysis-1", target["target_id"], "actor") is True
    assert store.inbox()["items"] == []
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("DELETE FROM reports WHERE analysis_id='analysis-1'")
        assert conn.execute("SELECT COUNT(*) FROM feedback_targets").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM feedback_responses").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM feedback_events").fetchone()[0] == 2


def test_feedback_survives_single_analysis_deletion(tmp_path):
    db_path = tmp_path / "single_del.db"
    p_store = PersistenceStore(PersistenceConfig(db_path=db_path))
    f_store = FeedbackStore(db_path)

    analysis_id = "analysis-single"
    p_store.create_analysis_run(analysis_id, "corr-1", "token-1")
    report = valid_report()
    p_store.persist_report(
        "0" * 64,
        report,
        analysis_id=analysis_id,
        owner_user_id="token-1",
        source_filename="cv.pdf",
    )
    p_store.complete_analysis_run(analysis_id, "completed")

    target = f_store.materialize(analysis_id, report)[0]
    f_store.put(
        analysis_id,
        target["target_id"],
        "token-1",
        FeedbackInput(
            rating="not_helpful",
            reason="missing_context",
            comment="Candidate has missing experience",
            context_label="CV overview",
            context_text="Experience\nAcme Corp · Senior Dev",
        ),
        actor_email="recruiter@idego.pl",
    )
    f_store.triage(
        target["target_id"],
        f_store.pseudonym("actor", "token-1"),
        "maintainer-1",
        TriageInput(status="reviewing", note="Checking parser"),
    )

    deleted = p_store.delete_analysis(analysis_id, "token-1")
    assert deleted is True
    assert p_store.get_analysis_payload(analysis_id) is None

    inbox = f_store.inbox()
    assert len(inbox["items"]) == 1
    item = inbox["items"][0]
    assert item["analysis_id"] == analysis_id
    assert item["rating"] == "not_helpful"
    assert item["reason"] == "missing_context"
    assert item["comment"] == "Candidate has missing experience"
    assert item["context_label"] == "CV overview"
    assert item["context_text"] == "Experience\nAcme Corp · Senior Dev"
    assert item["actor_email"] == "recruiter@idego.pl"
    assert item["triage_status"] == "reviewing"
    assert item["triage_note"] == "Checking parser"

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        assert len(conn.execute("PRAGMA foreign_key_check").fetchall()) == 0


def test_feedback_survives_delete_all_analyses(tmp_path):
    db_path = tmp_path / "del_all.db"
    p_store = PersistenceStore(PersistenceConfig(db_path=db_path))
    f_store = FeedbackStore(db_path)

    for i in (1, 2):
        aid = f"analysis-{i}"
        p_store.create_analysis_run(aid, f"corr-{i}", "shared-token")
        report = valid_report(f"{i}" * 64)
        p_store.persist_report(
            f"{i}" * 64,
            report,
            analysis_id=aid,
            owner_user_id="shared-token",
            source_filename=f"cv-{i}.pdf",
        )
        p_store.complete_analysis_run(aid, "completed")
        target = f_store.materialize(aid, report)[0]
        f_store.put(
            aid,
            target["target_id"],
            f"actor-{i}",
            FeedbackInput(comment=f"Feedback note for analysis {i}"),
            actor_email=f"recruiter{i}@idego.pl",
        )

    assert len(f_store.inbox()["items"]) == 2

    deleted_count = p_store.delete_all_analyses("shared-token")
    assert deleted_count == 2
    assert p_store.list_analyses("shared-token") == []

    items = f_store.inbox()["items"]
    assert len(items) == 2
    comments = {item["comment"] for item in items}
    assert comments == {"Feedback note for analysis 1", "Feedback note for analysis 2"}

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        assert len(conn.execute("PRAGMA foreign_key_check").fetchall()) == 0


def test_feedback_survives_retention_purge(tmp_path):
    db_path = tmp_path / "retention.db"
    p_store = PersistenceStore(PersistenceConfig(db_path=db_path, retention_days=30))
    f_store = FeedbackStore(db_path)

    aid = "analysis-expired"
    p_store.create_analysis_run(aid, "corr-exp", "owner-token")
    report = valid_report()
    p_store.persist_report(
        "0" * 64,
        report,
        analysis_id=aid,
        owner_user_id="owner-token",
        source_filename="old_cv.pdf",
    )
    p_store.complete_analysis_run(aid, "completed")

    payload = {
        **report,
        "company_research": {
            "status": "failed",
            "failure_reason": "timeout",
            "attempt_count": 2,
            "failure": {"retryable": True, "attempt_count": 2},
        },
    }
    targets = f_store.materialize(aid, payload)
    failure_target = next(t for t in targets if t["kind"] == "operation_failure")
    f_store.put(
        aid,
        failure_target["target_id"],
        "actor-exp",
        FeedbackInput(
            rating="not_helpful",
            reason="operation_failed",
            comment="LLM call timed out",
            context_label="Failure diagnostic",
            context_text="Execution failed with timeout",
        ),
        actor_email="dev@idego.pl",
    )

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE reports SET created_at = '2020-01-01T00:00:00+00:00' WHERE analysis_id = ?",
            (aid,),
        )
        conn.execute(
            "UPDATE analysis_runs SET created_at = '2020-01-01T00:00:00+00:00' WHERE analysis_id = ?",
            (aid,),
        )

    purged = p_store.purge_expired()
    assert purged["reports"] == 1
    assert p_store.get_analysis_payload(aid) is None

    inbox = f_store.inbox()
    assert len(inbox["items"]) == 1
    item = inbox["items"][0]
    assert item["analysis_id"] == aid
    assert item["comment"] == "LLM call timed out"
    assert item["context_label"] == "Failure diagnostic"
    assert item["context_text"] == "Execution failed with timeout"
    assert item["actor_email"] == "dev@idego.pl"
    assert item["failure"] is not None
    assert item["failure"]["error_code"] == "timeout"
    assert item["failure"]["attempt_count"] == 2

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        assert len(conn.execute("PRAGMA foreign_key_check").fetchall()) == 0


def test_feedback_migration_from_legacy_schema_with_fk(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE reports (
          analysis_id TEXT PRIMARY KEY, input_hash TEXT, contract_version TEXT,
          strategy_name TEXT, strategy_version TEXT, status TEXT, created_at TEXT,
          access_token_hash TEXT, source_filename TEXT
        );
        CREATE TABLE feedback_targets (
          target_id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, kind TEXT NOT NULL,
          source_category TEXT NOT NULL, source_key TEXT NOT NULL, versions_json TEXT NOT NULL,
          created_at TEXT NOT NULL, UNIQUE(analysis_id, kind, source_category, source_key),
          FOREIGN KEY(analysis_id) REFERENCES reports(analysis_id) ON DELETE CASCADE
        );
        CREATE INDEX feedback_targets_analysis ON feedback_targets(analysis_id);
        CREATE TABLE feedback_responses (
          target_id TEXT NOT NULL, actor_hash TEXT NOT NULL, rating TEXT, reason TEXT,
          comment TEXT, actor_email TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, withdrawn_at TEXT,
          context_label TEXT, context_text TEXT,
          PRIMARY KEY(target_id, actor_hash),
          FOREIGN KEY(target_id) REFERENCES feedback_targets(target_id) ON DELETE CASCADE
        );
        CREATE TABLE feedback_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, target_id TEXT NOT NULL, actor_hash TEXT NOT NULL,
          event_type TEXT NOT NULL, rating TEXT, reason TEXT, created_at TEXT NOT NULL,
          FOREIGN KEY(target_id) REFERENCES feedback_targets(target_id) ON DELETE CASCADE
        );
        CREATE TABLE feedback_triage (
          target_id TEXT NOT NULL, actor_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new',
          note TEXT, maintainer_hash TEXT, updated_at TEXT NOT NULL,
          PRIMARY KEY(target_id, actor_hash),
          FOREIGN KEY(target_id, actor_hash) REFERENCES feedback_responses(target_id, actor_hash) ON DELETE CASCADE
        );
        CREATE TABLE feedback_failure_context (
          target_id TEXT PRIMARY KEY, operation_kind TEXT NOT NULL, error_code TEXT NOT NULL,
          retryable INTEGER, attempt_count INTEGER NOT NULL, occurred_at TEXT NOT NULL,
          correlation_id TEXT NOT NULL, versions_json TEXT NOT NULL,
          FOREIGN KEY(target_id) REFERENCES feedback_targets(target_id) ON DELETE CASCADE
        );
        """
    )
    conn.execute("INSERT INTO reports VALUES ('legacy-1', 'h', 'c', 's', 'v', 'complete', '2026-01-01', 'tok', 'cv.pdf')")
    conn.execute("INSERT INTO feedback_targets VALUES ('t1', 'legacy-1', 'review_finding', 'attention', 'email-0', '{}', '2026-01-01')")
    conn.execute("INSERT INTO feedback_responses VALUES ('t1', 'actor-1', 'not_helpful', 'inaccurate', 'Misidentified email', 'reviewer@idego.pl', '2026-01-01', '2026-01-01', NULL, 'Email Finding', 'Excerpt of email')")
    conn.execute("INSERT INTO feedback_events VALUES (1, 't1', 'actor-1', 'submitted', 'not_helpful', 'inaccurate', '2026-01-01')")
    conn.execute("INSERT INTO feedback_triage VALUES ('t1', 'actor-1', 'planned', 'Refactor email parser', 'maintainer-1', '2026-01-01')")
    conn.execute("INSERT INTO feedback_failure_context VALUES ('t1', 'operation_failure', 'timeout', 1, 3, '2026-01-01', 'corr-leg', '{}')")
    conn.commit()
    conn.close()

    store = FeedbackStore(db_path)

    with store._connect() as c:
        fks = c.execute("PRAGMA foreign_key_list(feedback_targets)").fetchall()
        assert len(fks) == 0, f"Expected 0 FKs on feedback_targets, found: {fks}"
        violations = c.execute("PRAGMA foreign_key_check").fetchall()
        assert len(violations) == 0, f"Foreign key check failed: {violations}"

    inbox = store.inbox()
    assert len(inbox["items"]) == 1
    item = inbox["items"][0]
    assert item["analysis_id"] == "legacy-1"
    assert item["comment"] == "Misidentified email"
    assert item["context_label"] == "Email Finding"
    assert item["context_text"] == "Excerpt of email"
    assert item["actor_email"] == "reviewer@idego.pl"
    assert item["triage_status"] == "planned"
    assert item["triage_note"] == "Refactor email parser"
    assert item["failure"]["error_code"] == "timeout"
    assert item["failure"]["attempt_count"] == 3

    with store._connect() as c:
        c.execute("DELETE FROM reports WHERE analysis_id = 'legacy-1'")
        c.commit()
        violations = c.execute("PRAGMA foreign_key_check").fetchall()
        assert len(violations) == 0

    assert len(store.inbox()["items"]) == 1


def test_failure_feedback_contract_is_closed(tmp_path):
    store, _ = _store(tmp_path)
    target = store.materialize("analysis-1", {"ruleset_version":"v1","company_research":{"status":"failed","failure_reason":"timeout","attempt_count":2}})
    failure = next(item for item in target if item["kind"] == "operation_failure")
    with pytest.raises(ValueError, match="failure_feedback_is_closed"):
        store.put("analysis-1", failure["target_id"], "actor", FeedbackInput(rating="not_helpful", reason="inaccurate"))
    assert store.put("analysis-1", failure["target_id"], "actor", FeedbackInput(rating="not_helpful", reason="operation_failed"))


def test_context_report_size_is_limited():
    with pytest.raises(ValidationError):
        FeedbackInput(comment="Too big", context_report={"blob": "x" * 400_001})
    assert FeedbackInput(comment="Fits", context_report={"blob": "x" * 1000}).context_report is not None


def test_feedback_context_report_strips_internal_capability_fields_recursively(tmp_path):
    store, _ = _store(tmp_path)
    target = store.materialize("analysis-1", {"ruleset_version": "v1"})[0]
    result = store.put(
        "analysis-1",
        target["target_id"],
        "actor@example.com",
        FeedbackInput(
            rating="helpful",
            context_report={
                "analysis_access_token": "secret",
                "nested": {"owner_user_id": "owner", "safe": "value"},
                "items": [{"access_token": "also-secret", "safe": 1}],
            },
        ),
    )
    assert result is not None
    inbox = store.inbox()["items"][0]["context_report"]
    assert inbox == {"nested": {"safe": "value"}, "items": [{"safe": 1}]}


def test_feedback_rate_limit_is_scoped_per_analysis(tmp_path):
    store, _ = _store(tmp_path)
    first = store.materialize("analysis-1", {"ruleset_version": "v1"})[0]
    second = store.materialize("analysis-2", {"ruleset_version": "v1"})[0]
    actor = "actor@example.com"
    for index in range(30):
        target = store.materialize(
            "analysis-1",
            {"ruleset_version": "v1", "findings": [{"id": f"finding-{index}"}]},
        )[-1]
        store.put("analysis-1", target["target_id"], actor, FeedbackInput(rating="helpful"))
    with pytest.raises(ValueError, match="feedback_rate_limit"):
        store.put("analysis-1", first["target_id"], actor, FeedbackInput(rating="helpful"))
    assert store.put("analysis-2", second["target_id"], actor, FeedbackInput(rating="helpful"))
