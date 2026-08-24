from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from cv_validator.ai.config import AISettings
from cv_validator.domain import DeterministicAnalysisResult
from cv_validator.ingestion import RedactedDocument


PROMPT_VERSION = "2108"
SCHEMA_VERSION = "document-analysis-schema-v3"
INPUT_CONTRACT_VERSION = "document-analysis-input-v1"
DETERMINISTIC_OBSERVATIONS_VERSION = "deterministic-observations-v1"


@dataclass(frozen=True)
class DocumentAnalysisRequest:
    openai_payload: dict[str, Any]
    page_ids: tuple[str, ...]
    prompt_version: str
    schema_version: str
    input_contract_version: str
    deterministic_observations_version: str
    timeout_seconds: float
    max_retries: int

    def to_openai_payload(self) -> dict[str, Any]:
        return deepcopy(self.openai_payload)


def build_document_analysis_request(
    settings: AISettings,
    document: RedactedDocument,
    deterministic: DeterministicAnalysisResult,
) -> DocumentAnalysisRequest:
    if not isinstance(document, RedactedDocument):
        raise TypeError("Document Analyzer requires a RedactedDocument")

    prompt = _contract_text("prompt.md")
    schema = json.loads(_contract_text("document-analysis.schema.json"))
    observations = {
        "contract_version": DETERMINISTIC_OBSERVATIONS_VERSION,
        "deterministic_ruleset_version": deterministic.ruleset_version,
        "observations": deterministic.to_dict()["observations"],
    }
    input_text = format_document_analysis_input(document.markdown, observations)
    payload: dict[str, Any] = {
        "model": settings.model,
        "reasoning": {"effort": settings.reasoning_effort},
        "instructions": prompt,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": input_text}],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "document_analysis",
                "strict": True,
                "schema": schema,
            }
        },
        "tools": [],
        "store": settings.store,
        "max_output_tokens": settings.max_output_tokens,
    }
    return DocumentAnalysisRequest(
        openai_payload=payload,
        page_ids=tuple(page.page_id for page in document.pages),
        prompt_version=PROMPT_VERSION,
        schema_version=SCHEMA_VERSION,
        input_contract_version=INPUT_CONTRACT_VERSION,
        deterministic_observations_version=DETERMINISTIC_OBSERVATIONS_VERSION,
        timeout_seconds=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )


def format_document_analysis_input(
    page_markdown: str,
    deterministic_observations: dict[str, Any],
) -> str:
    observations_json = json.dumps(
        deterministic_observations,
        ensure_ascii=False,
        sort_keys=True,
    )
    return (
        "<deterministic_observations>\n"
        f"{observations_json}\n"
        "</deterministic_observations>\n\n"
        "<redacted_cv_markdown>\n"
        f"{page_markdown}\n"
        "</redacted_cv_markdown>"
    )


def load_document_analysis_schema() -> dict[str, Any]:
    return json.loads(_contract_text("document-analysis.schema.json"))


def _contract_text(name: str) -> str:
    return (
        files("cv_validator.ai.contracts")
        .joinpath(name)
        .read_text(encoding="utf-8")
    )
