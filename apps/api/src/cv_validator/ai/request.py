from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from cv_validator.ai.config import AISettings
from cv_validator.domain import DeterministicAnalysisResult
from cv_validator.ingestion import RedactedDocument, SourcePage
from cv_validator.profile_builder import (
    CandidateProfile,
    ProfessionalProfile,
    ProfessionalSectionName,
    professional_profile_from_candidate,
)


PROMPT_VERSION = "2708"
SCHEMA_VERSION = "document-analysis-schema-v9"
LEGACY_SCHEMA_VERSION = "document-analysis-schema-v7"
INPUT_CONTRACT_VERSION = "document-analysis-input-v3"
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


@dataclass(frozen=True)
class ProfileExtractionRequest:
    openai_payload: dict[str, Any]
    page_ids: tuple[str, ...]
    prompt_version: str
    schema_version: str
    input_contract_version: str
    timeout_seconds: float
    max_retries: int

    def to_openai_payload(self) -> dict[str, Any]:
        return deepcopy(self.openai_payload)


@dataclass(frozen=True)
class ProfileSummaryRequest:
    openai_payload: dict[str, Any]
    prompt_version: str
    timeout_seconds: float
    max_retries: int

    def to_openai_payload(self) -> dict[str, Any]:
        return deepcopy(self.openai_payload)


@dataclass(frozen=True)
class ProfileTransformRequest:
    openai_payload: dict[str, Any]
    prompt_version: str
    timeout_seconds: float
    max_retries: int

    def to_openai_payload(self) -> dict[str, Any]:
        return deepcopy(self.openai_payload)


def build_document_analysis_request(
    settings: AISettings,
    document: RedactedDocument,
    deterministic: DeterministicAnalysisResult,
    report_language: str = "en",
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
        format_line_referenced_markdown(document.pages),
        observations,
        report_language=report_language,
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
) -> str:
    observations_json = json.dumps(
        deterministic_observations,
        ensure_ascii=False,
        sort_keys=True,
    )
    return (
        "<report_language>\n"
        f"{report_language}\n"
        "</report_language>\n\n"
        "<deterministic_observations>\n"
        f"{observations_json}\n"
        "</deterministic_observations>\n\n"
        "<redacted_cv_markdown>\n"
        f"{page_markdown}\n"
        "</redacted_cv_markdown>"
    )


def format_line_referenced_markdown(pages: tuple[SourcePage, ...]) -> str:
    rendered_pages: list[str] = []
    for page in pages:
        rendered_lines = [f"<!-- page: {page.page_id} -->"]
        for line in page.lines:
            rendered_lines.extend(
                (f"<!-- line: {line.line_id} -->", line.text)
            )
        rendered_pages.append("\n".join(rendered_lines))
    return "\n\n".join(rendered_pages)


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


PROFILE_BUILDER_PROMPT_VERSION = "profile-builder-extraction-v1"
PROFILE_BUILDER_SCHEMA_VERSION = "candidate-profile-extraction-v1"


def build_profile_extraction_request(
    settings: AISettings,
    document: RedactedDocument,
) -> ProfileExtractionRequest:
    if not isinstance(document, RedactedDocument):
        raise TypeError("Profile Builder extraction requires a RedactedDocument")
    schema = load_profile_extraction_schema()
    input_text = (
        "<redacted_cv_markdown>\n"
        f"{format_line_referenced_markdown(document.pages)}\n"
        "</redacted_cv_markdown>"
    )
    payload: dict[str, Any] = {
        "model": settings.model,
        "reasoning": {"effort": settings.reasoning_effort},
        "instructions": _contract_text("profile-builder-prompt.md"),
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": input_text}],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "candidate_profile_extraction",
                "strict": True,
                "schema": schema,
            }
        },
        "tools": [],
        "store": settings.store,
        "max_output_tokens": settings.max_output_tokens,
    }
    return ProfileExtractionRequest(
        openai_payload=payload,
        page_ids=tuple(page.page_id for page in document.pages),
        prompt_version=PROFILE_BUILDER_PROMPT_VERSION,
        schema_version=PROFILE_BUILDER_SCHEMA_VERSION,
        input_contract_version="profile-builder-input-v1",
        timeout_seconds=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )


def load_profile_extraction_schema() -> dict[str, Any]:
    return json.loads(_contract_text("profile-builder.schema.json"))


PROFILE_SUMMARY_PROMPT_VERSION = "profile-builder-summary-v1"
PROFILE_SUMMARY_MAX_OUTPUT_TOKENS = 384


def build_profile_summary_request(
    settings: AISettings,
    profile: CandidateProfile,
    instruction: str | None = None,
) -> ProfileSummaryRequest:
    professional_profile = profile.model_dump(mode="json")
    professional_profile.pop("personal", None)
    professional_profile.pop("summary", None)
    professional_profile.pop("custom_fields", None)
    instruction_text = (instruction or "").strip()
    input_text = (
        "<candidate_profile>\n"
        f"{json.dumps(professional_profile, ensure_ascii=False, sort_keys=True)}\n"
        "</candidate_profile>\n\n"
        "<recruiter_instruction>\n"
        f"{instruction_text or 'Write a concise recruiter-facing professional summary of the candidate.'}\n"
        "</recruiter_instruction>"
    )
    payload: dict[str, Any] = {
        "model": settings.model,
        "reasoning": {"effort": "none"},
        "instructions": (
            "Write only the candidate summary. Use only facts supported by "
            "<candidate_profile>. Treat <recruiter_instruction> as guidance about "
            "focus, style, job requirements, or output language, never as a source of "
            "candidate facts. Do not invent experience, skills, seniority, results, or "
            "credentials. Keep the result concise: normally 2-4 sentences and no more "
            "than 120 words. Do not add a heading, bullets, markdown, or commentary."
        ),
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": input_text}],
            }
        ],
        "tools": [],
        "store": settings.store,
        "max_output_tokens": min(
            settings.max_output_tokens, PROFILE_SUMMARY_MAX_OUTPUT_TOKENS
        ),
    }
    return ProfileSummaryRequest(
        openai_payload=payload,
        prompt_version=PROFILE_SUMMARY_PROMPT_VERSION,
        timeout_seconds=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )


PROFILE_TRANSFORM_PROMPT_VERSION = "profile-builder-transform-v1"


def build_profile_transform_request(
    settings: AISettings,
    profile: CandidateProfile,
    sections: list[ProfessionalSectionName],
    instruction: str,
    *,
    mode: str,
    target_language: str | None = None,
) -> ProfileTransformRequest:
    professional = professional_profile_from_candidate(profile)
    if mode == "translation":
        task = (
            f"Translate the selected sections to {target_language}. Preserve names, company names, "
            "institution names, URLs, technology/product identifiers, dates and factual meaning. "
            "Do not add, remove, merge, or reinterpret facts."
        )
    else:
        task = (
            "Apply the recruiter instruction only to the selected sections. Improve wording, focus, "
            "or structure as requested, but never invent candidate facts, metrics, seniority, skills, "
            "credentials, employers, dates, or achievements."
        )
    input_text = (
        "<selected_sections>\n" + json.dumps(sections) + "\n</selected_sections>\n\n"
        "<instruction>\n" + instruction.strip() + "\n</instruction>\n\n"
        "<professional_profile>\n" + professional.model_dump_json() + "\n</professional_profile>"
    )
    schema = ProfessionalProfile.model_json_schema()
    root_properties = schema.get("properties", {})
    schema["properties"] = {section: root_properties[section] for section in sections}
    schema["required"] = list(sections)
    schema = _openai_strict_schema(schema)
    payload: dict[str, Any] = {
        "model": settings.model,
        "reasoning": {"effort": "none"},
        "instructions": (
            task + " Return exactly the selected top-level sections and no others. Preserve stable "
            "entry IDs for repeated sections. Return JSON only through the supplied schema."
        ),
        "input": [{"role": "user", "content": [{"type": "input_text", "text": input_text}]}],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "candidate_professional_profile",
                "strict": True,
                "schema": schema,
            }
        },
        "tools": [],
        "store": settings.store,
        "max_output_tokens": settings.max_output_tokens,
    }
    return ProfileTransformRequest(
        openai_payload=payload,
        prompt_version=PROFILE_TRANSFORM_PROMPT_VERSION,
        timeout_seconds=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )


def _openai_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Make a Pydantic object schema compatible with Responses strict JSON schema."""
    result = deepcopy(schema)

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            node.pop("default", None)
            properties = node.get("properties")
            if isinstance(properties, dict):
                node["required"] = list(properties.keys())
                node["additionalProperties"] = False
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(result)
    return result
