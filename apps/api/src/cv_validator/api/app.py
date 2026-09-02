from __future__ import annotations

import json
import os
import secrets
import threading
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from cv_validator.analysis import (
    AnalysisStrategy,
    AnalysisStrategyError,
    AnalysisStrategyUnavailable,
)
from cv_validator.analysis.docling_luna import DoclingLunaAnalysisStrategy
from cv_validator.analysis.luna_client import OpenAIResponsesLunaClient
from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.config import load_location_resolver
from cv_validator.errors import (
    AnalysisNotFoundPersistenceError,
    AnalysisRuntimeError,
    PersistenceError,
    UploadReadError,
)
from cv_validator.location import LocationResolver, SQLiteLocationResolver
from cv_validator.openai_config import OpenAISettings, load_openai_settings
from cv_validator.operations import OperationsTelemetry, safe_log
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

DEFAULT_DB = Path("data/docling_luna.db")
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
    openai_settings: OpenAISettings | None = None,
    analysis_strategy: AnalysisStrategy | None = None,
    batch_max_files: int | None = None,
    batch_max_bytes: int | None = None,
    company_researcher=None,
    education_researcher=None,
    linkedin_researcher=None,
    linkedin_connection_threshold: int | None = None,
    linkedin_max_profiles: int | None = None,
    research_cache_ttl_days: int | None = None,
    require_location_resolver: bool = False,
) -> FastAPI:
    settings = openai_settings or load_openai_settings()
    resolver = location_resolver or load_location_resolver(
        required=require_location_resolver
    )
    strategy = analysis_strategy or DoclingLunaAnalysisStrategy(
        client=(
            OpenAIResponsesLunaClient(
                api_key=settings.api_key,
                timeout_seconds=settings.timeout_seconds,
            )
            if settings.enabled
            else None
        ),
        location_resolver=resolver,
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
    max_files = (
        batch_max_files
        if batch_max_files is not None
        else _positive_int_env("CV_VALIDATOR_BATCH_MAX_FILES", DEFAULT_BATCH_MAX_FILES)
    )
    max_bytes = (
        batch_max_bytes
        if batch_max_bytes is not None
        else _positive_int_env("CV_VALIDATOR_BATCH_MAX_BYTES", DEFAULT_BATCH_MAX_BYTES)
    )
    research_locks = _ResearchLockRegistry()
    telemetry = OperationsTelemetry()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            research_locks.clear()
            if isinstance(resolver, SQLiteLocationResolver):
                resolver.close()

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
            "database": {"ready": True},
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

    @app.middleware("http")
    async def observe_request(request, call_next):
        supplied = request.headers.get("X-Correlation-ID")
        try:
            correlation_id = str(UUID(supplied)) if supplied else str(uuid4())
        except (ValueError, AttributeError):
            correlation_id = str(uuid4())
        started = perf_counter()
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
            },
            "openai": {
                "enabled": settings.enabled,
                "model": settings.model,
                "store": settings.store,
                "timeout_seconds": settings.timeout_seconds,
            },
            "retention": {"days": store.config.retention_days},
            "research_cache": {"ttl_days": store.config.research_cache_ttl_days},
            "batch": {"max_files": max_files, "max_bytes": max_bytes},
        }

    def analyze_upload(
        content: bytes,
        filename: str,
        report_language: str,
        access_token: str,
    ) -> dict:
        try:
            result = analyze_cv_bytes_result(
                content,
                filename=filename,
                strategy=strategy,
                report_language=report_language,
            )
            analysis_id = str(uuid4())
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
            return response_payload
        except AnalysisStrategyUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except AnalysisStrategyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=502,
                detail="analysis_strategy_invalid_output",
            ) from exc
        except PersistenceError as exc:
            raise HTTPException(
                status_code=500,
                detail="analysis_persistence_error",
            ) from exc

    @app.post("/analyze")
    async def analyze_single(
        file: UploadFile = File(...),
        x_analysis_access_token: str | None = Header(default=None),
        x_report_language: str = Header(default="en"),
    ) -> JSONResponse:
        filename = file.filename or "upload.pdf"
        try:
            content = await _read_upload(file)
        except UploadReadError as exc:
            raise HTTPException(status_code=500, detail="upload_read_error") from exc
        access_token = x_analysis_access_token or secrets.token_urlsafe(32)
        return JSONResponse(
            analyze_upload(
                content,
                filename,
                _report_language(x_report_language),
                access_token,
            )
        )

    @app.post("/analyze/batch")
    async def analyze_batch(
        files: list[UploadFile] = File(...),
        x_analysis_access_token: str | None = Header(default=None),
        x_report_language: str = Header(default="en"),
    ) -> JSONResponse:
        prepared = await _prepare_batch(
            files,
            max_files=max_files,
            max_bytes=max_bytes,
        )
        language = _report_language(x_report_language)
        access_token = x_analysis_access_token or secrets.token_urlsafe(32)
        results: list[dict] = []
        for item in prepared:
            filename = item.upload.filename or "upload.pdf"
            if item.error is not None:
                results.append(
                    {"filename": filename, "status": "error", "error": item.error}
                )
                continue
            try:
                payload = analyze_upload(
                    item.content or b"",
                    filename,
                    language,
                    access_token,
                )
            except HTTPException as exc:
                results.append(
                    {
                        "filename": filename,
                        "status": "error",
                        "error": exc.detail,
                    }
                )
            else:
                results.append(
                    {"filename": filename, "status": "ok", "report": payload}
                )
        return JSONResponse(
            {"analysis_access_token": access_token, "results": results}
        )

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
        try:
            request = build_company_research_request(stored)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        descriptors = company_subject_descriptors(request)
        lock_key = ":".join(descriptor.cache_key for descriptor in descriptors)
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
        try:
            request = build_education_research_request(stored)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        descriptors = education_subject_descriptors(request)
        lock_key = ":".join(descriptor.cache_key for descriptor in descriptors)
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
                    )
                except PersistenceError as exc:
                    _raise_research_persistence_error(exc)
        response = deepcopy(stored)
        response["linkedin_discovery"] = result
        return JSONResponse(response)

    app.state.store = store
    app.state.location_resolver = resolver
    app.state.openai_settings = settings
    app.state.analysis_strategy = strategy
    app.state.batch_max_files = max_files
    app.state.batch_max_bytes = max_bytes
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
) -> None:
    telemetry.increment("research_failures_total", category=category, outcome=outcome)
    safe_log(
        "research_failed",
        analysis_id=analysis_id,
        category=category,
        error_code=outcome,
    )
    raise HTTPException(status_code=status_code, detail=detail) from exc


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
                    error="upload_read_error",
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
    completed_rows = (
        ("company_research", store.get_company_research(analysis_id)),
        ("education_research", store.get_education_research(analysis_id)),
        ("linkedin_discovery", store.get_linkedin_discovery(analysis_id)),
    )
    for key, row in completed_rows:
        if row is not None:
            payload[key] = json.loads(row["result_json"])
    return payload


def _default_app() -> FastAPI:
    require_location_resolver = os.environ.get(
        "CV_VALIDATOR_REQUIRE_LOCATION_RESOLVER",
        "false",
    ).lower() in {"1", "true", "yes"}
    return create_app(require_location_resolver=require_location_resolver)


app = _default_app()
