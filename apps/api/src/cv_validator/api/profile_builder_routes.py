from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute
from cv_validator.analysis.docling_converter import DoclingTextConverter
from cv_validator.analysis.strategy import AnalysisStrategyError, SourceFormat
from cv_validator.api.concurrency import AnalysisCancellationRegistry
from cv_validator.api.persistence import PersistenceStore
from cv_validator.api.profile_builder_store import ProfileBuilderStore
from cv_validator.errors import PersistenceError, UploadReadError
from cv_validator.openai_config import OpenAISettings
from cv_validator.operations import AnalysisRecorder, safe_log
from cv_validator.usage import load_pricing_catalog
from cv_validator.profile_builder_ai import (
    ProfileAISettings, ProfileExtractor, ProfileSummarizer, ProfileTransformer,
    ProfileExtractionError, ProfileSummaryError, ProfileTransformError,
    OpenAIResponsesProfileExtractor, OpenAIResponsesProfileSummarizer, OpenAIResponsesProfileTransformer,
    extract_candidate_profile, generate_candidate_profile_summary, generate_candidate_profile_transform,
)
from cv_validator.profile_builder import (
    ProfileBuilderPreferences,
    ProfileBuilderSnapshot,
    ProfileCustomFieldDefinition,
    ProfileExportRequest,
    ProfilePdfExportError,
    ProfileSummaryGenerationRequest,
    ProfileTemplate,
    ProfileTransformGenerationRequest,
    apply_profile_conversion_preferences,
    default_profile_template,
    materialize_custom_fields,
    render_candidate_profile_docx,
    render_candidate_profile_pdf,
    sanitize_candidate_profile,
    sanitize_profile_builder_filename,
    sanitize_profile_builder_preferences,
    sanitize_profile_builder_snapshot,
    sanitize_profile_custom_field_definition,
    sanitize_profile_template,
)

DEFAULT_PROFILE_BUILDER_MAX_BYTES = 10 * 1024 * 1024


class _PrivateProfileRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def private_response(request):
            response = await handler(request)
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response

        return private_response


def create_profile_builder_router(
    analysis_store: PersistenceStore,
    settings: OpenAISettings,
    profile_extractor: ProfileExtractor | None = None,
    profile_summarizer: ProfileSummarizer | None = None,
    profile_transformer: ProfileTransformer | None = None,
    profile_builder_max_bytes: int | None = None,
    cancellations: AnalysisCancellationRegistry | None = None,
) -> APIRouter:
    router = APIRouter(tags=["Profile Builder"], route_class=_PrivateProfileRoute)
    store = ProfileBuilderStore(analysis_store)
    # Same checkpoint semantics as /analyze: a cancel takes effect before the
    # model call starts or before the extracted profile is returned.
    extraction_cancellations = cancellations or AnalysisCancellationRegistry()
    selected_ai_settings = ProfileAISettings(**asdict(settings))
    pricing = load_pricing_catalog()

    def usage_recorder() -> AnalysisRecorder:
        # Independent random accounting IDs; never store profile content or access tokens.
        return AnalysisRecorder(
            analysis_id=str(uuid4()), correlation_id=str(uuid4()),
            diagnostic_sink=analysis_store.record_diagnostic_event,
            usage_sink=analysis_store.record_ai_usage_event, pricing=pricing,
        )

    selected_profile_extractor = profile_extractor
    selected_profile_summarizer = profile_summarizer
    selected_profile_transformer = profile_transformer
    if settings.enabled:
        selected_profile_extractor = profile_extractor or OpenAIResponsesProfileExtractor(selected_ai_settings)
        selected_profile_summarizer = profile_summarizer or OpenAIResponsesProfileSummarizer(selected_ai_settings)
        selected_profile_transformer = profile_transformer or OpenAIResponsesProfileTransformer(selected_ai_settings)
    selected_profile_builder_max_bytes = profile_builder_max_bytes if profile_builder_max_bytes is not None else DEFAULT_PROFILE_BUILDER_MAX_BYTES
    if selected_profile_builder_max_bytes < 1:
        raise ValueError("profile builder max bytes must be positive")

    def resolved_profile_builder_preferences(
        token: str,
    ) -> ProfileBuilderPreferences:
        preferences = store.get_profile_builder_preferences(token)
        template_id = preferences.default_template_id
        if (
            template_id != "idego-default"
            and store.get_profile_template(template_id, token) is None
        ):
            preferences = preferences.model_copy(
                update={"default_template_id": "idego-default"}
            )
            store.set_profile_builder_preferences(token, preferences)
        return preferences

    @router.post("/profile-builder/extract/cancel", status_code=202)
    def profile_builder_cancel_extraction(
        x_profile_builder_access_token: str | None = Header(default=None),
        x_profile_builder_request_id: str | None = Header(default=None),
    ) -> JSONResponse:
        token = _require_profile_builder_access_token(x_profile_builder_access_token)
        if not x_profile_builder_request_id:
            raise HTTPException(status_code=400, detail="profile_builder_request_id_required")
        extraction_cancellations.request(token, x_profile_builder_request_id)
        return JSONResponse({"status": "cancel_requested"}, status_code=202)

    @router.post("/profile-builder/extract")
    def profile_builder_extract(
        file: UploadFile = File(...),
        x_ai_enabled: bool = Header(default=True),
        x_profile_builder_access_token: str | None = Header(default=None),
        x_profile_builder_request_id: str | None = Header(default=None),
    ) -> JSONResponse:
        token = _require_profile_builder_access_token(
            x_profile_builder_access_token
        )
        try:
            return _profile_builder_extract(file, x_ai_enabled, token, x_profile_builder_request_id)
        finally:
            extraction_cancellations.discard(token, x_profile_builder_request_id)

    def _profile_builder_extract(
        file: UploadFile,
        x_ai_enabled: bool,
        token: str,
        request_id: str | None,
    ) -> JSONResponse:
        def raise_if_cancelled() -> None:
            if extraction_cancellations.is_cancelled(token, request_id):
                raise HTTPException(status_code=409, detail="profile_extraction_cancelled")

        raise_if_cancelled()
        if not x_ai_enabled:
            raise HTTPException(
                status_code=409,
                detail="profile_builder_ai_disabled_for_request",
            )
        if not selected_ai_settings.enabled or selected_profile_extractor is None:
            raise HTTPException(status_code=503, detail="profile_builder_ai_disabled")
        filename = sanitize_profile_builder_filename(
            file.filename or "candidate.pdf"
        )
        try:
            content = _read_upload_limited(
                file, selected_profile_builder_max_bytes
            )
            redacted_document = _convert_profile_cv(content, filename)
            raise_if_cancelled()
            profile = extract_candidate_profile(
                selected_ai_settings,
                selected_profile_extractor,
                redacted_document,
                recorder=usage_recorder(),
            )
            raise_if_cancelled()
            preferences = resolved_profile_builder_preferences(token)
            profile = apply_profile_conversion_preferences(profile, preferences)
            profile = materialize_custom_fields(
                profile, store.list_profile_custom_fields()
            )
            profile = sanitize_candidate_profile(profile)
            if preferences.auto_summary and selected_profile_summarizer is not None:
                try:
                    profile.summary = generate_candidate_profile_summary(
                        selected_ai_settings,
                        selected_profile_summarizer,
                        profile,
                        preferences.summary_instruction,
                        recorder=usage_recorder(),
                    )
                except ProfileSummaryError as exc:
                    safe_log(
                        "profile_builder_auto_summary_failed",
                        error_code=str(exc),
                    )
        except AnalysisStrategyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ProfileExtractionError as exc:
            safe_log(
                "profile_builder_extraction_failed",
                error_code=str(exc),
            )
            raise HTTPException(
                status_code=502,
                detail="profile_extraction_failed",
            ) from exc
        except UploadReadError as exc:
            raise HTTPException(status_code=500, detail="analysis_runtime_error") from exc
        raise_if_cancelled()
        return JSONResponse(
            {
                "filename": filename,
                "profile": profile.model_dump(mode="json"),
                "warnings": [],
            }
        )

    @router.post("/profile-builder/summary")
    def profile_builder_generate_summary(
        request: ProfileSummaryGenerationRequest,
        x_ai_enabled: bool = Header(default=True),
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        _require_profile_builder_access_token(x_profile_builder_access_token)
        if not x_ai_enabled:
            raise HTTPException(
                status_code=409,
                detail="profile_builder_ai_disabled_for_request",
            )
        if not selected_ai_settings.enabled or selected_profile_summarizer is None:
            raise HTTPException(status_code=503, detail="profile_builder_ai_disabled")
        try:
            summary = generate_candidate_profile_summary(
                selected_ai_settings,
                selected_profile_summarizer,
                sanitize_candidate_profile(request.profile),
                request.instruction,
                recorder=usage_recorder(),
            )
        except ProfileSummaryError as exc:
            safe_log("profile_builder_summary_failed", error_code=str(exc))
            raise HTTPException(
                status_code=502,
                detail="profile_summary_failed",
            ) from exc
        return JSONResponse({"summary": summary})

    @router.post("/profile-builder/transform")
    def profile_builder_transform(
        request: ProfileTransformGenerationRequest,
        x_ai_enabled: bool = Header(default=True),
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        _require_profile_builder_access_token(x_profile_builder_access_token)
        if not x_ai_enabled:
            raise HTTPException(
                status_code=409,
                detail="profile_builder_ai_disabled_for_request",
            )
        if not selected_ai_settings.enabled or selected_profile_transformer is None:
            raise HTTPException(status_code=503, detail="profile_builder_ai_disabled")
        try:
            proposal = generate_candidate_profile_transform(
                selected_ai_settings,
                selected_profile_transformer,
                sanitize_candidate_profile(request.profile),
                request.sections,
                request.instruction,
                mode=request.mode,
                target_language=request.target_language,
                recorder=usage_recorder(),
            )
        except ProfileTransformError as exc:
            safe_log("profile_builder_transform_failed", error_code=str(exc))
            raise HTTPException(status_code=502, detail="profile_transform_failed") from exc
        return JSONResponse(
            {
                "mode": request.mode,
                "sections": request.sections,
                "proposal": proposal.model_dump(mode="json"),
            }
        )

    @router.post("/profile-builder/export/docx")
    def profile_builder_export_docx(
        request: ProfileExportRequest,
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> Response:
        _require_profile_builder_access_token(x_profile_builder_access_token)
        content = render_candidate_profile_docx(
            sanitize_candidate_profile(request.profile),
            request.anonymization,
            request.template,
        )
        return Response(
            content=content,
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            headers={
                "Content-Disposition": 'attachment; filename="candidate-profile.docx"'
            },
        )

    @router.post("/profile-builder/export/pdf")
    def profile_builder_export_pdf(
        request: ProfileExportRequest,
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> Response:
        _require_profile_builder_access_token(x_profile_builder_access_token)
        try:
            content = render_candidate_profile_pdf(
                sanitize_candidate_profile(request.profile),
                request.anonymization,
                request.template,
            )
        except ProfilePdfExportError as exc:
            detail = str(exc)
            status = 503 if detail == "profile_pdf_converter_unavailable" else 500
            raise HTTPException(status_code=status, detail=detail) from exc
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="candidate-profile.pdf"'
            },
        )

    @router.get("/profile-builder/profiles")
    def profile_builder_list_profiles(
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        token = _require_profile_builder_access_token(
            x_profile_builder_access_token
        )
        return JSONResponse(
            {"profiles": store.list_candidate_profiles(token)}
        )

    @router.post("/profile-builder/profiles")
    def profile_builder_create_profile(
        snapshot: ProfileBuilderSnapshot,
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        token = _require_profile_builder_access_token(
            x_profile_builder_access_token
        )
        safe_snapshot = sanitize_profile_builder_snapshot(snapshot)
        try:
            profile_id = store.create_candidate_profile(token, safe_snapshot)
        except PersistenceError as exc:
            raise HTTPException(
                status_code=500, detail="profile_builder_persistence_failed"
            ) from exc
        return JSONResponse(
            {
                "profile_id": profile_id,
                "snapshot": safe_snapshot.model_dump(mode="json"),
            },
            status_code=201,
        )

    @router.get("/profile-builder/profiles/{profile_id}")
    def profile_builder_get_profile(
        profile_id: str,
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        token = _require_profile_builder_access_token(
            x_profile_builder_access_token
        )
        payload = store.get_candidate_profile(profile_id, token)
        if payload is None:
            raise HTTPException(status_code=404, detail="profile_not_found")
        return JSONResponse(payload)

    @router.put("/profile-builder/profiles/{profile_id}")
    def profile_builder_update_profile(
        profile_id: str,
        snapshot: ProfileBuilderSnapshot,
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        token = _require_profile_builder_access_token(
            x_profile_builder_access_token
        )
        safe_snapshot = sanitize_profile_builder_snapshot(snapshot)
        try:
            updated = store.update_candidate_profile(
                profile_id,
                token,
                safe_snapshot,
            )
        except PersistenceError as exc:
            raise HTTPException(
                status_code=500, detail="profile_builder_persistence_failed"
            ) from exc
        if not updated:
            raise HTTPException(status_code=404, detail="profile_not_found")
        return JSONResponse(
            {
                "updated": True,
                "snapshot": safe_snapshot.model_dump(mode="json"),
            }
        )

    @router.delete("/profile-builder/profiles/{profile_id}")
    def profile_builder_delete_profile(
        profile_id: str,
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        token = _require_profile_builder_access_token(
            x_profile_builder_access_token
        )
        try:
            deleted = store.delete_candidate_profile(profile_id, token)
        except PersistenceError as exc:
            raise HTTPException(
                status_code=500, detail="profile_builder_persistence_failed"
            ) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="profile_not_found")
        return JSONResponse({"deleted": True})

    @router.get("/profile-builder/custom-fields")
    def profile_builder_list_custom_fields(
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        _require_profile_builder_access_token(x_profile_builder_access_token)
        return JSONResponse(
            {
                "fields": [
                    field.model_dump(mode="json")
                    for field in store.list_profile_custom_fields()
                ]
            }
        )

    @router.put("/profile-builder/custom-fields/{field_id}")
    def profile_builder_put_custom_field(
        field_id: str,
        definition: ProfileCustomFieldDefinition,
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        _require_profile_builder_access_token(x_profile_builder_access_token)
        if definition.id != field_id:
            raise HTTPException(status_code=400, detail="custom_field_id_mismatch")
        safe_definition = sanitize_profile_custom_field_definition(definition)
        try:
            store.upsert_profile_custom_field(safe_definition)
        except PersistenceError as exc:
            raise HTTPException(
                status_code=500, detail="profile_builder_persistence_failed"
            ) from exc
        return JSONResponse(
            {"saved": True, "field": safe_definition.model_dump(mode="json")}
        )

    @router.delete("/profile-builder/custom-fields/{field_id}")
    def profile_builder_delete_custom_field(
        field_id: str,
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        _require_profile_builder_access_token(x_profile_builder_access_token)
        try:
            deleted = store.delete_profile_custom_field(field_id)
        except PersistenceError as exc:
            raise HTTPException(
                status_code=500, detail="profile_builder_persistence_failed"
            ) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="custom_field_not_found")
        return JSONResponse({"deleted": True})

    @router.get("/profile-builder/preferences")
    def profile_builder_get_preferences(
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        token = _require_profile_builder_access_token(
            x_profile_builder_access_token
        )
        return JSONResponse(
            resolved_profile_builder_preferences(token).model_dump(mode="json")
        )

    @router.put("/profile-builder/preferences")
    def profile_builder_put_preferences(
        preferences: ProfileBuilderPreferences,
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        token = _require_profile_builder_access_token(
            x_profile_builder_access_token
        )
        safe_preferences = sanitize_profile_builder_preferences(preferences)
        if (
            safe_preferences.default_template_id != "idego-default"
            and store.get_profile_template(safe_preferences.default_template_id, token) is None
        ):
            raise HTTPException(
                status_code=400, detail="default_template_not_found"
            )
        try:
            store.set_profile_builder_preferences(token, safe_preferences)
        except PersistenceError as exc:
            raise HTTPException(
                status_code=500, detail="profile_builder_persistence_failed"
            ) from exc
        return JSONResponse(
            {"saved": True, "preferences": safe_preferences.model_dump(mode="json")}
        )

    @router.get("/profile-builder/templates")
    def profile_builder_list_templates(
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        token = _require_profile_builder_access_token(
            x_profile_builder_access_token
        )
        stored = store.list_profile_templates(token)
        stored_by_id = {
            item["template"]["id"]: item
            for item in stored
            if isinstance(item.get("template"), dict)
        }
        default_item = stored_by_id.pop("idego-default", None)
        if default_item is None:
            default_template = default_profile_template().model_dump(mode="json")
            default_item = {
                "template": default_template,
                "created_at": None,
                "updated_at": None,
                "built_in": True,
                "customized": False,
            }
        else:
            default_item = {
                **default_item,
                "built_in": True,
                "customized": True,
            }
        custom_items = [
            {**item, "built_in": False, "customized": True}
            for item in stored_by_id.values()
        ]
        return JSONResponse({"templates": [default_item, *custom_items]})

    @router.get("/profile-builder/templates/{template_id}")
    def profile_builder_get_template(
        template_id: str,
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        token = _require_profile_builder_access_token(
            x_profile_builder_access_token
        )
        stored = store.get_profile_template(template_id, token)
        if stored is not None:
            return JSONResponse(
                {
                    **stored,
                    "built_in": template_id == "idego-default",
                    "customized": True,
                }
            )
        if template_id == "idego-default":
            return JSONResponse(
                {
                    "template": default_profile_template().model_dump(mode="json"),
                    "created_at": None,
                    "updated_at": None,
                    "built_in": True,
                    "customized": False,
                }
            )
        raise HTTPException(status_code=404, detail="template_not_found")

    @router.put("/profile-builder/templates/{template_id}")
    def profile_builder_put_template(
        template_id: str,
        template: ProfileTemplate,
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        if template.id != template_id:
            raise HTTPException(status_code=400, detail="template_id_mismatch")
        token = _require_profile_builder_access_token(
            x_profile_builder_access_token
        )
        safe_template = sanitize_profile_template(template)
        if safe_template.id == "idego-default":
            safe_template = safe_template.model_copy(
                update={"visibility": "shared"}
            )
        try:
            store.upsert_profile_template(token, safe_template)
        except PersistenceError as exc:
            raise HTTPException(
                status_code=500, detail="profile_builder_persistence_failed"
            ) from exc
        return JSONResponse(
            {"saved": True, "template": safe_template.model_dump(mode="json")}
        )

    @router.delete("/profile-builder/templates/{template_id}")
    def profile_builder_delete_template(
        template_id: str,
        x_profile_builder_access_token: str | None = Header(default=None),
    ) -> JSONResponse:
        token = _require_profile_builder_access_token(
            x_profile_builder_access_token
        )
        try:
            deleted = store.delete_profile_template(template_id, token)
        except PersistenceError as exc:
            raise HTTPException(
                status_code=500, detail="profile_builder_persistence_failed"
            ) from exc
        if template_id == "idego-default":
            return JSONResponse({"deleted": deleted, "reset_to_builtin": True})
        if not deleted:
            raise HTTPException(status_code=404, detail="template_not_found")
        return JSONResponse({"deleted": True})

    return router


def _convert_profile_cv(content: bytes, filename: str):
    if not content:
        raise AnalysisStrategyError("empty_upload")
    try:
        source_format = SourceFormat(Path(filename).suffix.casefold().lstrip("."))
    except ValueError:
        raise AnalysisStrategyError("unsupported_file_type") from None
    return DoclingTextConverter().convert(content, filename, source_format)


def _read_upload_limited(upload: UploadFile, max_bytes: int) -> bytes:
    try:
        content = upload.file.read(max_bytes + 1)
    except OSError as exc:
        raise UploadReadError("upload read failed") from exc
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="profile_builder_file_size_limit_exceeded")
    return content


def _require_profile_builder_access_token(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=401, detail="profile_builder_auth_required")
    return value
