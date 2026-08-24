from __future__ import annotations

import os
import json
import threading
import secrets
from time import perf_counter
from copy import deepcopy
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from pydantic import BaseModel
from fastapi.responses import JSONResponse

from cv_validator.ai.application import DocumentAnalyzer
from cv_validator.ai.config import AISettings, load_ai_settings
from cv_validator.ai.openai_client import OpenAIResponsesDocumentAnalyzer
from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.config import load_ingestion_config, load_location_resolver
from cv_validator.ingestion import IngestionError
from cv_validator.pipeline import analyze_cv_bytes_result
from cv_validator.location import LocationResolver, SQLiteLocationResolver
from cv_validator.errors import AnalysisRuntimeError, UploadReadError
from cv_validator.serialization import serialize_analysis_payload
from cv_validator.research.company import CompanyResearchService, build_company_research_request
from cv_validator.research.domain import CompanyResearchClientError, CompanyResearchInvalidResponse, CompanyResearchTimeout
from cv_validator.research.openai_client import OpenAIResponsesCompanyResearcher
from cv_validator.research.education import EducationResearchService, build_education_research_request
from cv_validator.research.cache import (
    company_cache_descriptor, education_cache_descriptor, materialize_cache_hit,
    reusable_payload,
)
from cv_validator.research.domain import EducationResearchClientError, EducationResearchInvalidResponse, EducationResearchTimeout
from cv_validator.research.openai_client import OpenAIResponsesEducationResearcher
from cv_validator.research.linkedin import LinkedInComparisonService, LinkedInDiscoveryService, normalize_linkedin_url
from cv_validator.research.domain import LinkedInResearchClientError, LinkedInResearchInvalidResponse, LinkedInResearchTimeout
from cv_validator.research.openai_client import OpenAIResponsesLinkedInResearcher
from cv_validator.operations import OperationsTelemetry, safe_log

DEFAULT_DB = Path("data/cv_validator.db")
DEFAULT_BATCH_MAX_FILES = 4
DEFAULT_BATCH_MAX_BYTES = 20 * 1024 * 1024


class _LinkedInConfirmation(BaseModel):
    profile_url: str


@dataclass(frozen=True)
class _PreparedUpload:
    upload: UploadFile
    content: bytes | None
    error: str | None = None


def _db_path_from_env() -> Path:
    return Path(os.environ.get("CV_VALIDATOR_DB_PATH", DEFAULT_DB))


def _retention_days_from_env() -> int:
    return int(os.environ.get("CV_VALIDATOR_RETENTION_DAYS", "90"))


def _positive_int_env(name: str, default: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


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
    research_cache_ttl_days: int | None = None,
) -> FastAPI:
    ingestion_config = load_ingestion_config()
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
    if selected_ai_settings.enabled and selected_linkedin_researcher is None:
        selected_linkedin_researcher = OpenAIResponsesLinkedInResearcher(api_key=selected_ai_settings.api_key, timeout_seconds=selected_ai_settings.timeout_seconds)
    selected_linkedin_threshold = linkedin_connection_threshold if linkedin_connection_threshold is not None else _positive_int_env("CV_VALIDATOR_LINKEDIN_CONNECTION_THRESHOLD", 500)
    resolver = location_resolver or load_location_resolver()
    store = PersistenceStore(
        PersistenceConfig(
            db_path=db_path or _db_path_from_env(),
            retention_days=retention_days if retention_days is not None else _retention_days_from_env(),
            research_cache_ttl_days=research_cache_ttl_days if research_cache_ttl_days is not None else _positive_int_env("CV_VALIDATOR_RESEARCH_CACHE_TTL_DAYS", 30),
        )
    )
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
            if isinstance(resolver, SQLiteLocationResolver):
                resolver.close()

    app = FastAPI(
        title="CV Location Consistency Analyzer",
        version="0.1.0",
        lifespan=lifespan,
    )
    telemetry = OperationsTelemetry()

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
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/operations/metrics")
    def operations_metrics() -> dict:
        return telemetry.snapshot()

    @app.get("/operations/status")
    def operations_status() -> dict:
        return {
            "ai_enabled": selected_ai_settings.enabled,
            "retention": {"days": store.config.retention_days, "production_approved": False},
            "research_cache": {"ttl_days": store.config.research_cache_ttl_days},
            "batch": {"max_files": selected_batch_max_files, "max_bytes": selected_batch_max_bytes},
        }

    @app.post("/analyze")
    async def analyze_single(file: UploadFile = File(...), x_analysis_access_token: str | None = Header(default=None)) -> JSONResponse:
        filename = file.filename or "upload.pdf"
        try:
            content = await _read_upload(file)
            result = analyze_cv_bytes_result(
                content,
                filename=filename,
                ingestion_config=ingestion_config,
                location_resolver=resolver,
                ai_settings=selected_ai_settings,
                document_analyzer=selected_document_analyzer,
            )
            analysis_id = str(uuid4())
            access_token = x_analysis_access_token or secrets.token_urlsafe(32)
            payload = serialize_analysis_payload(
                result,
                selected_ai_settings,
                analysis_id=analysis_id,
            )
            store.persist_report(
                result.document_identity,
                result.report,
                report_payload=payload,
                analysis_id=analysis_id,
                ai_analysis=payload["ai_analysis"],
                access_token=access_token,
            )
        except IngestionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except AnalysisRuntimeError as exc:
            raise HTTPException(
                status_code=500,
                detail="analysis_runtime_error",
            ) from exc

        return JSONResponse(payload)

    @app.post("/analyze/batch")
    async def analyze_batch(files: list[UploadFile] = File(...), x_analysis_access_token: str | None = Header(default=None)) -> JSONResponse:
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
                result = analyze_cv_bytes_result(
                    item.content,
                    filename=filename,
                    ingestion_config=ingestion_config,
                    location_resolver=resolver,
                    ai_settings=selected_ai_settings,
                    document_analyzer=selected_document_analyzer,
                )
                analysis_id = str(uuid4())
                access_token = x_analysis_access_token or secrets.token_urlsafe(32)
                payload = serialize_analysis_payload(
                    result,
                    selected_ai_settings,
                    analysis_id=analysis_id,
                )
                store.persist_report(
                    result.document_identity,
                    result.report,
                    report_payload=payload,
                    analysis_id=analysis_id,
                    ai_analysis=payload["ai_analysis"],
                    access_token=access_token,
                )
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

    research_locks: dict[str, threading.Lock] = {}
    research_locks_guard = threading.Lock()

    @app.post("/analyses/{analysis_id}/research/company")
    def research_company(analysis_id: str, x_analysis_access_token: str | None = Header(default=None)) -> JSONResponse:
        if selected_company_researcher is None:
            raise HTTPException(status_code=503, detail="company_research_disabled")
        if not store.analysis_access_allowed(analysis_id, x_analysis_access_token):
            raise HTTPException(status_code=404, detail="analysis_not_found")
        stored_payload = store.get_analysis_payload(analysis_id)
        if stored_payload is None:
            raise HTTPException(status_code=404, detail="analysis_not_found")
        try:
            request = build_company_research_request(stored_payload)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        descriptor = company_cache_descriptor(request)
        with research_locks_guard:
            lock = research_locks.setdefault(f"cache:{descriptor.cache_key}", threading.Lock())
        with lock:
            completed = store.get_company_research(analysis_id)
            if completed is not None:
                result = json.loads(completed["result_json"])
            else:
                cached = store.get_reusable_research(descriptor)
                if cached is not None:
                    result = materialize_cache_hit("company", cached, descriptor=descriptor)
                    store.record_cache_use(analysis_id, "company", descriptor.cache_key, "hit")
                    store.persist_company_research(analysis_id, result)
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
        response = deepcopy(stored_payload)
        response["company_research"] = result
        return JSONResponse(response)

    @app.post("/analyses/{analysis_id}/research/education")
    def research_education(analysis_id: str, x_analysis_access_token: str | None = Header(default=None)) -> JSONResponse:
        if selected_education_researcher is None:
            raise HTTPException(status_code=503, detail="education_research_disabled")
        if not store.analysis_access_allowed(analysis_id, x_analysis_access_token):
            raise HTTPException(status_code=404, detail="analysis_not_found")
        stored_payload = store.get_analysis_payload(analysis_id)
        if stored_payload is None:
            raise HTTPException(status_code=404, detail="analysis_not_found")
        try:
            request = build_education_research_request(stored_payload)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        descriptor = education_cache_descriptor(request)
        with research_locks_guard:
            lock = research_locks.setdefault(f"cache:{descriptor.cache_key}", threading.Lock())
        with lock:
            completed = store.get_education_research(analysis_id)
            if completed is not None:
                result = json.loads(completed["result_json"])
            else:
                cached = store.get_reusable_research(descriptor)
                if cached is not None:
                    result = materialize_cache_hit("education", cached, descriptor=descriptor)
                    store.record_cache_use(analysis_id, "education", descriptor.cache_key, "hit")
                    store.persist_education_research(analysis_id, result)
                    telemetry.increment("research_cache_total", category="education", outcome="hit")
                else:
                    try:
                        result = EducationResearchService(selected_education_researcher).run(stored_payload)
                        result["cache"] = {"status": "miss", "format_version": descriptor.cache_format_version}
                        store.persist_reusable_research(descriptor, reusable_payload("education", result))
                        store.record_cache_use(analysis_id, "education", descriptor.cache_key, "miss")
                        store.persist_education_research(analysis_id, result)
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
        response = deepcopy(stored_payload)
        response["education_research"] = result
        return JSONResponse(response)

    @app.post("/analyses/{analysis_id}/research/linkedin/discovery")
    def discover_linkedin(analysis_id: str, x_analysis_access_token: str | None = Header(default=None)) -> JSONResponse:
        stored_payload = _owned_payload(store, analysis_id, x_analysis_access_token)
        if selected_linkedin_researcher is None: raise HTTPException(status_code=503, detail="linkedin_research_disabled")
        with research_locks_guard: lock = research_locks.setdefault(f"linkedin:{analysis_id}", threading.Lock())
        with lock:
            completed = store.get_linkedin_discovery(analysis_id)
            if completed is not None: result = json.loads(completed["result_json"])
            else:
                try:
                    result = LinkedInDiscoveryService(selected_linkedin_researcher, selected_linkedin_threshold).run(stored_payload)
                    store.persist_linkedin_discovery(analysis_id, result)
                except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
                except LinkedInResearchTimeout as exc:
                    _record_research_failure(telemetry, analysis_id, "linkedin_discovery", "timeout")
                    raise HTTPException(status_code=504, detail="linkedin_discovery_timeout") from exc
                except LinkedInResearchInvalidResponse as exc:
                    _record_research_failure(telemetry, analysis_id, "linkedin_discovery", "invalid_response")
                    raise HTTPException(status_code=502, detail="linkedin_discovery_invalid_response") from exc
                except LinkedInResearchClientError as exc:
                    _record_research_failure(telemetry, analysis_id, "linkedin_discovery", "client_error")
                    raise HTTPException(status_code=502, detail="linkedin_discovery_client_error") from exc
        response = deepcopy(stored_payload); response["linkedin_discovery"] = result
        return JSONResponse(response)

    @app.post("/analyses/{analysis_id}/research/linkedin/confirmation")
    def confirm_linkedin(analysis_id: str, confirmation: _LinkedInConfirmation, x_analysis_access_token: str | None = Header(default=None)) -> JSONResponse:
        _owned_payload(store, analysis_id, x_analysis_access_token)
        discovery_row = store.get_linkedin_discovery(analysis_id)
        if discovery_row is None: raise HTTPException(status_code=409, detail="linkedin_discovery_required")
        discovery = json.loads(discovery_row["result_json"])
        try: profile_url = normalize_linkedin_url(confirmation.profile_url)
        except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
        allowed = {normalize_linkedin_url(profile["profile_url"]) for profile in discovery["possible_profiles"]}
        if profile_url not in allowed: raise HTTPException(status_code=409, detail="profile_not_in_discovery")
        try: audit = store.confirm_linkedin_profile(analysis_id, profile_url, discovery["versions"]["research"])
        except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
        return JSONResponse({"linkedin_confirmation": audit})

    @app.post("/analyses/{analysis_id}/research/linkedin/comparison")
    def compare_linkedin(analysis_id: str, x_analysis_access_token: str | None = Header(default=None)) -> JSONResponse:
        stored_payload = _owned_payload(store, analysis_id, x_analysis_access_token)
        if selected_linkedin_researcher is None: raise HTTPException(status_code=503, detail="linkedin_research_disabled")
        confirmation = store.get_linkedin_confirmation(analysis_id)
        discovery_row = store.get_linkedin_discovery(analysis_id)
        if confirmation is None or discovery_row is None: raise HTTPException(status_code=409, detail="linkedin_confirmation_required")
        stored_payload["linkedin_discovery"] = json.loads(discovery_row["result_json"])
        with research_locks_guard: lock = research_locks.setdefault(f"linkedin-comparison:{analysis_id}", threading.Lock())
        with lock:
            completed = store.get_linkedin_comparison(analysis_id)
            if completed is not None: result = json.loads(completed["result_json"])
            else:
                try:
                    result = LinkedInComparisonService(selected_linkedin_researcher).run(stored_payload, confirmation["profile_url"])
                    store.persist_linkedin_comparison(analysis_id, confirmation["profile_url"], result)
                except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
                except LinkedInResearchTimeout as exc:
                    _record_research_failure(telemetry, analysis_id, "linkedin_comparison", "timeout")
                    raise HTTPException(status_code=504, detail="linkedin_comparison_timeout") from exc
                except LinkedInResearchInvalidResponse as exc:
                    _record_research_failure(telemetry, analysis_id, "linkedin_comparison", "invalid_response")
                    raise HTTPException(status_code=502, detail="linkedin_comparison_invalid_response") from exc
                except LinkedInResearchClientError as exc:
                    _record_research_failure(telemetry, analysis_id, "linkedin_comparison", "client_error")
                    raise HTTPException(status_code=502, detail="linkedin_comparison_client_error") from exc
        response = deepcopy(stored_payload); response["linkedin_comparison"] = result
        return JSONResponse(response)

    app.state.store = store
    app.state.location_resolver = resolver
    app.state.ai_settings = selected_ai_settings
    app.state.document_analyzer = selected_document_analyzer
    app.state.batch_max_files = selected_batch_max_files
    app.state.batch_max_bytes = selected_batch_max_bytes
    app.state.company_researcher = selected_company_researcher
    app.state.education_researcher = selected_education_researcher
    app.state.linkedin_researcher = selected_linkedin_researcher
    app.state.linkedin_connection_threshold = selected_linkedin_threshold
    app.state.research_cache_ttl_days = store.config.research_cache_ttl_days
    app.state.telemetry = telemetry
    return app


def _record_research_failure(telemetry: OperationsTelemetry, analysis_id: str, category: str, outcome: str) -> None:
    telemetry.increment("research_failures_total", category=category, outcome=outcome)
    safe_log("research_failed", analysis_id=analysis_id, category=category, error_code=outcome)


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
    return create_app()


app = _default_app()


def _owned_payload(store: PersistenceStore, analysis_id: str, access_token: str | None) -> dict:
    if not store.analysis_access_allowed(analysis_id, access_token): raise HTTPException(status_code=404, detail="analysis_not_found")
    payload = store.get_analysis_payload(analysis_id)
    if payload is None: raise HTTPException(status_code=404, detail="analysis_not_found")
    return payload
