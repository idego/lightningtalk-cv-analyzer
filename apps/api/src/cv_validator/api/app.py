from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from cv_validator.ai.config import AISettings, load_ai_settings
from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.config import load_ingestion_config, load_location_resolver
from cv_validator.ingestion import IngestionError
from cv_validator.pipeline import analyze_cv_bytes_result
from cv_validator.location import LocationResolver, SQLiteLocationResolver
from cv_validator.errors import AnalysisRuntimeError, UploadReadError
from cv_validator.serialization import serialize_report_payload

DEFAULT_DB = Path("data/cv_validator.db")


def _db_path_from_env() -> Path:
    return Path(os.environ.get("CV_VALIDATOR_DB_PATH", DEFAULT_DB))


def _retention_days_from_env() -> int:
    return int(os.environ.get("CV_VALIDATOR_RETENTION_DAYS", "90"))


def create_app(
    db_path: Path | None = None,
    retention_days: int | None = None,
    location_resolver: LocationResolver | None = None,
    ai_settings: AISettings | None = None,
) -> FastAPI:
    ingestion_config = load_ingestion_config()
    selected_ai_settings = ai_settings or load_ai_settings()
    resolver = location_resolver or load_location_resolver()
    store = PersistenceStore(
        PersistenceConfig(
            db_path=db_path or _db_path_from_env(),
            retention_days=retention_days if retention_days is not None else _retention_days_from_env(),
        )
    )
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
    async def analyze_single(file: UploadFile = File(...)) -> JSONResponse:
        filename = file.filename or "upload.pdf"
        try:
            content = await _read_upload(file)
            result = analyze_cv_bytes_result(
                content,
                filename=filename,
                ingestion_config=ingestion_config,
                location_resolver=resolver,
            )
            payload = serialize_report_payload(result.report)
            store.persist_report(
                result.document_identity,
                result.report,
                report_payload=payload,
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
    async def analyze_batch(files: list[UploadFile] = File(...)) -> JSONResponse:
        results: list[dict] = []
        for upload in files:
            filename = upload.filename or "upload.pdf"
            try:
                content = await _read_upload(upload)
                result = analyze_cv_bytes_result(
                    content,
                    filename=filename,
                    ingestion_config=ingestion_config,
                    location_resolver=resolver,
                )
                payload = serialize_report_payload(result.report)
                store.persist_report(
                    result.document_identity,
                    result.report,
                    report_payload=payload,
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

    app.state.store = store
    app.state.location_resolver = resolver
    app.state.ai_settings = selected_ai_settings
    return app


async def _read_upload(upload: UploadFile) -> bytes:
    try:
        return await upload.read()
    except OSError as exc:
        raise UploadReadError("upload read failed") from exc


def _default_app() -> FastAPI:
    return create_app()


app = _default_app()
