from __future__ import annotations

from typing import Any

import json
import hmac
import os
import secrets
import threading
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel

from cv_validator.analysis import (
    AnalysisStrategy,
    AnalysisStrategyError,
    AnalysisStrategyUnavailable,
)
from cv_validator.analysis.document_analysis import DocumentAnalysisStrategy
from cv_validator.analysis.model_client import OpenAIResponsesAnalysisClient
from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.api.feedback import FeedbackInput, FeedbackStore, TriageInput
from cv_validator.config import load_location_resolver, load_postal_code_resolver
from cv_validator.errors import (
    AnalysisNotFoundPersistenceError,
    PersistenceError,
    UploadReadError,
)
from cv_validator.location import (
    LocationResolver,
    PostalCodeResolver,
    SQLiteLocationResolver,
    SQLitePostalCodeResolver,
)
from cv_validator.openai_config import PINNED_OPENAI_MODEL, OpenAISettings, load_openai_settings
from cv_validator.operations import (
    AnalysisRecorder,
    OperationsTelemetry,
    configure_structured_logging,
    safe_log,
    utc_now,
)
from cv_validator.pipeline import analyze_cv_bytes_result
from cv_validator.research.cache import (
    company_subject_descriptors,
    education_subject_descriptors,
    merge_subject_results,
    materialize_cache_hit,
    reusable_payload,
    single_subject_result,
)
from cv_validator.research.company import (
    CompanyResearchService,
    build_company_research_request,
)
from cv_validator.research.domain import (
    CompanyResearchClientError,
    CompanyResearchInvalidResponse,
    CompanyResearchTimeout,
    CompanyResearchRequest,
    EducationResearchClientError,
    EducationResearchInvalidResponse,
    EducationResearchTimeout,
    EducationResearchRequest,
    LinkedInResearchClientError,
    LinkedInResearchInvalidResponse,
    LinkedInResearchTimeout,
)
from cv_validator.research.education import (
    EducationResearchService,
    apply_owner_scoped_education_context,
    build_education_research_request,
    normalize_public_education_result,
)
from cv_validator.research.linkedin import (
    DEFAULT_MAX_PROFILES,
    MAX_PROFILES_LIMIT,
    LinkedInDiscoveryService,
)
from cv_validator.research.openai_client import (
    OpenAIResponsesCompanyResearcher,
    OpenAIResponsesEducationResearcher,
    OpenAIResponsesLinkedInResearcher,
)
from cv_validator.serialization import serialize_analysis_payload
from cv_validator.usage import load_pricing_catalog

DEFAULT_DB = Path("data/cv_analyzer.db")
DEFAULT_UPLOAD_MAX_BYTES = 20 * 1024 * 1024


class _RetentionUpdate(BaseModel):
    days: int


@dataclass
class _ResearchLockEntry:
    lock: threading.Lock
    users: int = 0


class _ResearchLockLease:
    def __init__(
        self,
        registry: "_ResearchLockRegistry",
        key: str,
        entry: _ResearchLockEntry,
    ) -> None:
        self._registry = registry
        self._key = key
        self._entry = entry

    def __enter__(self) -> "_ResearchLockLease":
        try:
            self._entry.lock.acquire()
        except BaseException:
            self._registry.release(self._key, self._entry)
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._entry.lock.release()
        self._registry.release(self._key, self._entry)


class _AnalysisCancellationRegistry:
    """Remembers cancel requests by (access token, client request id).

    The model call is synchronous and cannot be interrupted, so a cancel takes
    effect at the next checkpoint: before the run starts or before its report is
    persisted. Entries are bounded and dropped once consumed or superseded.
    """

    _MAX_ENTRIES = 256

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], None] = {}
        self._guard = threading.Lock()

    def request(self, access_token: str, request_id: str) -> None:
        with self._guard:
            self._entries.pop((access_token, request_id), None)
            self._entries[(access_token, request_id)] = None
            while len(self._entries) > self._MAX_ENTRIES:
                self._entries.pop(next(iter(self._entries)))

    def is_cancelled(self, access_token: str, request_id: str | None) -> bool:
        if request_id is None:
            return False
        with self._guard:
            return (access_token, request_id) in self._entries

    def discard(self, access_token: str, request_id: str | None) -> None:
        if request_id is None:
            return
        with self._guard:
            self._entries.pop((access_token, request_id), None)


class _ResearchLockRegistry:
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
    postal_code_resolver: PostalCodeResolver | None = None,
    openai_settings: OpenAISettings | None = None,
    analysis_strategy: AnalysisStrategy | None = None,
    upload_max_bytes: int | None = None,
    company_researcher=None,
    education_researcher=None,
    linkedin_researcher=None,
    linkedin_connection_threshold: int | None = None,
    linkedin_max_profiles: int | None = None,
    research_cache_ttl_days: int | None = None,
    require_location_resolver: bool = False,
) -> FastAPI:
    configure_structured_logging()
    settings = openai_settings or load_openai_settings()
    resolver = location_resolver or load_location_resolver(
        required=require_location_resolver
    )
    postal_resolver = postal_code_resolver or load_postal_code_resolver()
    strategy = analysis_strategy or DocumentAnalysisStrategy(
        client=(
            OpenAIResponsesAnalysisClient(
                api_key=settings.api_key,
                timeout_seconds=settings.timeout_seconds,
            )
            if settings.enabled
            else None
        ),
        location_resolver=resolver,
        postal_code_resolver=postal_resolver,
    )

    selected_company_researcher = company_researcher
    selected_education_researcher = education_researcher
    selected_linkedin_researcher = linkedin_researcher
    linkedin_threshold = (
        linkedin_connection_threshold
        if linkedin_connection_threshold is not None
        else _positive_int_env("CV_VALIDATOR_LINKEDIN_CONNECTION_THRESHOLD", 500)
    )
    linkedin_profiles = (
        linkedin_max_profiles
        if linkedin_max_profiles is not None
        else _positive_int_env(
            "CV_VALIDATOR_LINKEDIN_MAX_PROFILES",
            DEFAULT_MAX_PROFILES,
        )
    )
    if linkedin_profiles > MAX_PROFILES_LIMIT:
        raise ValueError("CV_VALIDATOR_LINKEDIN_MAX_PROFILES must be at most 20")

    if settings.enabled:
        common = {
            "api_key": settings.api_key,
            "timeout_seconds": settings.timeout_seconds,
        }
        selected_company_researcher = (
            selected_company_researcher
            or OpenAIResponsesCompanyResearcher(**common)
        )
        selected_education_researcher = (
            selected_education_researcher
            or OpenAIResponsesEducationResearcher(**common)
        )
        selected_linkedin_researcher = (
            selected_linkedin_researcher
            or OpenAIResponsesLinkedInResearcher(
                **common,
                connection_threshold=linkedin_threshold,
                max_profiles=linkedin_profiles,
            )
        )

    store = PersistenceStore(
        PersistenceConfig(
            db_path=db_path or _db_path_from_env(),
            retention_days=(
                retention_days
                if retention_days is not None
                else _retention_days_from_env()
            ),
            research_cache_ttl_days=(
                research_cache_ttl_days
                if research_cache_ttl_days is not None
                else _positive_int_env("CV_VALIDATOR_RESEARCH_CACHE_TTL_DAYS", 30)
            ),
        )
    )
    feedback_store = FeedbackStore(store.config.db_path)
    max_upload_bytes = (
        upload_max_bytes
        if upload_max_bytes is not None
        else _positive_int_env("CV_VALIDATOR_UPLOAD_MAX_BYTES", DEFAULT_UPLOAD_MAX_BYTES)
    )
    research_locks = _ResearchLockRegistry()
    # Analyses run off the event loop so reads stay responsive, but the shared
    # strategy (one document converter) still processes one CV at a time.
    analysis_lock = threading.Lock()
    cancellations = _AnalysisCancellationRegistry()
    telemetry = OperationsTelemetry()
    pricing = load_pricing_catalog()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            research_locks.clear()
            if isinstance(resolver, SQLiteLocationResolver):
                resolver.close()
            if isinstance(postal_resolver, SQLitePostalCodeResolver):
                postal_resolver.close()

    app = FastAPI(
        title="CV Analyzer",
        version="2.0.0",
        lifespan=lifespan,
    )

    def capabilities() -> dict:
        return {
            "base_analysis": {
                "ready": strategy.ready,
                "strategy": strategy.name if strategy.ready else None,
                "reason": getattr(strategy, "readiness_reason", None),
            },
            "company_research": {
                "ready": selected_company_researcher is not None,
            },
            "education_research": {
                "ready": selected_education_researcher is not None,
            },
            "linkedin_research": {
                "ready": selected_linkedin_researcher is not None,
            },
            "geonames": {
                "ready": resolver is not None,
                "version": (
                    resolver.reference_data_version.version
                    if isinstance(resolver, SQLiteLocationResolver)
                    else None
                ),
            },
            "postal_reference_data": {
                "ready": postal_resolver is not None,
                "version": (
                    postal_resolver.reference_data_version.version
                    if postal_resolver is not None
                    else None
                ),
            },
            "database": {"ready": True},
            "feedback": {"ready": True, "enabled": True},
            "feedback_inbox": {"ready": True, "enabled": True},
        }

    def attach_capabilities(payload: dict) -> dict:
        payload["ai_features_enabled"] = settings.enabled
        payload["ai_capabilities"] = {
            "document_analysis": capabilities()["base_analysis"]["ready"],
            "company_research": capabilities()["company_research"]["ready"],
            "education_research": capabilities()["education_research"]["ready"],
            "linkedin_research": capabilities()["linkedin_research"]["ready"],
        }
        return payload

    def require_research_enabled(requested: bool) -> None:
        if not requested or not settings.enabled:
            raise HTTPException(status_code=409, detail="ai_disabled_for_analysis")

    def analysis_recorder(analysis_id: str) -> AnalysisRecorder:
        return AnalysisRecorder(
            analysis_id=analysis_id,
            correlation_id=store.analysis_correlation_id(analysis_id) or str(uuid4()),
            diagnostic_sink=store.record_diagnostic_event,
            usage_sink=store.record_ai_usage_event,
            pricing=pricing,
        )

    def record_research_result(
        recorder: AnalysisRecorder,
        category: str,
        result: dict[str, Any],
        started_at: str,
        started: float,
        *,
        cache_outcome: str | None = None,
    ) -> None:
        cache = result.get("cache", {})
        resolved_cache_outcome = (
            cache_outcome
            if cache_outcome is not None
            else cache.get("status") if isinstance(cache, dict) else None
        )
        saved_usage: dict[str, int] = {}
        if isinstance(cache, dict):
            direct_saved = cache.get("saved_usage")
            if isinstance(direct_saved, dict):
                saved_usage = direct_saved
            else:
                for subject in cache.get("subjects", []):
                    if isinstance(subject, dict) and isinstance(subject.get("saved_usage"), dict):
                        for key, value in subject["saved_usage"].items():
                            if isinstance(value, int):
                                saved_usage[key] = saved_usage.get(key, 0) + value
        model = result.get("model", {})
        recorder.record_ai_attempt(
            operation=f"{category}_research",
            category="research",
            provider="openai",
            configured_model=str(model.get("configured") or settings.model),
            response_model=model.get("response"),
            reasoning_effort="medium",
            attempt=1,
            outcome="completed",
            started_at=started_at,
            completed_at=utc_now(),
            latency_ms=int((perf_counter() - started) * 1000),
            usage=result.get("usage", {}),
            cache_outcome=resolved_cache_outcome,
            saved_usage=saved_usage if saved_usage else None,
        )
        recorder.emit(
            "research_completed",
            operation=f"{category}_research",
            category="research",
            outcome="completed",
            cache_outcome=resolved_cache_outcome,
        )

    @app.middleware("http")
    async def observe_request(request, call_next):
        supplied = request.headers.get("X-Correlation-ID")
        try:
            correlation_id = str(UUID(supplied)) if supplied else str(uuid4())
        except (ValueError, AttributeError):
            correlation_id = str(uuid4())
        started = perf_counter()
        request.state.correlation_id = correlation_id
        try:
            response = await call_next(request)
        except Exception:
            elapsed = (perf_counter() - started) * 1000
            route = getattr(request.scope.get("route"), "path", "unmatched")
            telemetry.request(route, 500, elapsed)
            safe_log(
                "request_completed",
                correlation_id=correlation_id,
                status_code=500,
                duration_ms=round(elapsed, 2),
                error_code="unhandled",
            )
            raise
        elapsed = (perf_counter() - started) * 1000
        route = getattr(request.scope.get("route"), "path", "unmatched")
        telemetry.request(route, response.status_code, elapsed)
        safe_log(
            "request_completed",
            correlation_id=correlation_id,
            status_code=response.status_code,
            duration_ms=round(elapsed, 2),
        )
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    @app.get("/health")
    def health() -> dict:
        current = capabilities()
        required_ready = current["database"]["ready"] and current["base_analysis"]["ready"]
        return {
            "status": "ready" if required_ready else "degraded",
            "ready": required_ready,
            "capabilities": current,
        }

    @app.get("/operations/metrics")
    def operations_metrics() -> dict:
        return telemetry.snapshot()

    @app.get("/operations/status")
    def operations_status() -> dict:
        return {
            "strategy": {
                "name": strategy.name,
                "version": strategy.version,
                "ready": strategy.ready,
                "reason": getattr(strategy, "readiness_reason", None),
            },
            "openai": {
                "enabled": settings.enabled,
                "model": settings.model,
                "store": settings.store,
                "timeout_seconds": settings.timeout_seconds,
            },
            "retention": {"days": store.config.retention_days},
            "research_cache": {"ttl_days": store.config.research_cache_ttl_days},
            "upload": {"max_bytes": max_upload_bytes},
        }

    def analyze_upload(
        content: bytes,
        filename: str,
        report_language: str,
        access_token: str,
        correlation_id: str,
        request_id: str | None = None,
    ) -> dict:
        with analysis_lock:
            try:
                return _analyze_upload(
                    content, filename, report_language, access_token, correlation_id, request_id
                )
            finally:
                cancellations.discard(access_token, request_id)

    def _analyze_upload(
        content: bytes,
        filename: str,
        report_language: str,
        access_token: str,
        correlation_id: str,
        request_id: str | None,
    ) -> dict:
        if cancellations.is_cancelled(access_token, request_id):
            raise HTTPException(status_code=409, detail="analysis_cancelled")
        analysis_id = str(uuid4())
        try:
            store.create_analysis_run(analysis_id, correlation_id, access_token)
        except PersistenceError as exc:
            raise HTTPException(status_code=500, detail="analysis_persistence_error") from exc
        recorder = AnalysisRecorder(
            analysis_id=analysis_id,
            correlation_id=correlation_id,
            diagnostic_sink=store.record_diagnostic_event,
            usage_sink=store.record_ai_usage_event,
            pricing=pricing,
        )
        if not strategy.ready:
            recorder.emit(
                "analysis_failed",
                operation="base_analysis",
                outcome="failed",
                error_code="analysis_strategy_unavailable",
            )
            store.complete_analysis_run(analysis_id, "unavailable", "analysis_strategy_unavailable")
            raise HTTPException(
                status_code=503,
                detail="analysis_strategy_unavailable",
                headers={"X-Analysis-ID": analysis_id},
            )
        try:
            result = analyze_cv_bytes_result(
                content,
                filename=filename,
                strategy=strategy,
                report_language=report_language,
                analysis_id=analysis_id,
                correlation_id=correlation_id,
                recorder=recorder,
            )
            base_status = result.report["base_analysis"]["status"]
            if base_status in {"failed", "unavailable"}:
                recorder.emit(
                    "analysis_failed",
                    operation="base_analysis",
                    outcome="failed",
                    error_code=f"analysis_{base_status}",
                )
                store.complete_analysis_run(analysis_id, base_status, f"analysis_{base_status}")
                raise HTTPException(
                    status_code=502,
                    detail=f"analysis_{base_status}",
                    headers={"X-Analysis-ID": analysis_id},
                )
            if cancellations.is_cancelled(access_token, request_id):
                recorder.emit(
                    "analysis_cancelled",
                    operation="base_analysis",
                    outcome="cancelled",
                    error_code="analysis_cancelled",
                )
                store.complete_analysis_run(analysis_id, "cancelled", "analysis_cancelled")
                raise HTTPException(
                    status_code=409,
                    detail="analysis_cancelled",
                    headers={"X-Analysis-ID": analysis_id},
                )
            response_payload = serialize_analysis_payload(
                result,
                analysis_id=analysis_id,
                access_token=access_token,
            )
            attach_capabilities(response_payload)
            store.persist_report(
                result.input_hash,
                response_payload,
                analysis_id=analysis_id,
                access_token=access_token,
                source_filename=filename,
            )
            feedback_store.materialize(analysis_id, response_payload, include_failures=False)
            recorder.emit(
                "persistence_completed",
                operation="report_persistence",
                outcome="completed",
            )
            try:
                store.persist_source_document(
                    analysis_id,
                    filename,
                    _source_content_type(filename),
                    content,
                )
            except PersistenceError:
                recorder.emit(
                    "persistence_failed",
                    operation="source_document_persistence",
                    outcome="failed",
                    error_code="source_document_persistence_error",
                )
            else:
                recorder.emit(
                    "persistence_completed",
                    operation="source_document_persistence",
                    outcome="completed",
                )
            store.complete_analysis_run(analysis_id, base_status)
            recorder.emit(
                "analysis_completed",
                operation="base_analysis",
                outcome="completed",
                accepted_count=sum(
                    item.get("status") == "accepted"
                    for key in ("employment", "education")
                    for item in result.report["base_analysis"][key]
                ),
                ambiguous_count=sum(
                    item.get("status") == "ambiguous"
                    for key in ("employment", "education")
                    for item in result.report["base_analysis"][key]
                ),
            )
            return response_payload
        except HTTPException:
            raise
        except AnalysisStrategyUnavailable as exc:
            store.complete_analysis_run(analysis_id, "unavailable", str(exc))
            raise HTTPException(
                status_code=503,
                detail=str(exc),
                headers={"X-Analysis-ID": analysis_id},
            ) from exc
        except AnalysisStrategyError as exc:
            store.complete_analysis_run(analysis_id, "failed", str(exc))
            raise HTTPException(
                status_code=422,
                detail=str(exc),
                headers={"X-Analysis-ID": analysis_id},
            ) from exc
        except ValueError as exc:
            store.complete_analysis_run(analysis_id, "failed", "analysis_strategy_invalid_output")
            raise HTTPException(
                status_code=502,
                detail="analysis_strategy_invalid_output",
                headers={"X-Analysis-ID": analysis_id},
            ) from exc
        except PersistenceError as exc:
            store.complete_analysis_run(analysis_id, "failed", "analysis_persistence_error")
            raise HTTPException(
                status_code=500,
                detail="analysis_persistence_error",
                headers={"X-Analysis-ID": analysis_id},
            ) from exc
        except Exception as exc:
            store.complete_analysis_run(analysis_id, "failed", "analysis_unhandled_error")
            recorder.emit(
                "analysis_failed",
                operation="base_analysis",
                outcome="failed",
                error_code="analysis_unhandled_error",
            )
            raise HTTPException(
                status_code=500,
                detail="analysis_failed",
                headers={"X-Analysis-ID": analysis_id},
            ) from exc

    @app.post("/analyze")
    async def analyze_single(
        request: Request,
        file: UploadFile = File(...),
        x_analysis_access_token: str | None = Header(default=None),
        x_report_language: str = Header(default="en"),
        x_analysis_request_id: str | None = Header(default=None),
    ) -> JSONResponse:
        filename = file.filename or "upload.pdf"
        try:
            content = await _read_upload(file)
        except UploadReadError as exc:
            raise HTTPException(status_code=500, detail="upload_read_error") from exc
        if len(content) > max_upload_bytes:
            raise HTTPException(status_code=413, detail="upload_size_limit_exceeded")
        access_token = x_analysis_access_token or secrets.token_urlsafe(32)
        return JSONResponse(
            await run_in_threadpool(
                analyze_upload,
                content,
                filename,
                _report_language(x_report_language),
                access_token,
                request.state.correlation_id,
                x_analysis_request_id,
            )
        )

    @app.post("/analyze/cancel", status_code=202)
    def cancel_analysis(
        x_analysis_access_token: str | None = Header(default=None),
        x_analysis_request_id: str | None = Header(default=None),
    ) -> JSONResponse:
        if not x_analysis_access_token or not x_analysis_request_id:
            raise HTTPException(status_code=400, detail="analysis_request_id_required")
        cancellations.request(x_analysis_access_token, x_analysis_request_id)
        return JSONResponse({"status": "cancel_requested"}, status_code=202)

    @app.get("/analyses")
    def list_analyses(
        x_analysis_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        store.purge_expired()
        return JSONResponse(
            {"analyses": store.list_analyses(x_analysis_access_token)}
        )

    @app.delete("/analyses")
    def delete_all_analyses(
        x_analysis_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        return JSONResponse(
            {"deleted": store.delete_all_analyses(x_analysis_access_token)}
        )

    @app.get("/analyses/{analysis_id}")
    def get_analysis(
        analysis_id: str,
        x_analysis_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        payload = _owned_payload(store, analysis_id, x_analysis_access_token)
        attach_capabilities(payload)
        return JSONResponse(payload)

    @app.post("/analyses/{analysis_id}/share")
    def create_analysis_share_link(
        analysis_id: str,
        x_analysis_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        share_token = secrets.token_urlsafe(32)
        if not store.persist_analysis_share_token(
            analysis_id,
            x_analysis_access_token,
            share_token,
        ):
            raise HTTPException(status_code=404, detail="analysis_not_found")
        return JSONResponse({"share_token": share_token})

    @app.get("/shared/analyses/{analysis_id}")
    def get_shared_analysis(
        analysis_id: str,
        x_analysis_share_token: str | None = Header(default=None),
    ) -> JSONResponse:
        if not store.analysis_share_access_allowed(analysis_id, x_analysis_share_token):
            raise HTTPException(status_code=404, detail="analysis_not_found")
        view = store.get_analysis_view(analysis_id)
        if view is None:
            raise HTTPException(status_code=404, detail="analysis_not_found")
        _attach_completed_research(store, analysis_id, view["report"])
        attach_capabilities(view["report"])
        return JSONResponse(view)

    @app.get("/analyses/{analysis_id}/diagnostics")
    def get_analysis_diagnostics(
        analysis_id: str,
        x_analysis_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        if not store.analysis_access_allowed(analysis_id, x_analysis_access_token):
            raise HTTPException(status_code=404, detail="analysis_not_found")
        payload = store.get_analysis_diagnostics(analysis_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="analysis_not_found")
        return JSONResponse(payload)

    @app.get("/analyses/{analysis_id}/usage")
    def get_analysis_usage(
        analysis_id: str,
        x_analysis_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        if not store.analysis_access_allowed(analysis_id, x_analysis_access_token):
            raise HTTPException(status_code=404, detail="analysis_not_found")
        return JSONResponse(store.get_analysis_usage_summary(analysis_id))

    @app.get("/internal/usage/summary")
    def get_usage_summary() -> JSONResponse:
        return JSONResponse(store.get_usage_summary())

    @app.get("/analyses/{analysis_id}/document")
    def get_analysis_document(
        analysis_id: str,
        x_analysis_access_token: str | None = Header(default=None),
    ) -> Response:
        if not store.analysis_access_allowed(analysis_id, x_analysis_access_token):
            raise HTTPException(status_code=404, detail="analysis_not_found")
        document = store.get_source_document(analysis_id)
        if document is None:
            raise HTTPException(status_code=404, detail="analysis_not_found")
        return Response(
            content=document["content"],
            media_type=document["content_type"],
            headers={
                "Content-Disposition": _inline_disposition(document["filename"]),
                "Cache-Control": "private, no-store",
            },
        )

    @app.get("/shared/analyses/{analysis_id}/document")
    def get_shared_analysis_document(
        analysis_id: str,
        x_analysis_share_token: str | None = Header(default=None),
    ) -> Response:
        if not store.analysis_share_access_allowed(analysis_id, x_analysis_share_token):
            raise HTTPException(status_code=404, detail="analysis_not_found")
        document = store.get_source_document(analysis_id)
        if document is None:
            raise HTTPException(status_code=404, detail="analysis_not_found")
        return Response(
            content=document["content"],
            media_type=document["content_type"],
            headers={
                "Content-Disposition": _inline_disposition(document["filename"]),
                "Cache-Control": "private, no-store",
            },
        )

    @app.delete("/analyses/{analysis_id}")
    def delete_analysis(
        analysis_id: str,
        x_analysis_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        if not store.delete_analysis(analysis_id, x_analysis_access_token):
            raise HTTPException(status_code=404, detail="analysis_not_found")
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

    @app.get("/analyses/{analysis_id}/feedback")
    def get_feedback_manifest(analysis_id: str, x_analysis_access_token: str | None = Header(default=None)) -> JSONResponse:
        payload = _owned_payload(store, analysis_id, x_analysis_access_token)
        feedback_store.materialize(analysis_id, payload, include_failures=False)
        return JSONResponse(feedback_store.manifest(analysis_id, x_analysis_access_token))

    @app.put("/analyses/{analysis_id}/feedback/{target_id}")
    def put_feedback(analysis_id: str, target_id: str, update: FeedbackInput, x_analysis_access_token: str | None = Header(default=None), x_feedback_actor_email: str | None = Header(default=None)) -> JSONResponse:
        _owned_payload(store, analysis_id, x_analysis_access_token)
        try:
            result = feedback_store.put(analysis_id, target_id, x_analysis_access_token or "", update, actor_email=x_feedback_actor_email)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(status_code=404, detail="feedback_not_found")
        return JSONResponse(result)

    @app.delete("/analyses/{analysis_id}/feedback/{target_id}")
    def withdraw_feedback(analysis_id: str, target_id: str, x_analysis_access_token: str | None = Header(default=None)) -> JSONResponse:
        _owned_payload(store, analysis_id, x_analysis_access_token)
        result = feedback_store.withdraw(analysis_id, target_id, x_analysis_access_token or "")
        if result is None:
            raise HTTPException(status_code=404, detail="feedback_not_found")
        return JSONResponse({"withdrawn": result})

    @app.get("/internal/feedback")
    def feedback_inbox(limit: int = Query(default=50, ge=1, le=100), cursor: int = Query(default=0, ge=0), rating: str | None = None, reason: str | None = None, kind: str | None = None, status: str | None = None, source: str | None = None, version: str | None = None, operation: str | None = None, error_code: str | None = None, date_from: str | None = None, date_to: str | None = None) -> JSONResponse:
        return JSONResponse(feedback_store.inbox(limit=limit, cursor=cursor, filters={"rating": rating, "reason": reason, "kind": kind, "status": status, "source": source, "version": version, "operation": operation, "error_code": error_code, "date_from": date_from, "date_to": date_to}))

    @app.put("/internal/feedback/{target_id}/{actor_hash}/triage")
    def update_feedback_triage(target_id: str, actor_hash: str, update: TriageInput, x_feedback_maintainer: str | None = Header(default=None)) -> JSONResponse:
        if not x_feedback_maintainer:
            raise HTTPException(status_code=400, detail="maintainer_required")
        if not feedback_store.triage(target_id, actor_hash, x_feedback_maintainer, update):
            raise HTTPException(status_code=404, detail="feedback_not_found")
        return JSONResponse({"updated": True})

    @app.delete("/internal/feedback/{target_id}/{actor_hash}")
    def delete_feedback_response(target_id: str, actor_hash: str, x_feedback_maintainer: str | None = Header(default=None)) -> JSONResponse:
        if not x_feedback_maintainer:
            raise HTTPException(status_code=400, detail="maintainer_required")
        if not feedback_store.delete_response(target_id, actor_hash):
            raise HTTPException(status_code=404, detail="feedback_not_found")
        return JSONResponse({"deleted": True})

    @app.post("/analyses/{analysis_id}/research/company")
    def research_company(
        analysis_id: str,
        x_analysis_access_token: str | None = Header(default=None),
        x_ai_enabled: bool = Header(default=True),
        x_research_refresh: bool = Header(default=False),
    ) -> JSONResponse:
        require_research_enabled(x_ai_enabled)
        if selected_company_researcher is None:
            raise HTTPException(status_code=503, detail="company_research_disabled")
        stored = _owned_payload(store, analysis_id, x_analysis_access_token)
        research_started_at = utc_now()
        research_started = perf_counter()
        recorder = analysis_recorder(analysis_id)
        recorder.emit("research_started", operation="company_research", category="research", outcome="started")
        try:
            request = build_company_research_request(stored)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        descriptors = company_subject_descriptors(request)
        lock_key = ":".join(descriptor.cache_key for descriptor in descriptors)
        paid_request_recorded = False
        with research_locks.acquire(f"cache:company:{lock_key}"):
            if x_research_refresh:
                for descriptor in descriptors:
                    store.invalidate_reusable_research(descriptor.cache_key)
            row = None if x_research_refresh else store.get_company_research(analysis_id)
            if row is not None:
                result = json.loads(row["result_json"])
            else:
                subject_results: list[dict[str, Any] | None] = [None] * len(descriptors)
                missing: list[int] = []
                for index, descriptor in enumerate(descriptors):
                    cached = store.get_reusable_research(descriptor)
                    if cached is None:
                        missing.append(index)
                    else:
                        subject_results[index] = materialize_cache_hit(
                            "company", cached, descriptor=descriptor
                        )
                if missing:
                    try:
                        fresh = CompanyResearchService(
                            selected_company_researcher
                        ).run(
                            stored,
                            request=CompanyResearchRequest(tuple(
                                request.input_facts[index] for index in missing
                            )),
                        )
                        record_research_result(
                            recorder,
                            "company",
                            fresh,
                            research_started_at,
                            research_started,
                            cache_outcome=(
                                "miss" if len(missing) == len(descriptors) else "partial_hit"
                            ),
                        )
                        paid_request_recorded = True
                    except ValueError as exc:
                        raise HTTPException(status_code=409, detail=str(exc)) from exc
                    except CompanyResearchTimeout as exc:
                        _research_failure(
                            telemetry,
                            analysis_id,
                            "company",
                            "timeout",
                            504,
                            "company_research_timeout",
                            exc,
                            recorder,
                            research_started_at,
                            research_started,
                        )
                    except CompanyResearchInvalidResponse as exc:
                        _research_failure(
                            telemetry,
                            analysis_id,
                            "company",
                            "invalid_response",
                            502,
                            "company_research_invalid_response",
                            exc,
                            recorder,
                            research_started_at,
                            research_started,
                        )
                    except CompanyResearchClientError as exc:
                        _research_failure(
                            telemetry,
                            analysis_id,
                            "company",
                            "client_error",
                            502,
                            "company_research_client_error",
                            exc,
                            recorder,
                            research_started_at,
                            research_started,
                        )
                    for fresh_index, request_index in enumerate(missing):
                        descriptor = descriptors[request_index]
                        subject = single_subject_result("company", fresh, fresh_index)
                        subject["cache"] = {
                            "status": "miss",
                            "format_version": descriptor.cache_format_version,
                        }
                        store.persist_reusable_research(
                            descriptor, reusable_payload("company", subject)
                        )
                        subject_results[request_index] = subject
                complete_results = [item for item in subject_results if item is not None]
                result = merge_subject_results("company", complete_results, descriptors)
                try:
                    for descriptor, subject in zip(descriptors, complete_results, strict=True):
                        store.record_cache_use(
                            analysis_id, "company", descriptor.cache_key,
                            subject["cache"]["status"],
                        )
                    store.persist_company_research(analysis_id, result)
                except PersistenceError as exc:
                    _raise_research_persistence_error(exc)
                telemetry.increment(
                    "research_cache_total",
                    category="company",
                    outcome=result["cache"]["status"],
                )
        response = deepcopy(stored)
        response["company_research"] = result
        if not paid_request_recorded:
            cache = result.get("cache", {})
            recorder.emit(
                "research_completed",
                operation="company_research",
                category="research",
                outcome="completed",
                cache_outcome=cache.get("status") if isinstance(cache, dict) else None,
            )
        return JSONResponse(response)

    @app.post("/analyses/{analysis_id}/research/education")
    def research_education(
        analysis_id: str,
        x_analysis_access_token: str | None = Header(default=None),
        x_ai_enabled: bool = Header(default=True),
        x_research_refresh: bool = Header(default=False),
    ) -> JSONResponse:
        require_research_enabled(x_ai_enabled)
        if selected_education_researcher is None:
            raise HTTPException(status_code=503, detail="education_research_disabled")
        stored = _owned_payload(store, analysis_id, x_analysis_access_token)
        research_started_at = utc_now()
        research_started = perf_counter()
        recorder = analysis_recorder(analysis_id)
        recorder.emit("research_started", operation="education_research", category="research", outcome="started")
        try:
            request = build_education_research_request(stored)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        descriptors = education_subject_descriptors(request)
        lock_key = ":".join(descriptor.cache_key for descriptor in descriptors)
        paid_request_recorded = False
        with research_locks.acquire(f"cache:education:{lock_key}"):
            if x_research_refresh:
                for descriptor in descriptors:
                    store.invalidate_reusable_research(descriptor.cache_key)
            row = None if x_research_refresh else store.get_education_research(analysis_id)
            if row is not None:
                result = json.loads(row["result_json"])
            else:
                subject_results: list[dict[str, Any] | None] = [None] * len(descriptors)
                missing: list[int] = []
                for index, descriptor in enumerate(descriptors):
                    cached = store.get_reusable_research(descriptor)
                    if cached is None:
                        missing.append(index)
                    else:
                        subject_results[index] = normalize_public_education_result(
                            materialize_cache_hit("education", cached, descriptor=descriptor)
                        )
                if missing:
                    try:
                        fresh = EducationResearchService(
                            selected_education_researcher
                        ).run(
                            stored,
                            request=EducationResearchRequest(tuple(
                                request.input_facts[index] for index in missing
                            )),
                        )
                        record_research_result(
                            recorder,
                            "education",
                            fresh,
                            research_started_at,
                            research_started,
                            cache_outcome=(
                                "miss" if len(missing) == len(descriptors) else "partial_hit"
                            ),
                        )
                        paid_request_recorded = True
                    except ValueError as exc:
                        raise HTTPException(status_code=409, detail=str(exc)) from exc
                    except EducationResearchTimeout as exc:
                        _research_failure(
                            telemetry,
                            analysis_id,
                            "education",
                            "timeout",
                            504,
                            "education_research_timeout",
                            exc,
                            recorder,
                            research_started_at,
                            research_started,
                        )
                    except EducationResearchInvalidResponse as exc:
                        _research_failure(
                            telemetry,
                            analysis_id,
                            "education",
                            "invalid_response",
                            502,
                            "education_research_invalid_response",
                            exc,
                            recorder,
                            research_started_at,
                            research_started,
                        )
                    except EducationResearchClientError as exc:
                        _research_failure(
                            telemetry,
                            analysis_id,
                            "education",
                            "client_error",
                            502,
                            "education_research_client_error",
                            exc,
                            recorder,
                            research_started_at,
                            research_started,
                        )
                    for fresh_index, request_index in enumerate(missing):
                        descriptor = descriptors[request_index]
                        subject = single_subject_result("education", fresh, fresh_index)
                        subject["cache"] = {
                            "status": "miss",
                            "format_version": descriptor.cache_format_version,
                        }
                        store.persist_reusable_research(
                            descriptor, reusable_payload("education", subject)
                        )
                        subject_results[request_index] = subject
                complete_results = [item for item in subject_results if item is not None]
                public_result = merge_subject_results("education", complete_results, descriptors)
                result = apply_owner_scoped_education_context(
                    public_result,
                    stored,
                    location_resolver=resolver,
                )
                try:
                    for descriptor, subject in zip(descriptors, complete_results, strict=True):
                        store.record_cache_use(
                            analysis_id, "education", descriptor.cache_key,
                            subject["cache"]["status"],
                        )
                    store.persist_education_research(analysis_id, result)
                except PersistenceError as exc:
                    _raise_research_persistence_error(exc)
                telemetry.increment(
                    "research_cache_total",
                    category="education",
                    outcome=result["cache"]["status"],
                )
        response = deepcopy(stored)
        response["education_research"] = result
        if not paid_request_recorded:
            cache = result.get("cache", {})
            recorder.emit(
                "research_completed",
                operation="education_research",
                category="research",
                outcome="completed",
                cache_outcome=cache.get("status") if isinstance(cache, dict) else None,
            )
        return JSONResponse(response)

    @app.post("/analyses/{analysis_id}/research/linkedin/discovery")
    def discover_linkedin(
        analysis_id: str,
        x_analysis_access_token: str | None = Header(default=None),
        x_ai_enabled: bool = Header(default=True),
    ) -> JSONResponse:
        require_research_enabled(x_ai_enabled)
        if selected_linkedin_researcher is None:
            raise HTTPException(status_code=503, detail="linkedin_research_disabled")
        stored = _owned_payload(store, analysis_id, x_analysis_access_token)
        research_started_at = utc_now()
        research_started = perf_counter()
        recorder = analysis_recorder(analysis_id)
        recorder.emit("research_started", operation="linkedin_discovery", category="research", outcome="started")
        paid_request_recorded = False
        with research_locks.acquire(f"linkedin:{analysis_id}"):
            row = store.get_linkedin_discovery(analysis_id)
            if row is not None:
                result = json.loads(row["result_json"])
            else:
                try:
                    result = LinkedInDiscoveryService(
                        selected_linkedin_researcher,
                        linkedin_threshold,
                        linkedin_profiles,
                    ).run(stored)
                    record_research_result(
                        recorder,
                        "linkedin_discovery",
                        result,
                        research_started_at,
                        research_started,
                    )
                    paid_request_recorded = True
                    store.persist_linkedin_discovery(analysis_id, result)
                except ValueError as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                except LinkedInResearchTimeout as exc:
                    _research_failure(
                        telemetry,
                        analysis_id,
                        "linkedin_discovery",
                        "timeout",
                        504,
                        "linkedin_discovery_timeout",
                        exc,
                        recorder,
                        research_started_at,
                        research_started,
                    )
                except LinkedInResearchInvalidResponse as exc:
                    _research_failure(
                        telemetry,
                        analysis_id,
                        "linkedin_discovery",
                        "invalid_response",
                        502,
                        "linkedin_discovery_invalid_response",
                        exc,
                        recorder,
                        research_started_at,
                        research_started,
                    )
                except LinkedInResearchClientError as exc:
                    _research_failure(
                        telemetry,
                        analysis_id,
                        "linkedin_discovery",
                        "client_error",
                        502,
                        "linkedin_discovery_client_error",
                        exc,
                        recorder,
                        research_started_at,
                        research_started,
                    )
                except PersistenceError as exc:
                    _raise_research_persistence_error(exc)
        response = deepcopy(stored)
        response["linkedin_discovery"] = result
        if not paid_request_recorded:
            recorder.emit(
                "research_completed",
                operation="linkedin_discovery_research",
                category="research",
                outcome="completed",
            )
        return JSONResponse(response)

    app.state.store = store
    app.state.location_resolver = resolver
    app.state.openai_settings = settings
    app.state.analysis_strategy = strategy
    app.state.upload_max_bytes = max_upload_bytes
    app.state.company_researcher = selected_company_researcher
    app.state.education_researcher = selected_education_researcher
    app.state.linkedin_researcher = selected_linkedin_researcher
    app.state.linkedin_connection_threshold = linkedin_threshold
    app.state.linkedin_max_profiles = linkedin_profiles
    app.state.research_cache_ttl_days = store.config.research_cache_ttl_days
    app.state.research_locks = research_locks
    app.state.telemetry = telemetry
    return app


def _research_failure(
    telemetry: OperationsTelemetry,
    analysis_id: str,
    category: str,
    outcome: str,
    status_code: int,
    detail: str,
    exc: Exception,
    recorder: AnalysisRecorder,
    started_at: str,
    started: float,
) -> None:
    telemetry.increment("research_failures_total", category=category, outcome=outcome)
    recorder.record_ai_attempt(
        operation=f"{category}_research",
        category="research",
        provider="openai",
        configured_model=PINNED_OPENAI_MODEL,
        response_model=getattr(exc, "model", None),
        reasoning_effort="medium",
        attempt=1,
        outcome="failed",
        error_code=outcome,
        started_at=started_at,
        completed_at=utc_now(),
        latency_ms=int((perf_counter() - started) * 1000),
        usage=getattr(exc, "usage", {}),
    )
    recorder.emit(
        "research_failed",
        operation=f"{category}_research",
        category=category,
        outcome="failed",
        error_code=outcome,
        reason=_bounded_reason(getattr(exc, "reason", None) or (str(exc) if exc.args else None)),
    )
    raise HTTPException(status_code=status_code, detail=detail) from exc


def _bounded_reason(value: Any) -> str | None:
    """Only short snake_case rule names are logged; never model or CV text."""
    if isinstance(value, str) and 0 < len(value) <= 64 and value.replace("_", "").isalnum():
        return value
    return None


def _raise_research_persistence_error(exc: PersistenceError) -> None:
    if isinstance(exc, AnalysisNotFoundPersistenceError):
        raise HTTPException(status_code=404, detail="analysis_not_found") from None
    raise HTTPException(status_code=409, detail="research_persistence_conflict") from None


async def _read_upload(upload: UploadFile) -> bytes:
    try:
        return await upload.read()
    except OSError as exc:
        raise UploadReadError("upload read failed") from exc


_SOURCE_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _source_content_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return _SOURCE_CONTENT_TYPES.get(suffix, "application/octet-stream")


def _inline_disposition(filename: str) -> str:
    """Build an inline Content-Disposition with a header-safe filename.

    The plain ``filename`` parameter keeps only printable ASCII without quotes
    or backslashes; the original name travels in RFC 5987 ``filename*``.
    """
    ascii_name = "".join(
        ch if 0x20 <= ord(ch) < 0x7F and ch not in '"\\' else "_"
        for ch in filename
    ).strip() or "document"
    disposition = f'inline; filename="{ascii_name}"'
    if ascii_name != filename:
        disposition += f"; filename*=UTF-8''{quote(filename, safe='')}"
    return disposition


def _attach_completed_research(
    store: PersistenceStore,
    analysis_id: str,
    payload: dict,
) -> dict:
    completed_rows = (
        ("company_research", store.get_company_research(analysis_id)),
        ("education_research", store.get_education_research(analysis_id)),
        ("linkedin_discovery", store.get_linkedin_discovery(analysis_id)),
    )
    for key, row in completed_rows:
        if row is not None:
            payload[key] = json.loads(row["result_json"])
    return payload


def _owned_payload(
    store: PersistenceStore,
    analysis_id: str,
    access_token: str | None,
) -> dict:
    if not store.analysis_access_allowed(analysis_id, access_token):
        raise HTTPException(status_code=404, detail="analysis_not_found")
    payload = store.get_analysis_payload(analysis_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="analysis_not_found")
    return _attach_completed_research(store, analysis_id, payload)


def _default_app() -> FastAPI:
    require_location_resolver = os.environ.get(
        "CV_VALIDATOR_REQUIRE_LOCATION_RESOLVER",
        "false",
    ).lower() in {"1", "true", "yes"}
    return create_app(require_location_resolver=require_location_resolver)


app = _default_app()
