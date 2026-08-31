from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from cv_validator.ai.config import AISettings
from cv_validator.domain import DeterministicAnalysisResult
from cv_validator.ingestion import RedactedDocument, SourcePage


PROMPT_VERSION = "2710"
SCHEMA_VERSION = "document-analysis-schema-v9"
LEGACY_SCHEMA_VERSION = "document-analysis-schema-v7"
INPUT_CONTRACT_VERSION = "document-analysis-input-v4"
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
    report_language: str

    def to_openai_payload(self) -> dict[str, Any]:
        return deepcopy(self.openai_payload)


def build_document_analysis_request(
    settings: AISettings,
    document: RedactedDocument,
    deterministic: DeterministicAnalysisResult,
    report_language: str = "en",
    *,
    exclusion_intervals: tuple[tuple[str, int, int], ...] = (),
    understanding_context: dict[str, Any] | None = None,
) -> DocumentAnalysisRequest:
    if not isinstance(document, RedactedDocument):
        raise TypeError("Document Analyzer requires a RedactedDocument")

    if report_language not in {"en", "pl"}:
        raise ValueError("unsupported report language")
    prompt = _contract_text("prompt.md")
    schema = load_document_analysis_schema()
    observations = {
        "contract_version": DETERMINISTIC_OBSERVATIONS_VERSION,
        "deterministic_ruleset_version": deterministic.ruleset_version,
        "observations": deterministic.to_dict()["observations"],
    }
    input_text = format_document_analysis_input(
        format_visible_line_referenced_markdown(document.pages, exclusion_intervals),
        observations,
        report_language=report_language,
        understanding_context=understanding_context,
    )
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
        report_language=report_language,
    )


def format_document_analysis_input(
    page_markdown: str,
    deterministic_observations: dict[str, Any],
    report_language: str = "en",
    understanding_context: dict[str, Any] | None = None,
) -> str:
    observations_json = json.dumps(
        deterministic_observations,
        ensure_ascii=False,
        sort_keys=True,
    )
    context = json.dumps(_bounded_understanding_context(understanding_context), ensure_ascii=False, sort_keys=True)
    return (
        "<report_language>\n"
        f"{report_language}\n"
        "</report_language>\n\n"
        "<deterministic_observations>\n"
        f"{observations_json}\n"
        "</deterministic_observations>\n\n"
        "<code_owned_understanding>\n"
        f"{context}\n"
        "</code_owned_understanding>\n\n"
        "<redacted_cv_markdown>\n"
        f"{page_markdown}\n"
        "</redacted_cv_markdown>"
    )


def format_line_referenced_markdown(pages: tuple[SourcePage, ...]) -> str:
    return format_visible_line_referenced_markdown(pages, ())


def format_visible_line_referenced_markdown(pages: tuple[SourcePage, ...], intervals: tuple[tuple[str, int, int], ...]) -> str:
    rendered_pages: list[str] = []
    for page in pages:
        rendered_lines = [f"<!-- page: {page.page_id} -->"]
        for line in page.lines:
            text = list(line.text)
            for page_id, start, end in intervals:
                if page_id != page.page_id or start >= line.end_offset or end <= line.start_offset:
                    continue
                left = max(start, line.start_offset) - line.start_offset
                right = min(end, line.end_offset) - line.start_offset
                text[left:right] = "█" * (right - left)
            rendered_lines.extend(
                (f"<!-- line: {line.line_id} -->", "".join(text))
            )
        rendered_pages.append("\n".join(rendered_lines))
    return "\n\n".join(rendered_pages)


def _bounded_understanding_context(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"status": "unavailable"}
    sections = [{key: item.get(key) for key in ("id", "kind", "confidence")} for item in value.get("sections", [])[:32] if isinstance(item, dict)]
    records = []
    missing_fields = []
    for item in value.get("records", [])[:100]:
        if not isinstance(item, dict): continue
        fields = [{key: field.get(key) for key in ("name", "status", "value", "authority", "confidence")} for field in item.get("fields", [])[:8] if isinstance(field, dict)]
        records.append({"id": item.get("id"), "kind": item.get("kind"), "section_id": item.get("section_id"), "fields": fields})
        missing_fields.extend(
            {"record_id": item.get("id"), "kind": item.get("kind"), "field": field.get("name"), "status": field.get("status")}
            for field in fields
            if field.get("status") != "supported" or field.get("value") is None
        )
    ambiguous = [{"id": item.get("id"), "category": item.get("category"), "reason_code": item.get("reason_code")} for item in value.get("ambiguous_spans", [])[:100] if isinstance(item, dict)]
    return {
        "status": value.get("status"),
        "review_mode": "independent_full_document_second_pass",
        "authority": "code_owned_fields_are_immutable",
        "priorities": ["unknown_fields", "ambiguous_spans", "missing_records", "code_ai_conflicts"],
        "sections": sections,
        "records": records,
        "missing_fields": missing_fields[:200],
        "ambiguous_spans": ambiguous,
    }


def load_document_analysis_schema() -> dict[str, Any]:
    return json.loads(_contract_text("document-analysis.schema.v9.json"))


def load_legacy_document_analysis_schema() -> dict[str, Any]:
    """Load the v7 contract only to keep already persisted/test payloads readable."""
    return json.loads(_contract_text("document-analysis.schema.json"))


def _contract_text(name: str) -> str:
    return (
        files("cv_validator.ai.contracts")
        .joinpath(name)
        .read_text(encoding="utf-8")
    )
