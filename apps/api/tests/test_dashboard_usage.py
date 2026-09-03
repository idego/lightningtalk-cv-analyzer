from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from conftest import valid_report
from cv_validator.api.app import create_app
from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.openai_config import OpenAISettings
from cv_validator.operations import AnalysisRecorder
from cv_validator.usage import PricingCatalog


def _pricing() -> PricingCatalog:
    return PricingCatalog.from_payload({
        "version": "test-rates-v1",
        "models": {
            "gpt-5.6-luna": {
                "input_usd_per_million": "0.20",
                "cached_input_usd_per_million": "0.02",
                "output_usd_per_million": "1.20",
            }
        },
    })


def _recorder(store: PersistenceStore, analysis_id: str) -> AnalysisRecorder:
    return AnalysisRecorder(
        analysis_id=analysis_id,
        correlation_id="correlation-1",
        diagnostic_sink=lambda _event: None,
        usage_sink=store.record_ai_usage_event,
        pricing=_pricing(),
    )


def _persist_completed_report(store: PersistenceStore, analysis_id: str) -> None:
    store.create_analysis_run(analysis_id, "correlation-1", "owner-token")
    store.persist_report(
        "0" * 64,
        valid_report(),
        analysis_id=analysis_id,
        access_token="owner-token",
        source_filename="candidate.pdf",
    )
    store.complete_analysis_run(analysis_id, "completed")


def test_usage_summary_is_idempotent_and_survives_report_deletion(tmp_path) -> None:
    store = PersistenceStore(PersistenceConfig(tmp_path / "reports.db"))
    analysis_id = "analysis-1"
    _persist_completed_report(store, analysis_id)
    recorder = _recorder(store, analysis_id)

    event = dict(
        operation="profile",
        category="base_analysis",
        provider="openai",
        configured_model="gpt-5.6-luna",
        response_model="gpt-5.6-luna",
        reasoning_effort="medium",
        attempt=1,
        outcome="completed",
        started_at="2026-09-03T08:00:00+00:00",
        completed_at="2026-09-03T08:00:01+00:00",
        latency_ms=1000,
        usage={
            "input_tokens": 1_000,
            "input_tokens_details": {"cached_tokens": 400},
            "output_tokens": 200,
            "total_tokens": 1_200,
        },
    )
    recorder.record_ai_attempt(**event)
    recorder.record_ai_attempt(**event)
    recorder.record_ai_attempt(
        **{**event, "operation": "company_research", "started_at": "2026-09-03T08:01:00+00:00", "completed_at": "2026-09-03T08:01:00+00:00", "usage": {}, "cache_outcome": "hit"}
    )

    before = store.get_usage_summary()
    report = store.get_analysis_usage_summary(analysis_id)

    assert before["reports_processed"] == 1
    assert before["requests"] == 2
    assert before["paid_requests"] == 1
    assert before["input_tokens"] == 1_000
    assert before["cached_input_tokens"] == 400
    assert before["output_tokens"] == 200
    assert before["total_tokens"] == 1_200
    assert before["estimated_cost_usd"] == "0.000368000"
    assert before["estimated_cost_pln"] == "0.001380000"
    assert before["average_tokens_per_report"] == 1200.0
    assert before["average_estimated_cost_usd"] == "0.000368000"
    assert report["estimated_cost_usd"] == "0.000368000"
    assert report["estimated_cost_pln"] == "0.001380000"

    assert store.delete_analysis(analysis_id, "owner-token") is True
    after = store.get_usage_summary()

    assert after["reports_processed"] == 1
    assert after["requests"] == 2
    assert after["estimated_cost_usd"] == before["estimated_cost_usd"]
    assert after["estimated_cost_pln"] == before["estimated_cost_pln"]


def test_usage_ledger_upgrades_develop_schema_once(tmp_path) -> None:
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE ai_usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                category TEXT NOT NULL,
                provider TEXT NOT NULL,
                configured_model TEXT NOT NULL,
                response_model TEXT,
                reasoning_effort TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                outcome TEXT NOT NULL,
                error_code TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                latency_ms INTEGER NOT NULL,
                input_tokens INTEGER NOT NULL,
                cached_input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                estimated_cost_usd TEXT,
                pricing_version TEXT NOT NULL,
                pricing_reason TEXT,
                cache_outcome TEXT,
                saved_input_tokens INTEGER NOT NULL DEFAULT 0,
                saved_cached_input_tokens INTEGER NOT NULL DEFAULT 0,
                saved_output_tokens INTEGER NOT NULL DEFAULT 0,
                saved_total_tokens INTEGER NOT NULL DEFAULT 0,
                saved_cost_usd TEXT
            );
            """
        )
        conn.execute(
            """INSERT INTO ai_usage_events (
                analysis_id, correlation_id, operation, category, provider,
                configured_model, response_model, reasoning_effort, attempt,
                outcome, started_at, completed_at, latency_ms, input_tokens,
                cached_input_tokens, output_tokens, total_tokens,
                estimated_cost_usd, pricing_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "legacy-analysis", "legacy-correlation", "profile", "base_analysis",
                "openai", "gpt-5.6-luna", "gpt-5.6-luna", "medium", 1,
                "completed", "2026-09-02T10:00:00+00:00", "2026-09-02T10:00:01+00:00",
                1000, 1000, 0, 100, 1100, "0.000320000", "legacy-pricing-v1",
            ),
        )

    store = PersistenceStore(PersistenceConfig(path))
    first = store.get_usage_summary()
    reopened = PersistenceStore(PersistenceConfig(path))
    second = reopened.get_usage_summary()
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            """SELECT event_id, event_key, estimated_cost_pln, fx_rate, fx_version,
                      billing_status, reasoning_output_tokens
               FROM ai_usage_events WHERE analysis_id = 'legacy-analysis'"""
        ).fetchone()

    assert first == second
    assert row is not None
    assert row[0] == "legacy-usage-1"
    assert row[1] == "legacy-usage-1"
    assert row[2] == "0.001200000"
    assert row[3] == "3.75"
    assert row[4] == "legacy-backfill-usd-pln-fixed-3.75-v1"
    assert row[5] == "paid"
    assert row[6] == 0


def test_usage_ledger_schema_contains_accounting_only(tmp_path) -> None:
    path = tmp_path / "reports.db"
    PersistenceStore(PersistenceConfig(path))
    with sqlite3.connect(path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(ai_usage_events)")}

    assert {"event_id", "event_key", "analysis_id", "operation", "provider", "estimated_cost_usd", "estimated_cost_pln", "fx_rate", "fx_version"}.issubset(columns)
    assert columns.isdisjoint({"cv_text", "evidence", "prompt", "model_response", "candidate_name", "email"})


def test_usage_endpoints_expose_only_aggregates_and_keep_report_scope(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "reports.db",
        openai_settings=OpenAISettings(enabled=False),
    )
    store = app.state.store
    analysis_id = "analysis-api-1"
    _persist_completed_report(store, analysis_id)
    _recorder(store, analysis_id).record_ai_attempt(
        operation="review",
        category="base_analysis",
        provider="openai",
        configured_model="gpt-5.6-luna",
        response_model="gpt-5.6-luna",
        reasoning_effort="medium",
        attempt=1,
        outcome="completed",
        started_at="2026-09-03T09:00:00+00:00",
        completed_at="2026-09-03T09:00:01+00:00",
        latency_ms=1000,
        usage={"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
    )
    client = TestClient(app)

    forbidden = client.get(
        f"/analyses/{analysis_id}/usage",
        headers={"X-Analysis-Access-Token": "wrong-token"},
    )
    report_usage = client.get(
        f"/analyses/{analysis_id}/usage",
        headers={"X-Analysis-Access-Token": "owner-token"},
    )
    deployment = client.get("/internal/usage/summary")

    assert forbidden.status_code == 404
    assert report_usage.status_code == 200
    assert report_usage.json()["total_tokens"] == 110
    assert "usage_events" not in report_usage.json()
    assert deployment.status_code == 200
    assert deployment.json()["reports_processed"] == 1
    assert deployment.json()["operations"][0]["key"] == "review"
