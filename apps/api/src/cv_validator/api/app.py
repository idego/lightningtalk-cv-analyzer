from __future__ import annotations

import os
import json
import threading
import secrets
from copy import deepcopy
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
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
from cv_validator.research.company import CompanyResearchService
from cv_validator.research.domain import CompanyResearchClientError, CompanyResearchInvalidResponse, CompanyResearchTimeout
from cv_validator.research.openai_client import OpenAIResponsesCompanyResearcher
from cv_validator.research.education import EducationResearchService
from cv_validator.research.domain import EducationResearchClientError, EducationResearchInvalidResponse, EducationResearchTimeout
from cv_validator.research.openai_client import OpenAIResponsesEducationResearcher

DEFAULT_DB = Path("data/cv_validator.db")
DEFAULT_BATCH_MAX_FILES = 4
DEFAULT_BATCH_MAX_BYTES = 20 * 1024 * 1024


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
    resolver = location_resolver or load_location_resolver()
    store = PersistenceStore(
        PersistenceConfig(
            db_path=db_path or _db_path_from_env(),
            retention_days=retention_days if retention_days is not None else _retention_days_from_env(),
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

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

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
        with research_locks_guard:
            lock = research_locks.setdefault(analysis_id, threading.Lock())
        with lock:
            completed = store.get_company_research(analysis_id)
            if completed is not None:
                result = json.loads(completed["result_json"])
            else:
                try:
                    result = CompanyResearchService(selected_company_researcher).run(stored_payload)
                    store.persist_company_research(analysis_id, result)
                except ValueError as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                except CompanyResearchTimeout as exc:
                    raise HTTPException(status_code=504, detail="company_research_timeout") from exc
                except CompanyResearchInvalidResponse as exc:
                    raise HTTPException(status_code=502, detail="company_research_invalid_response") from exc
                except CompanyResearchClientError as exc:
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
        with research_locks_guard:
            lock = research_locks.setdefault(analysis_id, threading.Lock())
        with lock:
            completed = store.get_education_research(analysis_id)
            if completed is not None:
                result = json.loads(completed["result_json"])
            else:
                try:
                    result = EducationResearchService(selected_education_researcher).run(stored_payload)
                    store.persist_education_research(analysis_id, result)
                except ValueError as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                except EducationResearchTimeout as exc:
                    raise HTTPException(status_code=504, detail="education_research_timeout") from exc
                except EducationResearchInvalidResponse as exc:
                    raise HTTPException(status_code=502, detail="education_research_invalid_response") from exc
                except EducationResearchClientError as exc:
                    raise HTTPException(status_code=502, detail="education_research_client_error") from exc
        response = deepcopy(stored_payload)
        response["education_research"] = result
        return JSONResponse(response)

    app.state.store = store
    app.state.location_resolver = resolver
    app.state.ai_settings = selected_ai_settings
    app.state.document_analyzer = selected_document_analyzer
    app.state.batch_max_files = selected_batch_max_files
    app.state.batch_max_bytes = selected_batch_max_bytes
    app.state.company_researcher = selected_company_researcher
    app.state.education_researcher = selected_education_researcher
    return app


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
