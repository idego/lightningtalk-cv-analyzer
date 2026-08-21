from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.config import load_ingestion_config
from cv_validator.ingestion import IngestionError
from cv_validator.pipeline import analyze_cv_bytes_result

DEFAULT_DB = Path("data/cv_validator.db")


def _db_path_from_env() -> Path:
    return Path(os.environ.get("CV_VALIDATOR_DB_PATH", DEFAULT_DB))


def _retention_days_from_env() -> int:
    return int(os.environ.get("CV_VALIDATOR_RETENTION_DAYS", "90"))


def create_app(
    db_path: Path | None = None,
    retention_days: int | None = None,
) -> FastAPI:
    ingestion_config = load_ingestion_config()
    store = PersistenceStore(
        PersistenceConfig(
            db_path=db_path or _db_path_from_env(),
            retention_days=retention_days if retention_days is not None else _retention_days_from_env(),
        )
    )
    app = FastAPI(title="CV Location Consistency Analyzer", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/analyze")
    async def analyze_single(file: UploadFile = File(...)) -> JSONResponse:
        content = await file.read()
        filename = file.filename or "upload.pdf"
        try:
            result = analyze_cv_bytes_result(
                content, filename=filename, ingestion_config=ingestion_config
            )
        except IngestionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        store.persist_report(result.document_identity, result.report)
        return JSONResponse(result.report.to_dict())

    @app.post("/analyze/batch")
    async def analyze_batch(files: list[UploadFile] = File(...)) -> JSONResponse:
        results: list[dict] = []
        for upload in files:
            content = await upload.read()
            filename = upload.filename or "upload.pdf"
            try:
                result = analyze_cv_bytes_result(
                    content, filename=filename, ingestion_config=ingestion_config
                )
                store.persist_report(result.document_identity, result.report)
                results.append(
                    {
                        "filename": filename,
                        "status": "ok",
                        "report": result.report.to_dict(),
                    }
                )
            except IngestionError as exc:
                results.append({"filename": filename, "status": "error", "error": str(exc)})
        return JSONResponse({"results": results})

    app.state.store = store
    return app


def _default_app() -> FastAPI:
    return create_app()


app = _default_app()
