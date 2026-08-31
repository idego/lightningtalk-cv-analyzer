from __future__ import annotations

import os
import json
import hmac
import threading
import secrets
from concurrent.futures import Future
from dataclasses import replace
from time import perf_counter
from copy import deepcopy
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel
from fastapi.responses import JSONResponse

from cv_validator.ai.application import DocumentAnalyzer
from cv_validator.ai.application import run_document_analysis
from cv_validator.ai.config import AISettings, load_ai_settings
from cv_validator.ai.openai_client import OpenAIResponsesDocumentAnalyzer
from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.api.feedback import FeedbackInput, FeedbackStore, TriageInput
from cv_validator.config import (
    load_ingestion_config,
    load_link_check_config,
    load_location_resolver,
)
from cv_validator.file_links.checker import (
    DNSResolver,
    LinkCheckConfig,
    LinkHTTPClient,
    LinkInspector,
)
from cv_validator.ingestion import IngestionError
from cv_validator.pipeline import PipelineResult, analyze_cv_bytes_result
from cv_validator.ai.domain import AIAnalysisStatus
from cv_validator.location import LocationResolver, SQLiteLocationResolver
from cv_validator.errors import (
    AnalysisNotFoundPersistenceError,
    AnalysisRuntimeError,
    PersistenceError,
    UploadReadError,
)
from cv_validator.serialization import serialize_analysis_payload
from cv_validator.research.company import CompanyResearchService, build_company_research_request
from cv_validator.research.domain import CompanyResearchClientError, CompanyResearchInvalidResponse, CompanyResearchTimeout
from cv_validator.research.openai_client import OpenAIResponsesCompanyResearcher
from cv_validator.research.education import (
    EducationResearchService,
    apply_owner_scoped_education_context,
    build_education_research_request,
    normalize_public_education_result,
)
from cv_validator.research.cache import (
    company_cache_descriptor, education_cache_descriptor, materialize_cache_hit,
    reusable_payload,
)
from cv_validator.research.domain import EducationResearchClientError, EducationResearchInvalidResponse, EducationResearchTimeout
from cv_validator.research.openai_client import OpenAIResponsesEducationResearcher
from cv_validator.research.linkedin import DEFAULT_MAX_PROFILES, MAX_PROFILES_LIMIT, LinkedInDiscoveryService
from cv_validator.research.domain import LinkedInResearchClientError, LinkedInResearchInvalidResponse, LinkedInResearchTimeout
from cv_validator.research.openai_client import OpenAIResponsesLinkedInResearcher
from cv_validator.operations import OperationsTelemetry, safe_log

DEFAULT_DB = Path("data/cv_validator.db")
DEFAULT_BATCH_MAX_FILES = 4
DEFAULT_BATCH_MAX_BYTES = 20 * 1024 * 1024


class _RetentionUpdate(BaseModel):
    days: int


@dataclass(frozen=True)
class _PreparedUpload:
    upload: UploadFile
    content: bytes | None
    error: str | None = None


@dataclass
class _RetryFlight:
    future: Future[dict]
    waiters: int = 1


@dataclass
class _ResearchLockEntry:
    lock: threading.Lock
    users: int = 0


class _ResearchLockLease:
    def __init__(self, registry: _ResearchLockRegistry, key: str, entry: _ResearchLockEntry) -> None:
        self._registry = registry
        self._key = key
        self._entry = entry

    def __enter__(self) -> _ResearchLockLease:
        try:
            self._entry.lock.acquire()
        except BaseException:
            self._registry.release(self._key, self._entry)
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._entry.lock.release()
        self._registry.release(self._key, self._entry)


class _ResearchLockRegistry:
    """Coalesce keyed research requests without retaining idle locks."""

    def __init__(self) -> None:
        self._entries: dict[str, _ResearchLockEntry] = {}
        self._guard = threading.Lock()

    def acquire(self, key: str) -> _ResearchLockLease:
        with self._guard:
            entry = self._entries.get(key)
            if entry is None:
                entry = _ResearchLockEntry(threading.Lock())
                self._entries[key] = entry
            entry.users += 1
        return _ResearchLockLease(self, key, entry)

    def release(self, key: str, entry: _ResearchLockEntry) -> None:
        with self._guard:
            entry.users -= 1
            if entry.users == 0 and self._entries.get(key) is entry:
                del self._entries[key]

    def clear(self) -> None:
        with self._guard:
            self._entries.clear()

    def __len__(self) -> int:
        with self._guard:
            return len(self._entries)


def _db_path_from_env() -> Path:
    return Path(os.environ.get("CV_VALIDATOR_DB_PATH", DEFAULT_DB))


def _retention_days_from_env() -> int:
    return int(os.environ.get("CV_VALIDATOR_RETENTION_DAYS", "90"))


def _positive_int_env(name: str, default: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _report_language(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"en", "pl"}:
        raise HTTPException(status_code=400, detail="unsupported_report_language")
    return normalized


def create_app(
    db_path: Path | None = None,
    retention_days: int | None = None,
    location_resolver: LocationResolver | None = None,
    ai_settings: AISettings | None = None,
    document_analyzer: DocumentAnalyzer | None = None,
    batch_max_files: int | None = None,
    batch_max_bytes: int | None = None,
    company_researcher=None,
    education_researcher=None,
    linkedin_researcher=None,
    linkedin_connection_threshold: int | None = None,
    linkedin_max_profiles: int | None = None,
    research_cache_ttl_days: int | None = None,
    require_location_resolver: bool = False,
    link_check_config: LinkCheckConfig | None = None,
    link_inspector: LinkInspector | None = None,
    link_dns_resolver: DNSResolver | None = None,
    link_http_client: LinkHTTPClient | None = None,
) -> FastAPI:
    ingestion_config = load_ingestion_config()
    selected_link_check_config = link_check_config or load_link_check_config()
    selected_ai_settings = ai_settings or load_ai_settings()
    selected_document_analyzer = document_analyzer
    if selected_ai_settings.enabled and selected_document_analyzer is None:
        selected_document_analyzer = OpenAIResponsesDocumentAnalyzer(
            selected_ai_settings
        )
    selected_company_researcher = company_researcher
    if selected_ai_settings.enabled and selected_company_researcher is None:
        selected_company_researcher = OpenAIResponsesCompanyResearcher(
            api_key=selected_ai_settings.api_key,
            timeout_seconds=selected_ai_settings.timeout_seconds,
        )
    selected_education_researcher = education_researcher
    if selected_ai_settings.enabled and selected_education_researcher is None:
        selected_education_researcher = OpenAIResponsesEducationResearcher(
            api_key=selected_ai_settings.api_key,
            timeout_seconds=selected_ai_settings.timeout_seconds,
        )
    selected_linkedin_researcher = linkedin_researcher
    selected_linkedin_threshold = linkedin_connection_threshold if linkedin_connection_threshold is not None else _positive_int_env("CV_VALIDATOR_LINKEDIN_CONNECTION_THRESHOLD", 500)
    selected_linkedin_max_profiles = linkedin_max_profiles if linkedin_max_profiles is not None else _positive_int_env("CV_VALIDATOR_LINKEDIN_MAX_PROFILES", DEFAULT_MAX_PROFILES)
    if selected_linkedin_max_profiles > MAX_PROFILES_LIMIT:
        raise ValueError("CV_VALIDATOR_LINKEDIN_MAX_PROFILES must be at most 20")
    if selected_ai_settings.enabled and selected_linkedin_researcher is None:
        selected_linkedin_researcher = OpenAIResponsesLinkedInResearcher(
            api_key=selected_ai_settings.api_key,
            timeout_seconds=selected_ai_settings.timeout_seconds,
            connection_threshold=selected_linkedin_threshold,
            max_profiles=selected_linkedin_max_profiles,
        )
    resolver = location_resolver or load_location_resolver(
        required=require_location_resolver,
    )
    store = PersistenceStore(
        PersistenceConfig(
            db_path=db_path or _db_path_from_env(),
            retention_days=retention_days if retention_days is not None else _retention_days_from_env(),
            research_cache_ttl_days=research_cache_ttl_days if research_cache_ttl_days is not None else _positive_int_env("CV_VALIDATOR_RESEARCH_CACHE_TTL_DAYS", 30),
        )
    )
    feedback_enabled = os.environ.get("CV_VALIDATOR_FEEDBACK_ENABLED", "false").lower() in {"1", "true", "yes"}
    feedback_inbox_enabled = os.environ.get("CV_VALIDATOR_FEEDBACK_INBOX_ENABLED", "false").lower() in {"1", "true", "yes"}
    feedback_failures_enabled = os.environ.get("CV_VALIDATOR_FEEDBACK_FAILURES_ENABLED", "false").lower() in {"1", "true", "yes"}
    feedback_secret = os.environ.get("CV_VALIDATOR_FEEDBACK_HMAC_SECRET") or os.environ.get("BETTER_AUTH_SECRET") or "local-feedback-secret-change-me"
    feedback_internal_token = os.environ.get("CV_VALIDATOR_FEEDBACK_INTERNAL_TOKEN", "")
    if feedback_enabled and feedback_secret == "local-feedback-secret-change-me":
        raise ValueError("CV_VALIDATOR_FEEDBACK_HMAC_SECRET is required when feedback is enabled")
    if feedback_inbox_enabled and not feedback_internal_token:
        raise ValueError("CV_VALIDATOR_FEEDBACK_INTERNAL_TOKEN is required when feedback inbox is enabled")
    feedback_store = FeedbackStore(store.config.db_path, feedback_secret)
    selected_batch_max_files = (
        batch_max_files
        if batch_max_files is not None
        else _positive_int_env("CV_VALIDATOR_BATCH_MAX_FILES", DEFAULT_BATCH_MAX_FILES)
    )
    selected_batch_max_bytes = (
        batch_max_bytes
        if batch_max_bytes is not None
        else _positive_int_env("CV_VALIDATOR_BATCH_MAX_BYTES", DEFAULT_BATCH_MAX_BYTES)
    )
    if selected_batch_max_files < 1 or selected_batch_max_bytes < 1:
        raise ValueError("batch limits must be positive integers")
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            retry_contexts.clear()
            retry_locks.clear()
            retry_flights.clear()
            retry_invalidated.clear()
            research_locks.clear()
            if isinstance(resolver, SQLiteLocationResolver):
                resolver.close()

    app = FastAPI(
        title="CV Location Consistency Analyzer",
        version="0.1.0",
        lifespan=lifespan,
    )
    telemetry = OperationsTelemetry()
    retry_contexts: dict[str, PipelineResult] = {}
    retry_contexts_guard = threading.Lock()
    retry_locks: dict[str, threading.Lock] = {}
    retry_flights: dict[str, _RetryFlight] = {}
    retry_invalidated: set[str] = set()

    def remove_retry_state(analysis_ids: tuple[str, ...]) -> None:
        with retry_contexts_guard:
            for analysis_id in analysis_ids:
                if isinstance(retry_flights.get(analysis_id), _RetryFlight):
                    retry_invalidated.add(analysis_id)
                retry_contexts.pop(analysis_id, None)
                retry_locks.pop(analysis_id, None)
                retry_flights.pop(analysis_id, None)

    store.set_purge_listener(remove_retry_state)

    def attach_ai_capabilities(payload: dict, *, requested: bool) -> dict:
        payload["ai_features_enabled"] = bool(
            requested
            and selected_ai_settings.enabled
            and selected_document_analyzer is not None
        )
        payload["ai_capabilities"] = {
            "document_analysis": selected_document_analyzer is not None,
            "company_research": selected_company_researcher is not None,
            "education_research": selected_education_researcher is not None,
            "linkedin_research": selected_linkedin_researcher is not None,
        }
        return payload

    def require_analysis_ai_enabled(payload: dict, requested: bool) -> None:
        if not requested or payload.get("ai_features_enabled") is False:
            raise HTTPException(status_code=409, detail="ai_disabled_for_analysis")

    @app.middleware("http")
    async def observe_request(request, call_next):
        supplied_correlation_id = request.headers.get("X-Correlation-ID")
        try:
            correlation_id = str(UUID(supplied_correlation_id)) if supplied_correlation_id else str(uuid4())
        except (ValueError, AttributeError):
            correlation_id = str(uuid4())
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (perf_counter() - started) * 1000
            route = getattr(request.scope.get("route"), "path", "unmatched")
            telemetry.request(route, 500, duration_ms)
            safe_log("request_completed", correlation_id=correlation_id, status_code=500, duration_ms=round(duration_ms, 2), error_code="unhandled")
            raise
        duration_ms = (perf_counter() - started) * 1000
        route = getattr(request.scope.get("route"), "path", "unmatched")
        telemetry.request(route, response.status_code, duration_ms)
        safe_log("request_completed", correlation_id=correlation_id, status_code=response.status_code, duration_ms=round(duration_ms, 2))
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    @app.get("/health")
    def health() -> dict:
        location_ready = resolver is not None
        capabilities = {
            "database": {"ready": True},
            "geonames": {
                "ready": location_ready,
                "version": (
                    resolver.reference_data_version.version
                    if isinstance(resolver, SQLiteLocationResolver)
                    else None
                ),
                "recovery": None if location_ready else "Configure the approved GeoNames index and manifest.",
            },
            "document_ai": {"ready": selected_document_analyzer is not None},
            "company_research": {"ready": selected_company_researcher is not None},
            "education_research": {"ready": selected_education_researcher is not None},
            "linkedin_research": {"ready": selected_linkedin_researcher is not None},
            "link_checks": {
                "ready": selected_link_check_config.enabled,
                "enabled": selected_link_check_config.enabled,
                "version": selected_link_check_config.configuration_version,
            },
            "feedback": {"ready": True, "enabled": feedback_enabled, "failure_targets_enabled": feedback_failures_enabled},
            "feedback_inbox": {"ready": not feedback_inbox_enabled or bool(feedback_internal_token), "enabled": feedback_inbox_enabled},
        }
        ready = all(item["ready"] for item in capabilities.values())
        return {
            "status": "ready" if ready else "degraded",
            "ready": ready,
            "capabilities": capabilities,
        }

    @app.get("/operations/metrics")
    def operations_metrics() -> dict:
        return telemetry.snapshot()

    @app.get("/operations/status")
    def operations_status() -> dict:
        return {
            "ai_enabled": selected_ai_settings.enabled,
            "retention": {
                "days": store.config.retention_days,
                "configurable": True,
                "scope": "candidate_analysis_data",
            },
            "research_cache": {"ttl_days": store.config.research_cache_ttl_days},
            "batch": {"max_files": selected_batch_max_files, "max_bytes": selected_batch_max_bytes},
            "link_checks": {
                "enabled": selected_link_check_config.enabled,
                "protocols": selected_link_check_config.allowed_protocols,
                "ports": selected_link_check_config.allowed_ports,
                "timeout_seconds": selected_link_check_config.timeout_seconds,
                "max_response_bytes": selected_link_check_config.max_response_bytes,
                "max_redirects": selected_link_check_config.max_redirects,
                "max_concurrency": selected_link_check_config.max_concurrency,
                "max_retries": selected_link_check_config.max_retries,
                "total_budget_seconds": selected_link_check_config.total_budget_seconds,
                "configuration_version": selected_link_check_config.configuration_version,
            },
            "document_ai": {
                "timeout_seconds": selected_ai_settings.timeout_seconds,
                "max_output_tokens": selected_ai_settings.max_output_tokens,
                "transport_retry_limit": selected_ai_settings.transport_retry_limit,
                "invalid_response_retry_limit": selected_ai_settings.invalid_response_retry_limit,
                "absolute_attempt_limit": selected_ai_settings.absolute_attempt_limit,
            },
        }

    @app.post("/analyze")
    async def analyze_single(
        file: UploadFile = File(...),
        x_analysis_access_token: str | None = Header(default=None),
        x_report_language: str = Header(default="en"),
        x_ai_enabled: bool = Header(default=True),
    ) -> JSONResponse:
        filename = file.filename or "upload.pdf"
        try:
            content = await _read_upload(file)
            request_ai_settings = selected_ai_settings if x_ai_enabled else replace(selected_ai_settings, enabled=False)
            result = analyze_cv_bytes_result(
                content,
                filename=filename,
                ingestion_config=ingestion_config,
                location_resolver=resolver,
                ai_settings=request_ai_settings,
                document_analyzer=selected_document_analyzer,
                report_language=_report_language(x_report_language),
                defer_ai=request_ai_settings.enabled,
                link_check_config=selected_link_check_config,
                link_inspector=link_inspector,
                link_dns_resolver=link_dns_resolver,
                link_http_client=link_http_client,
                link_metrics=telemetry,
            )
            analysis_id = str(uuid4())
            access_token = x_analysis_access_token or secrets.token_urlsafe(32)
            payload = serialize_analysis_payload(
                result,
                request_ai_settings,
                analysis_id=analysis_id,
            )
            attach_ai_capabilities(payload, requested=x_ai_enabled)
            store.persist_report(
                result.document_identity,
                result.report,
                report_payload=payload,
                analysis_id=analysis_id,
                ai_analysis=payload["ai_analysis"],
                access_token=access_token,
                source_filename=filename,
            )
            if feedback_enabled:
                feedback_store.materialize(analysis_id, payload, include_failures=feedback_failures_enabled)
            if result.redacted_document is not None and result.ai_outcome.status in {
                AIAnalysisStatus.PENDING,
                AIAnalysisStatus.FAILED,
            }:
                with retry_contexts_guard:
                    retry_contexts[analysis_id] = result
        except IngestionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except AnalysisRuntimeError as exc:
            raise HTTPException(
                status_code=500,
                detail="analysis_runtime_error",
            ) from exc

        return JSONResponse(payload)

    @app.post("/analyze/batch")
    async def analyze_batch(
        files: list[UploadFile] = File(...),
        x_analysis_access_token: str | None = Header(default=None),
        x_report_language: str = Header(default="en"),
        x_ai_enabled: bool = Header(default=True),
    ) -> JSONResponse:
        prepared = await _prepare_batch(
            files,
            max_files=selected_batch_max_files,
            max_bytes=selected_batch_max_bytes,
        )
        results: list[dict] = []
        for item in prepared:
            upload = item.upload
            filename = upload.filename or "upload.pdf"
            if item.error is not None:
                results.append(
                    {
                        "filename": filename,
                        "status": "error",
                        "error": item.error,
                    }
                )
                continue
            try:
                assert item.content is not None
                request_ai_settings = selected_ai_settings if x_ai_enabled else replace(selected_ai_settings, enabled=False)
                result = analyze_cv_bytes_result(
                    item.content,
                    filename=filename,
                    ingestion_config=ingestion_config,
                    location_resolver=resolver,
                    ai_settings=request_ai_settings,
                    document_analyzer=selected_document_analyzer,
                    report_language=_report_language(x_report_language),
                    defer_ai=request_ai_settings.enabled,
                    link_check_config=selected_link_check_config,
                    link_inspector=link_inspector,
                    link_dns_resolver=link_dns_resolver,
                    link_http_client=link_http_client,
                    link_metrics=telemetry,
                )
                analysis_id = str(uuid4())
                access_token = x_analysis_access_token or secrets.token_urlsafe(32)
                payload = serialize_analysis_payload(
                    result,
                    request_ai_settings,
                    analysis_id=analysis_id,
                )
                attach_ai_capabilities(payload, requested=x_ai_enabled)
                store.persist_report(
                    result.document_identity,
                    result.report,
                    report_payload=payload,
                    analysis_id=analysis_id,
                    ai_analysis=payload["ai_analysis"],
                    access_token=access_token,
                    source_filename=filename,
                )
                if feedback_enabled:
                    feedback_store.materialize(analysis_id, payload, include_failures=feedback_failures_enabled)
                if result.redacted_document is not None and result.ai_outcome.status in {
                    AIAnalysisStatus.PENDING,
                    AIAnalysisStatus.FAILED,
                }:
                    with retry_contexts_guard:
                        retry_contexts[analysis_id] = result
                results.append(
                    {
                        "filename": filename,
                        "status": "ok",
                        "report": payload,
                    }
                )
            except IngestionError as exc:
                results.append({"filename": filename, "status": "error", "error": str(exc)})
            except AnalysisRuntimeError:
                results.append(
                    {
                        "filename": filename,
                        "status": "error",
                        "error": "analysis_runtime_error",
                    }
                )
        return JSONResponse({"results": results})

    @app.get("/analyses")
    def list_analyses(
        x_analysis_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        store.purge_expired()
        return JSONResponse({"analyses": store.list_analyses(x_analysis_access_token)})

    @app.delete("/analyses")
    def delete_all_analyses(
        x_analysis_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        owned_ids = {
            item["analysis_id"]
            for item in store.list_analyses(x_analysis_access_token)
        }
        deleted = store.delete_all_analyses(x_analysis_access_token)
        remove_retry_state(tuple(sorted(owned_ids)))
        return JSONResponse({"deleted": deleted})

    @app.get("/analyses/{analysis_id}")
    def get_analysis(
        analysis_id: str,
        x_analysis_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        payload = _owned_payload(store, analysis_id, x_analysis_access_token)
        with retry_contexts_guard:
            payload["ai_analysis"]["manual_retry_available"] = (
                analysis_id in retry_contexts
                and selected_ai_settings.enabled
                and selected_document_analyzer is not None
            )
        return JSONResponse(payload)

    @app.get("/analyses/{analysis_id}/feedback")
    def get_feedback_manifest(
        analysis_id: str,
        x_analysis_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        if not feedback_enabled:
            raise HTTPException(status_code=404, detail="feedback_not_found")
        payload = _owned_payload(store, analysis_id, x_analysis_access_token)
        feedback_store.materialize(analysis_id, payload, include_failures=feedback_failures_enabled)
        return JSONResponse(feedback_store.manifest(analysis_id, x_analysis_access_token))

    @app.put("/analyses/{analysis_id}/feedback/{target_id}")
    def put_feedback(
        analysis_id: str,
        target_id: str,
        update: FeedbackInput,
        x_analysis_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        started = perf_counter()
        if not feedback_enabled:
            raise HTTPException(status_code=404, detail="feedback_not_found")
        _owned_payload(store, analysis_id, x_analysis_access_token)
        try:
            result = feedback_store.put(analysis_id, target_id, x_analysis_access_token or "", update)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(status_code=404, detail="feedback_not_found")
        safe_log("feedback_operation", operation="put", outcome="ok", target_kind=result["target_kind"], classification=update.reason or update.rating or "comment_only", duration_ms=round((perf_counter()-started)*1000, 2))
        return JSONResponse(result)

    @app.delete("/analyses/{analysis_id}/feedback/{target_id}")
    def withdraw_feedback(
        analysis_id: str,
        target_id: str,
        x_analysis_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        if not feedback_enabled:
            raise HTTPException(status_code=404, detail="feedback_not_found")
        _owned_payload(store, analysis_id, x_analysis_access_token)
        result = feedback_store.withdraw(analysis_id, target_id, x_analysis_access_token or "")
        if result is None:
            raise HTTPException(status_code=404, detail="feedback_not_found")
        return JSONResponse({"withdrawn": result})

    def require_internal(token: str | None) -> None:
        if not feedback_inbox_enabled or not feedback_internal_token or not token or not hmac.compare_digest(token, feedback_internal_token):
            raise HTTPException(status_code=404, detail="feedback_not_found")

    @app.get("/internal/feedback")
    def feedback_inbox(
        x_feedback_internal_token: str | None = Header(default=None),
        limit: int = Query(default=50, ge=1, le=100), cursor: int = Query(default=0, ge=0),
        rating: str | None = None, reason: str | None = None, kind: str | None = None, status: str | None = None,
        source: str | None = None, version: str | None = None, operation: str | None = None,
        error_code: str | None = None, date_from: str | None = None, date_to: str | None = None,
    ) -> JSONResponse:
        require_internal(x_feedback_internal_token)
        return JSONResponse(feedback_store.inbox(limit=limit, cursor=cursor, filters={"rating": rating, "reason": reason, "kind": kind, "status": status, "source":source,"version":version,"operation":operation,"error_code":error_code,"date_from":date_from,"date_to":date_to}))

    @app.put("/internal/feedback/{target_id}/{actor_hash}/triage")
    def update_feedback_triage(
        target_id: str, actor_hash: str, update: TriageInput,
        x_feedback_internal_token: str | None = Header(default=None),
        x_feedback_maintainer: str | None = Header(default=None),
    ) -> JSONResponse:
        require_internal(x_feedback_internal_token)
        if not x_feedback_maintainer:
            raise HTTPException(status_code=400, detail="maintainer_required")
        if not feedback_store.triage(target_id, actor_hash, x_feedback_maintainer, update):
            raise HTTPException(status_code=404, detail="feedback_not_found")
        return JSONResponse({"updated": True})

    @app.post("/analyses/{analysis_id}/ai/retry")
    def retry_ai_analysis(
        analysis_id: str,
        x_analysis_access_token: str | None = Header(default=None),
        x_ai_enabled: bool = Header(default=True),
    ) -> JSONResponse:
        stored_payload = _owned_payload(store, analysis_id, x_analysis_access_token)
        require_analysis_ai_enabled(stored_payload, x_ai_enabled)
        if not selected_ai_settings.enabled or selected_document_analyzer is None:
            raise HTTPException(status_code=409, detail="ai_unavailable")
        with retry_contexts_guard:
            flight = retry_flights.get(analysis_id)
            if flight is None:
                context = retry_contexts.get(analysis_id)
                if context is None or context.redacted_document is None:
                    raise HTTPException(status_code=409, detail="ai_retry_context_unavailable")
                flight = _RetryFlight(Future())
                retry_flights[analysis_id] = flight
                leader = True
            else:
                flight.waiters += 1
                leader = False
        if leader:
            try:
                with retry_contexts_guard:
                    context = retry_contexts.get(analysis_id)
                if context is None or context.redacted_document is None:
                    raise HTTPException(status_code=409, detail="ai_retry_context_unavailable")
                from cv_validator.document_understanding.visibility import build_visibility_exclusion_index
                exclusion = build_visibility_exclusion_index(context.redacted_document)
                outcome = run_document_analysis(
                    selected_ai_settings,
                    selected_document_analyzer,
                    context.redacted_document,
                    context.deterministic,
                    report_language=context.report_language,
                    exclusion_intervals=exclusion.intervals,
                    understanding_context=context.report.document_understanding,
                )
                with retry_contexts_guard:
                    if analysis_id in retry_invalidated:
                        raise HTTPException(
                            status_code=409,
                            detail="ai_retry_context_unavailable",
                        )
                updated_result = replace(context, ai_outcome=outcome)
                payload = serialize_analysis_payload(
                    updated_result,
                    selected_ai_settings,
                    analysis_id=analysis_id,
                )
                attach_ai_capabilities(payload, requested=True)
                for key in (
                    "company_research",
                    "education_research",
                    "linkedin_discovery",
                ):
                    if key in stored_payload:
                        payload[key] = stored_payload[key]
                try:
                    store.replace_ai_analysis(analysis_id, payload)
                except PersistenceError:
                    with retry_contexts_guard:
                        invalidated = analysis_id in retry_invalidated
                    if invalidated or not store.analysis_access_allowed(
                        analysis_id, x_analysis_access_token
                    ):
                        raise HTTPException(
                            status_code=409,
                            detail="ai_retry_context_unavailable",
                        ) from None
                    raise
                with retry_contexts_guard:
                    if analysis_id in retry_invalidated:
                        raise HTTPException(
                            status_code=409,
                            detail="ai_retry_context_unavailable",
                        )
                    if outcome.status is AIAnalysisStatus.FAILED:
                        retry_contexts[analysis_id] = updated_result
                    else:
                        retry_contexts.pop(analysis_id, None)
                        retry_locks.pop(analysis_id, None)
                    flight.future.set_result(payload)
            except BaseException as exc:
                flight.future.set_exception(exc)
        try:
            payload = flight.future.result()
            return JSONResponse(deepcopy(payload))
        finally:
            with retry_contexts_guard:
                flight.waiters -= 1
                if flight.waiters == 0 and retry_flights.get(analysis_id) is flight:
                    retry_flights.pop(analysis_id, None)
                if flight.waiters == 0:
                    retry_invalidated.discard(analysis_id)

    @app.delete("/analyses/{analysis_id}")
    def delete_analysis(
        analysis_id: str,
        x_analysis_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        if not store.delete_analysis(analysis_id, x_analysis_access_token):
            raise HTTPException(status_code=404, detail="analysis_not_found")
        remove_retry_state((analysis_id,))
        return JSONResponse({"deleted": True})

    @app.get("/settings/retention")
    def get_retention() -> JSONResponse:
        return JSONResponse({"days": store.config.retention_days})

    @app.put("/settings/retention")
    def update_retention(update: _RetentionUpdate) -> JSONResponse:
        try:
            store.set_retention_days(update.days)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail="retention_days_out_of_range",
            ) from exc
        return JSONResponse({"days": store.config.retention_days})

    research_locks = _ResearchLockRegistry()

    @app.post("/analyses/{analysis_id}/research/company")
    def research_company(analysis_id: str, x_analysis_access_token: str | None = Header(default=None), x_ai_enabled: bool = Header(default=True)) -> JSONResponse:
        if selected_company_researcher is None:
            raise HTTPException(status_code=503, detail="company_research_disabled")
        if not store.analysis_access_allowed(analysis_id, x_analysis_access_token):
            raise HTTPException(status_code=404, detail="analysis_not_found")
        stored_payload = store.get_analysis_payload(analysis_id)
        if stored_payload is None:
            raise HTTPException(status_code=404, detail="analysis_not_found")
        require_analysis_ai_enabled(stored_payload, x_ai_enabled)
        try:
            request = build_company_research_request(stored_payload)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        descriptor = company_cache_descriptor(request)
        with research_locks.acquire(f"cache:{descriptor.cache_key}"):
            completed = store.get_company_research(analysis_id)
            if completed is not None:
                result = json.loads(completed["result_json"])
            else:
                cached = store.get_reusable_research(descriptor)
                if cached is not None:
                    result = materialize_cache_hit("company", cached, descriptor=descriptor)
                    try:
                        store.record_cache_use(analysis_id, "company", descriptor.cache_key, "hit")
                        store.persist_company_research(analysis_id, result)
                    except PersistenceError as exc:
                        _raise_research_persistence_error(exc)
                    telemetry.increment("research_cache_total", category="company", outcome="hit")
                else:
                    try:
                        result = CompanyResearchService(selected_company_researcher).run(stored_payload)
                        result["cache"] = {"status": "miss", "format_version": descriptor.cache_format_version}
                        store.persist_reusable_research(descriptor, reusable_payload("company", result))
                        store.record_cache_use(analysis_id, "company", descriptor.cache_key, "miss")
                        store.persist_company_research(analysis_id, result)
                        telemetry.increment("research_cache_total", category="company", outcome="miss")
                    except ValueError as exc:
                        raise HTTPException(status_code=409, detail=str(exc)) from exc
                    except CompanyResearchTimeout as exc:
                        telemetry.increment("research_failures_total", category="company", outcome="timeout")
                        safe_log("research_failed", analysis_id=analysis_id, category="company", error_code="timeout")
                        raise HTTPException(status_code=504, detail="company_research_timeout") from exc
                    except CompanyResearchInvalidResponse as exc:
                        telemetry.increment("research_failures_total", category="company", outcome="invalid_response")
                        safe_log("research_failed", analysis_id=analysis_id, category="company", error_code="invalid_response")
                        raise HTTPException(status_code=502, detail="company_research_invalid_response") from exc
                    except CompanyResearchClientError as exc:
                        telemetry.increment("research_failures_total", category="company", outcome="client_error")
                        safe_log("research_failed", analysis_id=analysis_id, category="company", error_code="client_error")
                        raise HTTPException(status_code=502, detail="company_research_client_error") from exc
                    except PersistenceError as exc:
                        _raise_research_persistence_error(exc)
        response = deepcopy(stored_payload)
        response["company_research"] = result
        return JSONResponse(response)

    @app.post("/analyses/{analysis_id}/research/education")
    def research_education(analysis_id: str, x_analysis_access_token: str | None = Header(default=None), x_ai_enabled: bool = Header(default=True)) -> JSONResponse:
        if selected_education_researcher is None:
            raise HTTPException(status_code=503, detail="education_research_disabled")
        if not store.analysis_access_allowed(analysis_id, x_analysis_access_token):
            raise HTTPException(status_code=404, detail="analysis_not_found")
        stored_payload = store.get_analysis_payload(analysis_id)
        if stored_payload is None:
            raise HTTPException(status_code=404, detail="analysis_not_found")
        require_analysis_ai_enabled(stored_payload, x_ai_enabled)
        try:
            request = build_education_research_request(stored_payload)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        descriptor = education_cache_descriptor(request)
        with research_locks.acquire(f"cache:{descriptor.cache_key}"):
            completed = store.get_education_research(analysis_id)
            if completed is not None:
                result = json.loads(completed["result_json"])
            else:
                cached = store.get_reusable_research(descriptor)
                if cached is not None:
                    public_result = materialize_cache_hit("education", cached, descriptor=descriptor)
                    public_result = normalize_public_education_result(public_result)
                    try:
                        store.record_cache_use(analysis_id, "education", descriptor.cache_key, "hit")
                    except PersistenceError as exc:
                        _raise_research_persistence_error(exc)
                    telemetry.increment("research_cache_total", category="education", outcome="hit")
                else:
                    try:
                        public_result = EducationResearchService(selected_education_researcher).run(stored_payload)
                        public_result["cache"] = {"status": "miss", "format_version": descriptor.cache_format_version}
                        store.persist_reusable_research(descriptor, reusable_payload("education", public_result))
                        store.record_cache_use(analysis_id, "education", descriptor.cache_key, "miss")
                        telemetry.increment("research_cache_total", category="education", outcome="miss")
                    except ValueError as exc:
                        raise HTTPException(status_code=409, detail=str(exc)) from exc
                    except EducationResearchTimeout as exc:
                        telemetry.increment("research_failures_total", category="education", outcome="timeout")
                        safe_log("research_failed", analysis_id=analysis_id, category="education", error_code="timeout")
                        raise HTTPException(status_code=504, detail="education_research_timeout") from exc
                    except EducationResearchInvalidResponse as exc:
                        telemetry.increment("research_failures_total", category="education", outcome="invalid_response")
                        safe_log("research_failed", analysis_id=analysis_id, category="education", error_code="invalid_response")
                        raise HTTPException(status_code=502, detail="education_research_invalid_response") from exc
                    except EducationResearchClientError as exc:
                        telemetry.increment("research_failures_total", category="education", outcome="client_error")
                        safe_log("research_failed", analysis_id=analysis_id, category="education", error_code="client_error")
                        raise HTTPException(status_code=502, detail="education_research_client_error") from exc
                    except PersistenceError as exc:
                        _raise_research_persistence_error(exc)
                result = apply_owner_scoped_education_context(
                    public_result,
                    stored_payload,
                    location_resolver=resolver,
                )
                try:
                    store.persist_education_research(analysis_id, result)
                except PersistenceError as exc:
                    _raise_research_persistence_error(exc)
        response = deepcopy(stored_payload)
        response["education_research"] = result
        return JSONResponse(response)

    @app.post("/analyses/{analysis_id}/research/linkedin/discovery")
    def discover_linkedin(analysis_id: str, x_analysis_access_token: str | None = Header(default=None), x_ai_enabled: bool = Header(default=True)) -> JSONResponse:
        stored_payload = _owned_payload(store, analysis_id, x_analysis_access_token)
        require_analysis_ai_enabled(stored_payload, x_ai_enabled)
        if selected_linkedin_researcher is None: raise HTTPException(status_code=503, detail="linkedin_research_disabled")
        with research_locks.acquire(f"linkedin:{analysis_id}"):
            completed = store.get_linkedin_discovery(analysis_id)
            if completed is not None: result = json.loads(completed["result_json"])
            else:
                try:
                    result = LinkedInDiscoveryService(
                        selected_linkedin_researcher,
                        selected_linkedin_threshold,
                        selected_linkedin_max_profiles,
                    ).run(stored_payload)
                    store.persist_linkedin_discovery(analysis_id, result)
                except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
                except LinkedInResearchTimeout as exc:
                    _record_research_failure(telemetry, analysis_id, "linkedin_discovery", "timeout")
                    raise HTTPException(status_code=504, detail="linkedin_discovery_timeout") from exc
                except LinkedInResearchInvalidResponse as exc:
                    _record_research_failure(
                        telemetry,
                        analysis_id,
                        "linkedin_discovery",
                        f"invalid_response:{str(exc) or 'unknown'}",
                    )
                    raise HTTPException(status_code=502, detail="linkedin_discovery_invalid_response") from exc
                except LinkedInResearchClientError as exc:
                    _record_research_failure(telemetry, analysis_id, "linkedin_discovery", "client_error")
                    raise HTTPException(status_code=502, detail="linkedin_discovery_client_error") from exc
                except PersistenceError as exc:
                    _raise_research_persistence_error(exc)
        response = deepcopy(stored_payload); response["linkedin_discovery"] = result
        return JSONResponse(response)

    app.state.store = store
    app.state.location_resolver = resolver
    app.state.ai_settings = selected_ai_settings
    app.state.document_analyzer = selected_document_analyzer
    app.state.batch_max_files = selected_batch_max_files
    app.state.batch_max_bytes = selected_batch_max_bytes
    app.state.link_check_config = selected_link_check_config
    app.state.company_researcher = selected_company_researcher
    app.state.education_researcher = selected_education_researcher
    app.state.linkedin_researcher = selected_linkedin_researcher
    app.state.linkedin_connection_threshold = selected_linkedin_threshold
    app.state.linkedin_max_profiles = selected_linkedin_max_profiles
    app.state.research_cache_ttl_days = store.config.research_cache_ttl_days
    app.state.research_locks = research_locks
    app.state.telemetry = telemetry
    app.state.ai_retry_contexts = retry_contexts
    app.state.ai_retry_locks = retry_locks
    app.state.ai_retry_flights = retry_flights
    app.state.ai_retry_invalidated = retry_invalidated
    return app


def _record_research_failure(telemetry: OperationsTelemetry, analysis_id: str, category: str, outcome: str) -> None:
    telemetry.increment("research_failures_total", category=category, outcome=outcome)
    safe_log("research_failed", analysis_id=analysis_id, category=category, error_code=outcome)


def _raise_research_persistence_error(exc: PersistenceError) -> None:
    if isinstance(exc, AnalysisNotFoundPersistenceError):
        raise HTTPException(status_code=404, detail="analysis_not_found") from None
    raise HTTPException(status_code=409, detail="research_persistence_conflict") from None


async def _read_upload(upload: UploadFile) -> bytes:
    try:
        return await upload.read()
    except OSError as exc:
        raise UploadReadError("upload read failed") from exc


async def _prepare_batch(
    files: list[UploadFile],
    *,
    max_files: int,
    max_bytes: int,
) -> list[_PreparedUpload]:
    if len(files) > max_files:
        raise HTTPException(status_code=413, detail="batch_file_limit_exceeded")

    prepared: list[_PreparedUpload] = []
    total_bytes = 0
    for upload in files:
        try:
            content = await _read_upload(upload)
        except AnalysisRuntimeError:
            prepared.append(
                _PreparedUpload(
                    upload=upload,
                    content=None,
                    error="analysis_runtime_error",
                )
            )
            continue
        total_bytes += len(content)
        if total_bytes > max_bytes:
            raise HTTPException(
                status_code=413,
                detail="batch_request_size_limit_exceeded",
            )
        prepared.append(_PreparedUpload(upload=upload, content=content))
    return prepared


def _default_app() -> FastAPI:
    require_location_resolver = os.environ.get(
        "CV_VALIDATOR_REQUIRE_LOCATION_RESOLVER", "false"
    ).lower() in {"1", "true", "yes"}
    return create_app(require_location_resolver=require_location_resolver)


app = _default_app()


def _owned_payload(store: PersistenceStore, analysis_id: str, access_token: str | None) -> dict:
    if not store.analysis_access_allowed(analysis_id, access_token): raise HTTPException(status_code=404, detail="analysis_not_found")
    payload = store.get_analysis_payload(analysis_id)
    if payload is None: raise HTTPException(status_code=404, detail="analysis_not_found")
    completed_rows = (
        ("company_research", store.get_company_research(analysis_id)),
        ("education_research", store.get_education_research(analysis_id)),
        ("linkedin_discovery", store.get_linkedin_discovery(analysis_id)),
    )
    for key, row in completed_rows:
        if row is not None:
            payload[key] = json.loads(row["result_json"])
    return payload
