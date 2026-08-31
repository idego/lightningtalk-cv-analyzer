from __future__ import annotations

from copy import deepcopy
from time import perf_counter
from typing import Any, Protocol

from jsonschema import Draft202012Validator

from cv_validator.ai.config import AISettings
from cv_validator.ai.domain import (
    AIAnalysisStatus,
    AIDocumentAnalysisOutcome,
    AIFailureReason,
    AIReportComposition,
    DocumentAnalyzerResponse,
    ProfileExtractionResponse,
    ProfileSummaryResponse,
    ProfileTransformResponse,
)
from cv_validator.ai.request import (
    DocumentAnalysisRequest,
    ProfileExtractionRequest,
    ProfileSummaryRequest,
    ProfileTransformRequest,
    build_document_analysis_request,
    build_profile_extraction_request,
    build_profile_summary_request,
    build_profile_transform_request,
    load_profile_extraction_schema,
)
from cv_validator.ai.validation import (
    DocumentAnalysisValidationError,
    validate_document_analysis_response,
)
from cv_validator.domain import DeterministicAnalysisResult, Report
from cv_validator.ingestion import RedactedDocument
from cv_validator.profile_builder import (
    CandidateProfile,
    ProfessionalProfile,
    ProfessionalSectionName,
)


class DocumentAnalyzerTimeoutError(TimeoutError):
    """Safe transport timeout without request or response content."""


class DocumentAnalyzerClientError(RuntimeError):
    """Safe expected transport failure without candidate content."""

    def __init__(
        self,
        *,
        retryable: bool = False,
        http_status_class: str | None = None,
        provider_request_id: str | None = None,
    ) -> None:
        super().__init__("document analyzer client error")
        self.retryable = retryable
        self.http_status_class = http_status_class
        self.provider_request_id = provider_request_id


class DocumentAnalyzer(Protocol):
    def analyze(
        self,
        request: DocumentAnalysisRequest,
    ) -> DocumentAnalyzerResponse: ...


class ProfileExtractor(Protocol):
    def extract(
        self,
        request: ProfileExtractionRequest,
    ) -> ProfileExtractionResponse: ...


class ProfileExtractionError(RuntimeError):
    """Safe Profile Builder extraction failure without candidate content."""


class ProfileSummarizer(Protocol):
    def summarize(
        self,
        request: ProfileSummaryRequest,
    ) -> ProfileSummaryResponse: ...


class ProfileSummaryError(RuntimeError):
    """Safe Profile Builder summary failure without candidate content."""


class ProfileTransformer(Protocol):
    def transform(
        self,
        request: ProfileTransformRequest,
    ) -> ProfileTransformResponse: ...


class ProfileTransformError(RuntimeError):
    """Safe Profile Builder transform failure without candidate content."""


def analyze_report_with_ai(
    settings: AISettings,
    analyzer: DocumentAnalyzer,
    document: RedactedDocument,
    report: Report,
    report_language: str = "en",
) -> AIReportComposition:
    """Run optional AI analysis without replacing any deterministic report field."""
    if report.deterministic is None:
        raise ValueError("AI report composition requires deterministic analysis")

    outcome = run_document_analysis(
        settings,
        analyzer,
        document,
        report.deterministic,
        report_language=report_language,
    )
    return AIReportComposition(
        deterministic_report=report,
        ai_outcome=outcome,
    )


def run_document_analysis(
    settings: AISettings,
    analyzer: DocumentAnalyzer,
    document: RedactedDocument,
    deterministic: DeterministicAnalysisResult,
    report_language: str = "en",
) -> AIDocumentAnalysisOutcome:
    if not settings.enabled:
        return AIDocumentAnalysisOutcome(status=AIAnalysisStatus.DISABLED)

    request = build_document_analysis_request(
        settings,
        document,
        deterministic,
        report_language=report_language,
    )
    attempts = 0
    transport_retries = 0
    invalid_retries = 0
    usage: dict[str, Any] = {}
    started = perf_counter()
    while attempts < settings.absolute_attempt_limit:
        attempts += 1
        try:
            response = analyzer.analyze(request)
        except DocumentAnalyzerTimeoutError:
            if transport_retries < settings.transport_retry_limit and attempts < settings.absolute_attempt_limit:
                transport_retries += 1
                continue
            return _failed(
                AIFailureReason.TIMEOUT,
                usage=usage or None,
                failure_stage="transport",
                retryable=True,
                attempt_count=attempts,
                latency_ms=(perf_counter() - started) * 1000,
            )
        except DocumentAnalyzerClientError as exc:
            if exc.retryable and transport_retries < settings.transport_retry_limit and attempts < settings.absolute_attempt_limit:
                transport_retries += 1
                continue
            return _failed(
                AIFailureReason.CLIENT_ERROR,
                usage=usage or None,
                failure_stage="transport",
                retryable=exc.retryable,
                http_status_class=exc.http_status_class,
                provider_request_id=exc.provider_request_id,
                attempt_count=attempts,
                latency_ms=(perf_counter() - started) * 1000,
            )

        usage = _merge_usage(usage, response.usage)
        if response.refused or response.payload is None:
            return _failed(
                AIFailureReason.REFUSAL,
                response_model=response.response_model,
                usage=usage,
                failure_stage="provider_response",
                retryable=False,
                attempt_count=attempts,
                latency_ms=(perf_counter() - started) * 1000,
            )

        try:
            validated = validate_document_analysis_response(response.payload, document)
        except DocumentAnalysisValidationError as exc:
            stage = str(exc).rsplit(": ", 1)[-1]
            if invalid_retries < settings.invalid_response_retry_limit and attempts < settings.absolute_attempt_limit:
                invalid_retries += 1
                continue
            return _failed(
                AIFailureReason.INVALID_RESPONSE,
                response_model=response.response_model,
                usage=usage,
                failure_stage=stage,
                retryable=True,
                attempt_count=attempts,
                latency_ms=(perf_counter() - started) * 1000,
            )

        return AIDocumentAnalysisOutcome(
            status=AIAnalysisStatus.SUCCEEDED,
            analysis=validated,
            response_model=response.response_model,
            usage=usage,
            attempt_count=attempts,
            latency_ms=(perf_counter() - started) * 1000,
        )
    raise AssertionError("AI attempt loop exhausted without outcome")


def _failed(
    reason: AIFailureReason,
    *,
    response_model: str | None = None,
    usage: dict[str, Any] | None = None,
    failure_stage: str | None = None,
    retryable: bool | None = None,
    http_status_class: str | None = None,
    provider_request_id: str | None = None,
    attempt_count: int = 0,
    latency_ms: float | None = None,
) -> AIDocumentAnalysisOutcome:
    return AIDocumentAnalysisOutcome(
        status=AIAnalysisStatus.FAILED,
        failure_reason=reason,
        response_model=response_model,
        usage=None if usage is None else dict(usage),
        failure_stage=failure_stage,
        retryable=retryable,
        http_status_class=http_status_class,
        provider_request_id=provider_request_id,
        attempt_count=attempt_count,
        latency_ms=latency_ms,
    )


def _merge_usage(total: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    merged = dict(total)
    for key, value in current.items():
        if isinstance(value, (int, float)) and isinstance(merged.get(key, 0), (int, float)):
            merged[key] = merged.get(key, 0) + value
    return merged


def extract_candidate_profile(
    settings: AISettings,
    extractor: ProfileExtractor,
    document: RedactedDocument,
) -> CandidateProfile:
    if not settings.enabled:
        raise ProfileExtractionError("profile_builder_ai_disabled")
    request = build_profile_extraction_request(settings, document)
    attempts = 0
    invalid_retries = 0
    transport_retries = 0
    while attempts < settings.absolute_attempt_limit:
        attempts += 1
        try:
            response = extractor.extract(request)
        except DocumentAnalyzerTimeoutError as exc:
            if (
                transport_retries < settings.transport_retry_limit
                and attempts < settings.absolute_attempt_limit
            ):
                transport_retries += 1
                continue
            raise ProfileExtractionError("profile_extraction_timeout") from exc
        except DocumentAnalyzerClientError as exc:
            if (
                exc.retryable
                and transport_retries < settings.transport_retry_limit
                and attempts < settings.absolute_attempt_limit
            ):
                transport_retries += 1
                continue
            raise ProfileExtractionError("profile_extraction_client_error") from exc

        if response.refused or response.payload is None:
            raise ProfileExtractionError("profile_extraction_refused")
        try:
            return _materialize_candidate_profile(response.payload)
        except ProfileExtractionError:
            if (
                invalid_retries < settings.invalid_response_retry_limit
                and attempts < settings.absolute_attempt_limit
            ):
                invalid_retries += 1
                continue
            raise
    raise ProfileExtractionError("profile_extraction_failed")


def _materialize_candidate_profile(payload: Any) -> CandidateProfile:
    schema = load_profile_extraction_schema()
    if not isinstance(payload, dict) or any(
        Draft202012Validator(schema).iter_errors(payload)
    ):
        raise ProfileExtractionError("profile_extraction_invalid_response")
    materialized = deepcopy(payload)
    materialized["schema_version"] = "candidate-profile-v1"
    for key in ("skills", "technologies"):
        materialized[key] = _dedupe_profile_strings(materialized[key])
    for prefix, key in (
        ("experience", "experience"),
        ("education", "education"),
        ("language", "languages"),
        ("certification", "certifications"),
        ("additional", "additional_sections"),
    ):
        for index, item in enumerate(materialized[key], start=1):
            item["id"] = f"{prefix}-{index:03d}"
    for item in materialized["experience"]:
        for key in ("responsibilities", "achievements", "technologies"):
            item[key] = _dedupe_profile_strings(item[key])
    for item in materialized["additional_sections"]:
        item["items"] = _dedupe_profile_strings(item["items"])
    try:
        return CandidateProfile.model_validate(materialized)
    except Exception as exc:
        raise ProfileExtractionError(
            "profile_extraction_materialization_failed"
        ) from exc


def _dedupe_profile_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        value = raw.strip()
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def generate_candidate_profile_summary(
    settings: AISettings,
    summarizer: ProfileSummarizer,
    profile: CandidateProfile,
    instruction: str | None = None,
) -> str:
    if not settings.enabled:
        raise ProfileSummaryError("profile_builder_ai_disabled")
    request = build_profile_summary_request(settings, profile, instruction)
    attempts = 0
    transport_retries = 0
    while attempts < settings.absolute_attempt_limit:
        attempts += 1
        try:
            response = summarizer.summarize(request)
        except DocumentAnalyzerTimeoutError as exc:
            if (
                transport_retries < settings.transport_retry_limit
                and attempts < settings.absolute_attempt_limit
            ):
                transport_retries += 1
                continue
            raise ProfileSummaryError("profile_summary_timeout") from exc
        except DocumentAnalyzerClientError as exc:
            if (
                exc.retryable
                and transport_retries < settings.transport_retry_limit
                and attempts < settings.absolute_attempt_limit
            ):
                transport_retries += 1
                continue
            raise ProfileSummaryError("profile_summary_client_error") from exc

        if response.refused or response.summary is None:
            raise ProfileSummaryError("profile_summary_refused")
        summary = response.summary.strip()
        if not summary or len(summary) > 3_000:
            raise ProfileSummaryError("profile_summary_invalid_response")
        return summary
    raise ProfileSummaryError("profile_summary_failed")


def generate_candidate_profile_transform(
    settings: AISettings,
    transformer: ProfileTransformer,
    profile: CandidateProfile,
    sections: list[ProfessionalSectionName],
    instruction: str,
    *,
    mode: str,
    target_language: str | None = None,
) -> ProfessionalProfile:
    if not settings.enabled:
        raise ProfileTransformError("profile_builder_ai_disabled")
    request = build_profile_transform_request(
        settings,
        profile,
        sections,
        instruction,
        mode=mode,
        target_language=target_language,
    )
    attempts = 0
    transport_retries = 0
    invalid_retries = 0
    while attempts < settings.absolute_attempt_limit:
        attempts += 1
        try:
            response = transformer.transform(request)
        except DocumentAnalyzerTimeoutError as exc:
            if transport_retries < settings.transport_retry_limit and attempts < settings.absolute_attempt_limit:
                transport_retries += 1
                continue
            raise ProfileTransformError("profile_transform_timeout") from exc
        except DocumentAnalyzerClientError as exc:
            if exc.retryable and transport_retries < settings.transport_retry_limit and attempts < settings.absolute_attempt_limit:
                transport_retries += 1
                continue
            raise ProfileTransformError("profile_transform_client_error") from exc
        if response.refused or response.payload is None:
            raise ProfileTransformError("profile_transform_refused")
        original = ProfessionalProfile(
            headline=profile.headline, summary=profile.summary, skills=profile.skills,
            technologies=profile.technologies, experience=profile.experience, education=profile.education,
            languages=profile.languages, certifications=profile.certifications,
            additional_sections=profile.additional_sections,
        )
        selected = set(sections)
        if not isinstance(response.payload, dict) or set(response.payload) != selected:
            if invalid_retries < settings.invalid_response_retry_limit and attempts < settings.absolute_attempt_limit:
                invalid_retries += 1
                continue
            raise ProfileTransformError("profile_transform_invalid_response")
        try:
            merged = original.model_dump(mode="json")
            merged.update(response.payload)
            proposed = ProfessionalProfile.model_validate(merged)
        except Exception as exc:
            if invalid_retries < settings.invalid_response_retry_limit and attempts < settings.absolute_attempt_limit:
                invalid_retries += 1
                continue
            raise ProfileTransformError("profile_transform_invalid_response") from exc

        for field_name in ("experience", "education", "languages", "certifications", "additional_sections"):
            if field_name not in selected:
                continue
            original_ids = [item.id for item in getattr(original, field_name)]
            proposed_ids = [item.id for item in getattr(proposed, field_name)]
            if proposed_ids != original_ids:
                raise ProfileTransformError("profile_transform_modified_entry_structure")

        if mode == "translation":
            if proposed.technologies != original.technologies:
                raise ProfileTransformError("profile_translation_modified_technologies")
            for before, after in zip(original.experience, proposed.experience):
                if (
                    after.company != before.company
                    or after.company_category != before.company_category
                    or after.project != before.project
                    or after.location != before.location
                    or after.start_date != before.start_date
                    or after.end_date != before.end_date
                    or after.current != before.current
                    or after.technologies != before.technologies
                ):
                    raise ProfileTransformError("profile_translation_modified_protected_fact")
            for before, after in zip(original.education, proposed.education):
                if (
                    after.institution != before.institution
                    or after.location != before.location
                    or after.start_date != before.start_date
                    or after.end_date != before.end_date
                ):
                    raise ProfileTransformError("profile_translation_modified_protected_fact")
            for before, after in zip(original.certifications, proposed.certifications):
                if (after.issuer, after.date, after.url) != (before.issuer, before.date, before.url):
                    raise ProfileTransformError("profile_translation_modified_protected_fact")
        return proposed
    raise ProfileTransformError("profile_transform_failed")
