from __future__ import annotations

import json
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
        except openai.APIError as exc:
            raise DocumentAnalyzerClientError() from exc

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
        if not response.output_text:
            raise DocumentAnalyzerClientError()
        try:
            payload = json.loads(response.output_text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise DocumentAnalyzerClientError() from exc
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
