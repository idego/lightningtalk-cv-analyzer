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
from cv_validator.ai.domain import DocumentAnalyzerResponse
from cv_validator.ai.request import DocumentAnalysisRequest


class _ResponsesAPI(Protocol):
    def create(self, **payload: Any) -> Any: ...


class _OpenAIClient(Protocol):
    responses: _ResponsesAPI


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
        try:
            response = self._client.responses.create(
                **request.to_openai_payload()
            )
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

        usage = (
            response.usage.model_dump()
            if response.usage is not None
            else {}
        )
        if _contains_refusal(response):
            return DocumentAnalyzerResponse(
                payload=None,
                response_model=response.model,
                usage=usage,
                refused=True,
            )
        try:
            payload = json.loads(response.output_text)
        except (TypeError, json.JSONDecodeError):
            # Preserve only the fact that validation must reject the response;
            # never put output text in an exception or diagnostic.
            payload = "invalid_json"
        return DocumentAnalyzerResponse(
            payload=payload,
            response_model=response.model,
            usage=usage,
        )


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
