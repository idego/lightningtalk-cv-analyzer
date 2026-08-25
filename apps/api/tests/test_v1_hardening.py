from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from cv_validator.ai.config import AISettings
from cv_validator.api.app import create_app
from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.measurement import summarize_measurements


def test_measurement_report_covers_operational_dimensions():
    report = summarize_measurements([
        {"mode":"single", "latency_seconds":1.0, "status":"succeeded", "input_tokens":10, "output_tokens":2,
         "web_searches":0, "cache":"miss", "estimated_cost_usd":0.01, "evidence_kind":"controlled_fake"},
        {"mode":"batch", "latency_seconds":2.0, "status":"failed", "input_tokens":5, "output_tokens":0,
         "web_searches":4, "cache":"hit", "estimated_cost_usd":0.02, "evidence_kind":"historical_live"},
    ])
    assert report["latency_seconds"] == {"total":3.0, "mean":1.5, "max":2.0}
    assert report["failures"] == 1 and report["tokens"] == {"input":15, "output":2}
    assert report["web_searches"] == 4 and report["cache"] == {"hits":1, "misses":1}
    assert report["estimated_cost_usd"] == 0.03


def test_retention_cleanup_is_operator_visible_and_cache_expiry_is_independent(tmp_path):
    store=PersistenceStore(PersistenceConfig(tmp_path/"db.sqlite", retention_days=90, research_cache_ttl_days=30))
    old=(datetime.now(timezone.utc)-timedelta(days=91)).isoformat()
    with store._connect() as conn:
        conn.execute("INSERT INTO reports (input_hash,ruleset_version,score,band,findings_json,created_at,analysis_id) VALUES ('hash','rules',0,'gray','[]',?,'expired')", (old,))
        conn.execute("INSERT INTO audit_log (input_hash,ruleset_version,output_json,created_at,analysis_id) VALUES ('hash','rules','{}',?,'expired')", (old,))
    deleted=store.purge_expired()
    assert deleted["reports"] == deleted["audit_log"] == 1

    app=create_app(db_path=tmp_path/"status.sqlite", ai_settings=AISettings(enabled=False), retention_days=90)
    status=TestClient(app).get("/operations/status").json()
    assert status["retention"] == {
        "days": 90,
        "configurable": True,
        "scope": "candidate_analysis_data",
    }


def test_request_metrics_and_correlation_id_are_exposed_without_request_content(tmp_path, caplog):
    app=create_app(db_path=tmp_path/"metrics.sqlite", ai_settings=AISettings(enabled=False))
    client=TestClient(app)
    correlation_id="b6406cc0-06d8-4cf5-a541-cfde4857b451"
    response=client.get("/health", headers={"X-Correlation-ID":correlation_id})
    assert response.headers["X-Correlation-ID"] == correlation_id
    metrics=client.get("/operations/metrics").json()
    assert metrics["counters"]["requests_total|/health|200"] == 1
    assert "OPENAI_API_KEY" not in caplog.text


def test_untrusted_correlation_and_path_values_never_become_telemetry_labels(tmp_path, caplog):
    marker="90010112345"
    app=create_app(db_path=tmp_path/"safe-metrics.sqlite", ai_settings=AISettings(enabled=False))
    client=TestClient(app)
    response=client.get(f"/unknown/{marker}", headers={"X-Correlation-ID":marker})
    assert response.status_code == 404 and response.headers["X-Correlation-ID"] != marker
    snapshot=app.state.telemetry.snapshot()
    assert marker not in json.dumps(snapshot) and marker not in caplog.text
