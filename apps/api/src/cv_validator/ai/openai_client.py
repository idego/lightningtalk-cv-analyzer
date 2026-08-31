from __future__ import annotations

import json
import re
from typing import Any, Protocol

import openai

from cv_validator.ai.application import (
    DocumentAnalyzerClientError,
    DocumentAnalyzerTimeoutError,
)
from cv_validator.ai.config import AISettings
from cv_validator.ai.domain import (
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
)


class _ResponsesAPI(Protocol):
    def create(self, **payload: Any) -> Any: ...


class _OpenAIClient(Protocol):
    responses: _ResponsesAPI


class _StructuredRequest(Protocol):
    def to_openai_payload(self) -> dict[str, Any]: ...


class OpenAIResponsesDocumentAnalyzer:
    """Production Responses API adapter with safe, content-free failures."""

    def __init__(
        self,
        settings: AISettings,
        *,
        client: _OpenAIClient | None = None,
    ) -> None:
        if not settings.enabled or settings.api_key is None:
            raise ValueError("enabled AI settings are required")
        self._client = client or openai.OpenAI(
            api_key=settings.api_key,
            timeout=settings.timeout_seconds,
            max_retries=settings.max_retries,
        )

    def analyze(
        self,
        request: DocumentAnalysisRequest,
    ) -> DocumentAnalyzerResponse:
        payload, response_model, usage, refused = _create_json_response(
            self._client,
            request,
        )
        return DocumentAnalyzerResponse(
            payload=payload,
            response_model=response_model,
            usage=usage,
            refused=refused,
        )


def _create_json_response(
    client: _OpenAIClient,
    request: _StructuredRequest,
) -> tuple[Any | None, str, dict[str, Any], bool]:
    try:
        response = client.responses.create(**request.to_openai_payload())
    except openai.APITimeoutError as exc:
        raise DocumentAnalyzerTimeoutError() from exc
    except openai.APIStatusError as exc:
        status = exc.status_code
        raise DocumentAnalyzerClientError(
            retryable=status == 429 or status >= 500,
            http_status_class=f"{status // 100}xx",
            provider_request_id=_safe_request_id(
                exc.response.headers.get("x-request-id")
            ),
        ) from exc
    except openai.APIConnectionError as exc:
        raise DocumentAnalyzerClientError(retryable=True) from exc
    except openai.APIError as exc:
        raise DocumentAnalyzerClientError(retryable=False) from exc

    usage = response.usage.model_dump() if response.usage is not None else {}
    if _contains_refusal(response):
        return None, response.model, usage, True
    try:
        payload = json.loads(response.output_text)
    except (TypeError, json.JSONDecodeError):
        # Never retain model text in safe validation/transport failures.
        payload = "invalid_json"
    return payload, response.model, usage, False


def _contains_refusal(response: Any) -> bool:
    return any(
        getattr(content, "type", None) == "refusal"
        for output in getattr(response, "output", ())
        for content in getattr(output, "content", ())
    )


def _safe_request_id(value: str | None) -> str | None:
    if value is None or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value):
        return None
    return value


class OpenAIResponsesProfileExtractor:
    """Structured Profile Builder extraction using the existing Responses client."""

    def __init__(
        self,
        settings: AISettings,
        *,
        client: _OpenAIClient | None = None,
    ) -> None:
        if not settings.enabled or settings.api_key is None:
            raise ValueError("enabled AI settings are required")
        self._client = client or openai.OpenAI(
            api_key=settings.api_key,
            timeout=settings.timeout_seconds,
            max_retries=settings.max_retries,
        )

    def extract(
        self,
        request: ProfileExtractionRequest,
    ) -> ProfileExtractionResponse:
        payload, response_model, usage, refused = _create_json_response(
            self._client,
            request,
        )
        return ProfileExtractionResponse(
            payload=payload,
            response_model=response_model,
            usage=usage,
            refused=refused,
        )


class OpenAIResponsesProfileSummarizer:
    """Short, non-reasoning Profile Builder summary generation."""

    def __init__(
        self,
        settings: AISettings,
        *,
        client: _OpenAIClient | None = None,
    ) -> None:
        if not settings.enabled or settings.api_key is None:
            raise ValueError("enabled AI settings are required")
        self._client = client or openai.OpenAI(
            api_key=settings.api_key,
            timeout=settings.timeout_seconds,
            max_retries=settings.max_retries,
        )

    def summarize(self, request: ProfileSummaryRequest) -> ProfileSummaryResponse:
        try:
            response = self._client.responses.create(**request.to_openai_payload())
        except openai.APITimeoutError as exc:
            raise DocumentAnalyzerTimeoutError() from exc
        except openai.APIStatusError as exc:
            status = exc.status_code
            raise DocumentAnalyzerClientError(
                retryable=status == 429 or status >= 500,
                http_status_class=f"{status // 100}xx",
                provider_request_id=_safe_request_id(
                    exc.response.headers.get("x-request-id")
                ),
            ) from exc
        except openai.APIConnectionError as exc:
            raise DocumentAnalyzerClientError(retryable=True) from exc
        except openai.APIError as exc:
            raise DocumentAnalyzerClientError(retryable=False) from exc

        usage = response.usage.model_dump() if response.usage is not None else {}
        if _contains_refusal(response):
            return ProfileSummaryResponse(
                summary=None,
                response_model=response.model,
                usage=usage,
                refused=True,
            )
        summary = response.output_text.strip() if isinstance(response.output_text, str) else ""
        return ProfileSummaryResponse(
            summary=summary or None,
            response_model=response.model,
            usage=usage,
        )


class OpenAIResponsesProfileTransformer:
    """Source-faithful professional profile rewrites and translations."""

    def __init__(self, settings: AISettings, *, client: _OpenAIClient | None = None) -> None:
        if not settings.enabled or settings.api_key is None:
            raise ValueError("enabled AI settings are required")
        self._client = client or openai.OpenAI(
            api_key=settings.api_key,
            timeout=settings.timeout_seconds,
            max_retries=settings.max_retries,
        )

    def transform(self, request: ProfileTransformRequest) -> ProfileTransformResponse:
        payload, response_model, usage, refused = _create_json_response(self._client, request)
        return ProfileTransformResponse(
            payload=payload,
            response_model=response_model,
            usage=usage,
            refused=refused,
        )
