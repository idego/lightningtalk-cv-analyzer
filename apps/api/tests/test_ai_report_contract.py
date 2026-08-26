from __future__ import annotations

import json
import io
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from docx import Document
from fastapi.testclient import TestClient

from cv_validator.ai.config import AISettings
from cv_validator.ai.application import DocumentAnalyzerClientError
from cv_validator.ai.domain import (
    AIAnalysisStatus,
    AIDocumentAnalysisOutcome,
    AIFailureReason,
    ValidatedDocumentAnalysis,
    DocumentAnalyzerResponse,
)
from cv_validator.ai.request import (
    DETERMINISTIC_OBSERVATIONS_VERSION,
    INPUT_CONTRACT_VERSION,
    PROMPT_VERSION,
    SCHEMA_VERSION,
)
from cv_validator.api.app import create_app
from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.research.company import RESEARCH_VERSION as COMPANY_RESEARCH_VERSION
from cv_validator.research.education import RESEARCH_VERSION as EDUCATION_RESEARCH_VERSION
from cv_validator.research.linkedin import COMPARISON_VERSION, DISCOVERY_VERSION
from cv_validator.pipeline import analyze_cv_text_result
from cv_validator.serialization import serialize_analysis_payload


CHECK_IDS = (
    "contact",
    "education",
    "employment",
    "timeline",
    "duration_claims",
    "relationships",
    "document_quality",
    "protected_boundaries",
)


def _successful_result():
    result = analyze_cv_text_result(
        "Candidate Example\nExperience Experience\nSoftware engineer profile"
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "facts": {"contact": [], "education": [], "employment": []},
        "findings": [
            {
                "category": "document_artifact",
                "check_id": "document_quality",
                "status": "unconfirmed",
                "observation": "A heading is repeated.",
                "reason": "The same heading appears twice on one line.",
                "importance": "worth_knowing",
                "confidence": "high",
                "limitation": "Formatting may explain the repetition.",
                "authority": "ai",
                "source": "document_analyzer",
                "evidence": [
                    {
                        "page_id": "page-0001",
                        "line_id": "page-0001-line-0002",
                        "excerpt": "Experience Experience",
                    }
                ],
            }
        ],
        "unknowns": [],
        "research_candidates": [],
        "checklist": {
            check_id: {
                "checked": True,
                "issue_count": 1 if check_id == "document_quality" else 0,
            }
            for check_id in CHECK_IDS
        },
        "analysis_limitations": ["Only the supplied document was analyzed."],
    }
    return replace(
        result,
        ai_outcome=AIDocumentAnalysisOutcome(
            status=AIAnalysisStatus.SUCCEEDED,
            analysis=ValidatedDocumentAnalysis(
                schema_version=SCHEMA_VERSION,
                payload=payload,
            ),
            response_model="gpt-5.6-luna-runtime",
            usage={"input_tokens": 123, "output_tokens": 45},
        ),
    )


def _docx_bytes(text: str) -> bytes:
    document = Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


class _Analyzer:
    def __init__(self) -> None:
        self.requests = []

    def analyze(self, request):
        self.requests.append(request)
        return DocumentAnalyzerResponse(
            payload={
                "schema_version": SCHEMA_VERSION,
                "facts": {"contact": [], "education": [], "employment": []},
                "findings": [],
                "unknowns": [],
                "analysis_limitations": [],
            },
            response_model="gpt-5.6-luna-runtime",
            usage={"input_tokens": 20, "output_tokens": 5},
        )


class _PayloadAnalyzer:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def analyze(self, request):
        return DocumentAnalyzerResponse(
            payload=self.payload,
            response_model="gpt-5.6-luna-runtime",
            usage={"input_tokens": 20, "output_tokens": 5},
        )


class _BlockingAnalyzer(_Analyzer):
    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def analyze(self, request):
        self.started.set()
        assert self.release.wait(timeout=2)
        return super().analyze(request)


class _BlockingFailureAnalyzer(_BlockingAnalyzer):
    def analyze(self, request):
        self.requests.append(request)
        self.started.set()
        assert self.release.wait(timeout=2)
        raise DocumentAnalyzerClientError(
            retryable=False,
            http_status_class="4xx",
            provider_request_id="req-safe-shared",
        )


def test_analysis_payload_is_additive_complete_and_deterministic_invariant() -> None:
    result = _successful_result()
    deterministic_before = result.report.to_dict()

    payload = serialize_analysis_payload(
        result,
        AISettings(enabled=True, api_key="test-key"),
        analysis_id="analysis-test-1",
    )

    assert {key: payload[key] for key in deterministic_before} == deterministic_before
    assert result.report.to_dict() == deterministic_before
    assert payload["analysis_id"] == "analysis-test-1"
    assert payload["ai_analysis"]["status"] == "succeeded"
    assert payload["ai_analysis"]["authority"] == "ai"
    assert payload["ai_analysis"]["versions"] == {
        "prompt": PROMPT_VERSION,
        "schema": SCHEMA_VERSION,
        "input_contract": INPUT_CONTRACT_VERSION,
        "deterministic_observations": DETERMINISTIC_OBSERVATIONS_VERSION,
    }
    assert payload["ai_analysis"]["usage"] == {
        "input_tokens": 123,
        "output_tokens": 45,
    }
    assert set(payload["checklist"]["checks"]) == set(CHECK_IDS)
    assert payload["checklist"]["checks"]["document_quality"] == {
        "checked": True,
        "issue_count": 1,
    }
    ai_flag = next(flag for flag in payload["checklist"]["flags"] if flag["source"] == "ai")
    assert ai_flag["importance"] == "worth_knowing"
    assert ai_flag["evidence"][0]["excerpt"] == "Experience Experience"


def test_failed_analysis_has_a_complete_graceful_contract() -> None:
    result = analyze_cv_text_result("Candidate Example\nSoftware engineer profile")
    result = replace(
        result,
        ai_outcome=AIDocumentAnalysisOutcome(
            status=AIAnalysisStatus.FAILED,
            failure_reason=AIFailureReason.REFUSAL,
            response_model="gpt-5.6-luna-runtime",
            usage={"input_tokens": 10, "output_tokens": 0},
            failure_stage="provider_response",
            retryable=False,
            attempt_count=1,
            latency_ms=12.5,
        ),
    )

    payload = serialize_analysis_payload(
        result,
        AISettings(enabled=True, api_key="test-key"),
        analysis_id="analysis-test-2",
    )

    assert payload["ai_analysis"]["status"] == "failed"
    assert payload["ai_analysis"]["failure_reason"] == "refusal"
    assert payload["ai_analysis"]["failure"] == {
        "stage": "provider_response",
        "retryable": False,
        "http_status_class": None,
        "provider_request_id": None,
        "attempt_count": 1,
        "latency_ms": 12.5,
    }
    assert payload["ai_analysis"]["manual_retry_available"] is True
    assert payload["ai_analysis"]["findings"] == []
    assert payload["ai_analysis"]["facts"] == {
        "contact": [],
        "education": [],
        "employment": [],
    }
    assert all(
        check == {"checked": False, "issue_count": 0}
        for check in payload["checklist"]["checks"].values()
    )


def test_deferred_ai_returns_pending_deterministic_report_without_calling_provider() -> None:
    analyzer = _Analyzer()

    result = analyze_cv_text_result(
        "Candidate Example\nPhone: +48 22 123 45 67\nSoftware engineer profile",
        ai_settings=AISettings(enabled=True, api_key="test-key"),
        document_analyzer=analyzer,
        defer_ai=True,
    )
    payload = serialize_analysis_payload(
        result,
        AISettings(enabled=True, api_key="test-key"),
        analysis_id="analysis-pending-1",
    )

    assert analyzer.requests == []
    assert payload["ai_analysis"]["status"] == "pending"
    assert payload["ai_analysis"]["manual_retry_available"] is False
    assert payload["deterministic"]["facts"]
    assert payload["deterministic"]["scoring_signals"]


def test_pending_ai_enrichment_reuses_the_same_analysis_and_deterministic_report(
    tmp_path,
) -> None:
    db_path = tmp_path / "pending-enrichment.db"
    token = "owner-token"
    settings = AISettings(enabled=True, api_key="test-key")
    analyzer = _Analyzer()
    pending = analyze_cv_text_result(
        "Candidate Example\nPhone: +48 22 123 45 67\nSoftware engineer profile",
        ai_settings=settings,
        document_analyzer=analyzer,
        defer_ai=True,
    )
    pending_payload = serialize_analysis_payload(
        pending,
        settings,
        analysis_id="analysis-pending-2",
    )
    store = PersistenceStore(PersistenceConfig(db_path, retention_days=30))
    store.persist_report(
        pending.document_identity,
        pending.report,
        report_payload=pending_payload,
        analysis_id="analysis-pending-2",
        ai_analysis=pending_payload["ai_analysis"],
        access_token=token,
    )
    app = create_app(
        db_path=db_path,
        ai_settings=settings,
        document_analyzer=analyzer,
    )
    app.state.ai_retry_contexts["analysis-pending-2"] = pending
    endpoint = next(
        route.endpoint
        for route in app.routes
        if getattr(route, "path", None) == "/analyses/{analysis_id}/ai/retry"
    )

    response = endpoint("analysis-pending-2", token)
    enriched = json.loads(response.body)

    assert enriched["analysis_id"] == pending_payload["analysis_id"]
    assert enriched["ai_analysis"]["status"] == "succeeded"
    assert enriched["deterministic"] == pending_payload["deterministic"]
    assert enriched["score"] == pending_payload["score"]
    assert enriched["band"] == pending_payload["band"]
    assert len(analyzer.requests) == 1


def test_manual_ai_retry_replaces_only_ai_result_and_keeps_deterministic_report(
    tmp_path,
) -> None:
    db_path = tmp_path / "retry.db"
    token = "owner-token"
    baseline = analyze_cv_text_result(
        "Candidate Example\nExperienced software engineer profile"
    )
    failed = replace(
        baseline,
        ai_outcome=AIDocumentAnalysisOutcome(
            status=AIAnalysisStatus.FAILED,
            failure_reason=AIFailureReason.TIMEOUT,
            failure_stage="transport",
            retryable=True,
            attempt_count=2,
        ),
    )
    failed_payload = serialize_analysis_payload(
        failed,
        AISettings(enabled=True, api_key="test-key"),
        analysis_id="analysis-retry-1",
    )
    store = PersistenceStore(PersistenceConfig(db_path, retention_days=30))
    store.persist_report(
        failed.document_identity,
        failed.report,
        report_payload=failed_payload,
        analysis_id="analysis-retry-1",
        ai_analysis=failed_payload["ai_analysis"],
        access_token=token,
    )
    analyzer = _Analyzer()
    app = create_app(
        db_path=db_path,
        ai_settings=AISettings(enabled=True, api_key="test-key"),
        document_analyzer=analyzer,
    )
    app.state.ai_retry_contexts["analysis-retry-1"] = failed
    endpoint = next(
        route.endpoint
        for route in app.routes
        if getattr(route, "path", None) == "/analyses/{analysis_id}/ai/retry"
    )

    response = endpoint("analysis-retry-1", token)
    payload = json.loads(response.body)

    assert payload["ai_analysis"]["status"] == "succeeded"
    assert payload["score"] == failed_payload["score"]
    assert payload["band"] == failed_payload["band"]
    assert payload["deterministic"] == failed_payload["deterministic"]
    assert len(analyzer.requests) == 1
    assert "analysis-retry-1" not in app.state.ai_retry_contexts
    persisted = store.get_analysis_payload("analysis-retry-1")
    assert persisted == payload


def test_concurrent_manual_retry_waiters_share_one_provider_success(tmp_path) -> None:
    db_path = tmp_path / "retry-concurrent.db"
    token = "owner-token"
    baseline = analyze_cv_text_result("Candidate Example\nExperienced software engineer profile")
    failed = replace(
        baseline,
        ai_outcome=AIDocumentAnalysisOutcome(
            status=AIAnalysisStatus.FAILED,
            failure_reason=AIFailureReason.TIMEOUT,
            failure_stage="transport",
            retryable=True,
            attempt_count=2,
        ),
    )
    failed_payload = serialize_analysis_payload(
        failed,
        AISettings(enabled=True, api_key="test-key"),
        analysis_id="analysis-retry-concurrent",
    )
    store = PersistenceStore(PersistenceConfig(db_path, retention_days=30))
    store.persist_report(
        failed.document_identity,
        failed.report,
        report_payload=failed_payload,
        analysis_id="analysis-retry-concurrent",
        ai_analysis=failed_payload["ai_analysis"],
        access_token=token,
    )
    analyzer = _BlockingAnalyzer()
    app = create_app(
        db_path=db_path,
        ai_settings=AISettings(enabled=True, api_key="test-key"),
        document_analyzer=analyzer,
    )
    app.state.ai_retry_contexts["analysis-retry-concurrent"] = failed
    endpoint = next(
        route.endpoint for route in app.routes
        if getattr(route, "path", None) == "/analyses/{analysis_id}/ai/retry"
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(endpoint, "analysis-retry-concurrent", token)
        assert analyzer.started.wait(timeout=1)
        second = pool.submit(endpoint, "analysis-retry-concurrent", token)
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            flight = app.state.ai_retry_flights.get("analysis-retry-concurrent")
            if flight is not None and flight.waiters == 2:
                break
            time.sleep(0.005)
        assert app.state.ai_retry_flights["analysis-retry-concurrent"].waiters == 2
        analyzer.release.set()
        first_payload = json.loads(first.result(timeout=2).body)
        second_payload = json.loads(second.result(timeout=2).body)

    assert first_payload == second_payload
    assert first_payload["ai_analysis"]["status"] == "succeeded"
    assert len(analyzer.requests) == 1
    assert "analysis-retry-concurrent" not in app.state.ai_retry_flights


def test_concurrent_manual_retry_waiters_share_one_provider_failure(tmp_path) -> None:
    db_path = tmp_path / "retry-concurrent-failure.db"
    token = "owner-token"
    baseline = analyze_cv_text_result("Candidate Example\nExperienced software engineer profile")
    failed = replace(
        baseline,
        ai_outcome=AIDocumentAnalysisOutcome(
            status=AIAnalysisStatus.FAILED,
            failure_reason=AIFailureReason.TIMEOUT,
            failure_stage="transport",
            retryable=True,
            attempt_count=2,
        ),
    )
    failed_payload = serialize_analysis_payload(
        failed,
        AISettings(enabled=True, api_key="test-key"),
        analysis_id="analysis-retry-failure",
    )
    store = PersistenceStore(PersistenceConfig(db_path, retention_days=30))
    store.persist_report(
        failed.document_identity,
        failed.report,
        report_payload=failed_payload,
        analysis_id="analysis-retry-failure",
        ai_analysis=failed_payload["ai_analysis"],
        access_token=token,
    )
    analyzer = _BlockingFailureAnalyzer()
    app = create_app(
        db_path=db_path,
        ai_settings=AISettings(enabled=True, api_key="test-key"),
        document_analyzer=analyzer,
    )
    app.state.ai_retry_contexts["analysis-retry-failure"] = failed
    endpoint = next(
        route.endpoint for route in app.routes
        if getattr(route, "path", None) == "/analyses/{analysis_id}/ai/retry"
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(endpoint, "analysis-retry-failure", token)
        assert analyzer.started.wait(timeout=1)
        second = pool.submit(endpoint, "analysis-retry-failure", token)
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            flight = app.state.ai_retry_flights.get("analysis-retry-failure")
            if flight is not None and flight.waiters == 2:
                break
            time.sleep(0.005)
        assert app.state.ai_retry_flights["analysis-retry-failure"].waiters == 2
        analyzer.release.set()
        first_payload = json.loads(first.result(timeout=2).body)
        second_payload = json.loads(second.result(timeout=2).body)

    assert first_payload == second_payload
    assert first_payload["ai_analysis"]["status"] == "failed"
    assert first_payload["ai_analysis"]["failure_reason"] == "client_error"
    assert len(analyzer.requests) == 1
    assert "analysis-retry-failure" in app.state.ai_retry_contexts
    assert "analysis-retry-failure" not in app.state.ai_retry_flights


def test_purge_during_failed_retry_cannot_restore_retry_state(tmp_path) -> None:
    db_path = tmp_path / "retry-purge-race.db"
    token = "owner-token"
    analysis_id = "analysis-retry-purged"
    baseline = analyze_cv_text_result("Candidate Example\nExperienced software engineer profile")
    failed = replace(
        baseline,
        ai_outcome=AIDocumentAnalysisOutcome(
            status=AIAnalysisStatus.FAILED,
            failure_reason=AIFailureReason.TIMEOUT,
            failure_stage="transport",
            retryable=True,
            attempt_count=2,
        ),
    )
    failed_payload = serialize_analysis_payload(
        failed,
        AISettings(enabled=True, api_key="test-key"),
        analysis_id=analysis_id,
    )
    store = PersistenceStore(PersistenceConfig(db_path, retention_days=1))
    store.persist_report(
        failed.document_identity,
        failed.report,
        report_payload=failed_payload,
        analysis_id=analysis_id,
        ai_analysis=failed_payload["ai_analysis"],
        access_token=token,
    )
    analyzer = _BlockingFailureAnalyzer()
    app = create_app(
        db_path=db_path,
        retention_days=1,
        ai_settings=AISettings(enabled=True, api_key="test-key"),
        document_analyzer=analyzer,
    )
    store = app.state.store
    app.state.ai_retry_contexts[analysis_id] = failed
    endpoint = next(
        route.endpoint for route in app.routes
        if getattr(route, "path", None) == "/analyses/{analysis_id}/ai/retry"
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(endpoint, analysis_id, token)
        assert analyzer.started.wait(timeout=1)
        second = pool.submit(endpoint, analysis_id, token)
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            flight = app.state.ai_retry_flights.get(analysis_id)
            if flight is not None and flight.waiters == 2:
                break
            time.sleep(0.005)
        assert app.state.ai_retry_flights[analysis_id].waiters == 2

        old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        with store._connect() as conn:
            conn.execute("UPDATE reports SET created_at = ? WHERE analysis_id = ?", (old, analysis_id))
            conn.execute("UPDATE audit_log SET created_at = ? WHERE analysis_id = ?", (old, analysis_id))
        purge = store.purge_expired()
        assert purge["analysis_ids"] == (analysis_id,)
        assert store.get_analysis_payload(analysis_id) is None
        analyzer.release.set()

        for waiter in (first, second):
            with pytest.raises(Exception) as unavailable:
                waiter.result(timeout=2)
            assert getattr(unavailable.value, "status_code", None) == 409
            assert getattr(unavailable.value, "detail", None) == "ai_retry_context_unavailable"

    assert len(analyzer.requests) == 1
    assert store.get_analysis_payload(analysis_id) is None
    assert analysis_id not in app.state.ai_retry_contexts
    assert analysis_id not in app.state.ai_retry_locks
    assert analysis_id not in app.state.ai_retry_flights
    assert analysis_id not in app.state.ai_retry_invalidated


def test_purge_on_new_persist_removes_db_retry_context_lock_and_flight(tmp_path) -> None:
    app = create_app(db_path=tmp_path / "purge-persist.db", retention_days=1)
    store = app.state.store
    expired = analyze_cv_text_result("Expired Candidate\nSoftware engineer profile")
    expired_payload = serialize_analysis_payload(expired, AISettings(), analysis_id="expired-persist")
    store.persist_report(
        expired.document_identity,
        expired.report,
        report_payload=expired_payload,
        analysis_id="expired-persist",
        access_token="owner-token",
    )
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    with store._connect() as conn:
        conn.execute("UPDATE reports SET created_at = ? WHERE analysis_id = ?", (old, "expired-persist"))
        conn.execute("UPDATE audit_log SET created_at = ? WHERE analysis_id = ?", (old, "expired-persist"))
    app.state.ai_retry_contexts["expired-persist"] = expired
    app.state.ai_retry_locks["expired-persist"] = threading.Lock()
    app.state.ai_retry_flights["expired-persist"] = object()

    fresh = analyze_cv_text_result("Fresh Candidate\nSoftware engineer profile")
    fresh_payload = serialize_analysis_payload(fresh, AISettings(), analysis_id="fresh-persist")
    store.persist_report(
        fresh.document_identity,
        fresh.report,
        report_payload=fresh_payload,
        analysis_id="fresh-persist",
        access_token="owner-token",
    )

    assert store.get_analysis_payload("expired-persist") is None
    assert "expired-persist" not in app.state.ai_retry_contexts
    assert "expired-persist" not in app.state.ai_retry_locks
    assert "expired-persist" not in app.state.ai_retry_flights


def test_retention_change_returns_ids_and_removes_db_and_retry_state(tmp_path) -> None:
    app = create_app(db_path=tmp_path / "purge-retention.db", retention_days=30)
    store = app.state.store
    expired = analyze_cv_text_result("Expired Candidate\nSoftware engineer profile")
    payload = serialize_analysis_payload(expired, AISettings(), analysis_id="expired-retention")
    store.persist_report(
        expired.document_identity,
        expired.report,
        report_payload=payload,
        analysis_id="expired-retention",
        access_token="owner-token",
    )
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    with store._connect() as conn:
        conn.execute("UPDATE reports SET created_at = ? WHERE analysis_id = ?", (old, "expired-retention"))
        conn.execute("UPDATE audit_log SET created_at = ? WHERE analysis_id = ?", (old, "expired-retention"))
    app.state.ai_retry_contexts["expired-retention"] = expired
    app.state.ai_retry_locks["expired-retention"] = threading.Lock()
    app.state.ai_retry_flights["expired-retention"] = object()

    purge = store.set_retention_days(1)

    assert purge["analysis_ids"] == ("expired-retention",)
    assert store.get_analysis_payload("expired-retention") is None
    assert "expired-retention" not in app.state.ai_retry_contexts
    assert "expired-retention" not in app.state.ai_retry_locks
    assert "expired-retention" not in app.state.ai_retry_flights


def test_reopened_analysis_hydrates_owner_scoped_completed_research(tmp_path) -> None:
    app = create_app(db_path=tmp_path / "research-reopen.db")
    store = app.state.store
    base = {
        "analysis_id": "analysis-reopen",
        "score": 50,
        "band": "gray",
        "ai_analysis": {"status": "succeeded", "facts": {"contact": [], "education": [], "employment": []}, "research_candidates": []},
    }
    store.persist_analysis_payload_for_test(base)
    common = {
        "status": "completed",
        "accessed_at": "2026-08-25T00:00:00+00:00",
        "usage": {"input_tokens": 1},
        "model": {"configured": "fake", "response": "fake"},
    }
    company = {**common, "kind": "company", "versions": {"research": COMPANY_RESEARCH_VERSION, "prompt": "p", "schema": "s"}}
    education = {**common, "kind": "education", "versions": {"research": EDUCATION_RESEARCH_VERSION, "prompt": "p", "schema": "s"}}
    linkedin = {**common, "kind": "linkedin", "versions": {"research": DISCOVERY_VERSION, "prompt": "p", "schema": "s"}}
    linkedin_comparison = {**common, "kind": "linkedin_comparison", "versions": {"research": COMPARISON_VERSION, "prompt": "p", "schema": "s"}}
    store.persist_company_research("analysis-reopen", company)
    store.persist_education_research("analysis-reopen", education)
    store.persist_linkedin_discovery("analysis-reopen", linkedin)
    store.persist_linkedin_comparison(
        "analysis-reopen",
        "https://www.linkedin.com/in/example",
        linkedin_comparison,
    )
    endpoint = next(
        route.endpoint for route in app.routes
        if getattr(route, "path", None) == "/analyses/{analysis_id}"
    )

    payload = json.loads(endpoint("analysis-reopen", "test-access-token").body)

    assert payload["company_research"] == company
    assert payload["education_research"] == education
    assert payload["linkedin_discovery"] == linkedin
    assert payload["linkedin_comparison"] == linkedin_comparison
    assert "analysis_access_token" not in payload
    assert "access_token_hash" not in json.dumps(payload)
    with pytest.raises(Exception) as denied:
        endpoint("analysis-reopen", "other-owner-token")
    assert getattr(denied.value, "status_code", None) == 404


def test_every_code_observation_is_exposed_as_a_remaining_review_flag(
    location_resolver,
) -> None:
    result = analyze_cv_text_result(
        "Candidate Example\n"
        "Employer location: Berlin\n"
        "Employer location: Warsaw\n"
        "Client location: Berlin\n"
        "Experienced software engineer",
        location_resolver=location_resolver,
    )
    payload = serialize_analysis_payload(
        result,
        AISettings(enabled=False),
        analysis_id="analysis-observations",
    )

    observations = payload["deterministic"]["observations"]
    observation_flags = [
        flag for flag in payload["checklist"]["flags"]
        if flag["id"].startswith("code-observation-")
    ]
    assert len(observation_flags) == len(observations)
    assert sum(observation["kind"] == "location" for observation in observations) >= 3
    for observation, flag in zip(observations, observation_flags):
        assert flag["category"] == observation["kind"]
        assert flag["status"] == observation["status"]
        assert flag["importance"] == "remaining"
        assert flag["observation"] == (
            ", ".join(observation["values"]) or observation["kind"]
        )
        assert flag["reason"] == observation["reason"]
        assert flag["evidence"] == observation["evidence"]


def test_partial_validation_never_persists_rejected_model_text(tmp_path) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "facts": {
            "contact": [],
            "education": [
                {
                    "kind": "education",
                    "institution": {
                        "value": "Example University",
                        "line_ids": ["page-0001-line-0004"],
                    },
                    "program": {
                        "value": "UNSUPPORTED PRIVATE TEXT",
                        "line_ids": ["page-0001-line-0001"],
                    },
                    "study_dates": {"value": None, "line_ids": []},
                    "status": "present",
                }
            ],
            "employment": [],
        },
        "findings": [
            {
                "category": "document_artifact",
                "status": "unconfirmed",
                "observation": "UNSUPPORTED PRIVATE TEXT is mentioned.",
                "reason": "UNSUPPORTED PRIVATE TEXT was not confirmed.",
                "importance": "worth_knowing",
                    "confidence": "medium",
                    "limitation": "The source is incomplete.",
                    "material_effect": "important_fact_unreadable",
                    "affected_fact": "education",
                    "evidence": [
                    {"page_id": "page-0001", "line_id": "page-0001-line-0005"}
                ],
            }
        ],
        "unknowns": [],
        "analysis_limitations": [],
    }
    app = create_app(
        db_path=tmp_path / "leak.db",
        ai_settings=AISettings(enabled=True, api_key="test-key"),
        document_analyzer=_PayloadAnalyzer(payload),
    )
    token = "partial-validation-owner"
    with TestClient(app) as client:
        initial = client.post(
            "/analyze",
            files={
                "file": (
                    "candidate.docx",
                    _docx_bytes(
                        "Candidate Example\nExperienced software engineer profile\n"
                        "Education\nExample University\nTimeline"
                    ),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            headers={"X-Analysis-Access-Token": token},
        )
        response = client.post(
            f"/analyses/{initial.json()['analysis_id']}/ai/retry",
            headers={"X-Analysis-Access-Token": token},
        )

    assert response.status_code == 200
    response_text = response.text
    audit_text = app.state.store.get_audit_entries()[0]["output_json"]
    assert "UNSUPPORTED PRIVATE TEXT" not in response_text
    assert "UNSUPPORTED PRIVATE TEXT" not in audit_text
    serialized = response.json()
    assert serialized["ai_analysis"]["validation_warnings"]
    education = serialized["ai_analysis"]["facts"]["education"][0]
    assert "evidence" not in education
    assert education["field_evidence"]["institution"][0]["excerpt"] == "Example University"


def test_ai_analysis_is_linked_to_report_and_audit_in_sqlite(tmp_path) -> None:
    result = _successful_result()
    settings = AISettings(enabled=True, api_key="test-key")
    payload = serialize_analysis_payload(
        result,
        settings,
        analysis_id="analysis-test-3",
    )
    store = PersistenceStore(PersistenceConfig(tmp_path / "analysis.db"))

    stored_id = store.persist_report(
        result.document_identity,
        result.report,
        report_payload=payload,
        analysis_id="analysis-test-3",
        ai_analysis=payload["ai_analysis"],
    )

    assert stored_id == "analysis-test-3"
    audit = store.get_audit_entries()[0]
    assert audit["analysis_id"] == stored_id
    assert json.loads(audit["output_json"]) == payload
    stored_ai = store.get_ai_analysis(stored_id)
    assert stored_ai is not None
    assert stored_ai["status"] == "succeeded"
    assert stored_ai["prompt_version"] == PROMPT_VERSION
    assert stored_ai["schema_version"] == SCHEMA_VERSION
    assert stored_ai["deterministic_observations_version"] == (
        DETERMINISTIC_OBSERVATIONS_VERSION
    )
    assert json.loads(stored_ai["usage_json"])["input_tokens"] == 123
    assert json.loads(stored_ai["result_json"])["findings"][0]["authority"] == "ai"


def test_existing_database_is_migrated_without_losing_old_rows(tmp_path) -> None:
    db_path = tmp_path / "old.db"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                input_hash TEXT NOT NULL,
                ruleset_version TEXT NOT NULL,
                score INTEGER NOT NULL,
                band TEXT NOT NULL,
                findings_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                input_hash TEXT NOT NULL,
                ruleset_version TEXT NOT NULL,
                output_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            INSERT INTO reports VALUES (1, 'old', '1.0.0', 50, 'gray', '[]', '2026-08-21T00:00:00+00:00');
            INSERT INTO audit_log VALUES (1, 'old', '1.0.0', '{"band":"gray"}', '2026-08-21T00:00:00+00:00');
            """
        )

    store = PersistenceStore(PersistenceConfig(db_path, retention_days=36500))

    with sqlite3.connect(db_path) as connection:
        report = connection.execute(
            "SELECT input_hash, analysis_id FROM reports WHERE id = 1"
        ).fetchone()
        audit = connection.execute(
            "SELECT input_hash, analysis_id FROM audit_log WHERE id = 1"
        ).fetchone()
        ai_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ai_analyses'"
        ).fetchone()
    assert report == ("old", "legacy-1")
    assert audit == ("old", "legacy-1")
    assert ai_table == ("ai_analyses",)
    assert json.loads(store.get_audit_entries()[0]["output_json"]) == {"band": "gray"}


def test_http_response_and_audit_share_one_stable_analysis_id(tmp_path) -> None:
    from cv_validator.api.app import create_app

    app = create_app(
        db_path=tmp_path / "api.db",
        ai_settings=AISettings(enabled=True, api_key="test-key"),
        document_analyzer=_Analyzer(),
    )
    token = "stable-id-owner"

    with TestClient(app) as client:
        initial = client.post(
            "/analyze",
            files={
                "file": (
                    "candidate.docx",
                    _docx_bytes("Candidate Example\nSoftware engineer profile"),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            headers={"X-Analysis-Access-Token": token},
        )
        assert initial.json()["ai_analysis"]["status"] == "pending"
        response = client.post(
            f"/analyses/{initial.json()['analysis_id']}/ai/retry",
            headers={"X-Analysis-Access-Token": token},
        )

    assert response.status_code == 200
    payload = response.json()
    analysis_id = payload["analysis_id"]
    assert analysis_id
    assert payload["ai_analysis"]["status"] == "succeeded"
    assert payload["ai_analysis"]["model"]["response"] == "gpt-5.6-luna-runtime"
    audit = app.state.store.get_audit_entries()[0]
    assert audit["analysis_id"] == analysis_id
    assert json.loads(audit["output_json"]) == payload
    assert app.state.store.get_ai_analysis(analysis_id)["analysis_id"] == analysis_id


def test_enabled_ai_cannot_change_deterministic_api_fields(tmp_path) -> None:
    from cv_validator.api.app import create_app

    content = _docx_bytes(
        "Candidate Example\nCurrent location: Berlin, Germany\n"
        "Phone: +49 30 123456\nSoftware engineer profile"
    )
    disabled_app = create_app(db_path=tmp_path / "disabled.db")
    enabled_app = create_app(
        db_path=tmp_path / "enabled.db",
        ai_settings=AISettings(enabled=True, api_key="test-key"),
        document_analyzer=_Analyzer(),
    )

    with TestClient(disabled_app) as disabled_client:
        disabled = disabled_client.post(
            "/analyze",
            files={"file": ("cv.docx", content, "application/octet-stream")},
        ).json()
    with TestClient(enabled_app) as enabled_client:
        enabled = enabled_client.post(
            "/analyze",
            files={"file": ("cv.docx", content, "application/octet-stream")},
        ).json()

    immutable_keys = (
        "score",
        "band",
        "claimed_location",
        "findings",
        "ruleset_version",
        "signal_count",
        "supporting_count",
        "conflicting_count",
        "deterministic",
    )
    disabled_bytes = json.dumps(
        {key: disabled[key] for key in immutable_keys},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    enabled_bytes = json.dumps(
        {key: enabled[key] for key in immutable_keys},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert enabled_bytes == disabled_bytes


def test_bounded_four_cv_batch_has_independent_ids_and_persisted_ai(tmp_path) -> None:
    from cv_validator.api.app import create_app

    analyzer = _Analyzer()
    app = create_app(
        db_path=tmp_path / "batch.db",
        ai_settings=AISettings(enabled=True, api_key="test-key"),
        document_analyzer=analyzer,
        batch_max_files=4,
    )
    files = [
        (
            "files",
            (
                f"candidate-{number}.docx",
                _docx_bytes(
                    f"Candidate {number}\nExperienced software engineer profile"
                ),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        )
        for number in range(4)
    ]
    token = "batch-owner"

    with TestClient(app) as client:
        response = client.post(
            "/analyze/batch",
            files=files,
            headers={"X-Analysis-Access-Token": token},
        )
        initial_results = response.json()["results"]
        assert all(
            item["report"]["ai_analysis"]["status"] == "pending"
            for item in initial_results
        )
        assert analyzer.requests == []
        enriched = [
            client.post(
                f"/analyses/{item['report']['analysis_id']}/ai/retry",
                headers={"X-Analysis-Access-Token": token},
            ).json()
            for item in initial_results
        ]

    assert response.status_code == 200
    results = response.json()["results"]
    assert all(item["status"] == "ok" for item in results)
    analysis_ids = [item["report"]["analysis_id"] for item in results]
    assert len(set(analysis_ids)) == 4
    assert len(analyzer.requests) == 4
    assert all(item["ai_analysis"]["status"] == "succeeded" for item in enriched)
    assert len(app.state.store.get_audit_entries()) == 4
    assert all(app.state.store.get_ai_analysis(item) is not None for item in analysis_ids)
