from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import openai

from cv_validator.analysis.source import SourceDocument
from cv_validator.openai_config import PINNED_OPENAI_MODEL


SPECIALIST_REASONING_EFFORT = "none"
REVIEWER_REASONING_EFFORT = "low"


class ModelPassError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ModelPassResponse:
    payload: dict[str, Any]
    model: str
    usage: dict[str, Any]


class LunaAnalysisClient(Protocol):
    def run(
        self,
        pass_name: str,
        source: SourceDocument,
        context: dict[str, Any] | None = None,
    ) -> ModelPassResponse: ...


class OpenAIResponsesLunaClient:
    def __init__(
        self,
        *,
        client=None,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._client = client or openai.OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )

    def run(
        self,
        pass_name: str,
        source: SourceDocument,
        context: dict[str, Any] | None = None,
    ) -> ModelPassResponse:
        schema = PASS_SCHEMAS[pass_name]
        effort = REVIEWER_REASONING_EFFORT if pass_name == "review" else SPECIALIST_REASONING_EFFORT
        payload: dict[str, Any] = {"source_blocks": source.as_prompt_payload()}
        if context is not None:
            payload["candidate_context"] = context
        try:
            response = self._client.responses.create(
                model=PINNED_OPENAI_MODEL,
                reasoning={"effort": effort},
                instructions=PROMPTS[pass_name],
                input=json.dumps(payload, ensure_ascii=False),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": f"cv_{pass_name}",
                        "strict": True,
                        "schema": schema,
                    }
                },
                store=False,
                max_output_tokens={
                    "profile": 2200,
                    "employment": 3200,
                    "education": 2600,
                    "review": 3600,
                }[pass_name],
            )
        except openai.APITimeoutError as exc:
            raise ModelPassError("timeout") from exc
        except openai.APIError as exc:
            raise ModelPassError("client_error") from exc
        try:
            parsed = json.loads(response.output_text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ModelPassError("invalid_json") from exc
        if not isinstance(parsed, dict):
            raise ModelPassError("invalid_schema")
        usage = response.usage.model_dump() if response.usage is not None else {}
        return ModelPassResponse(parsed, response.model, usage)


def _field_schema() -> dict[str, Any]:
    return {
        "type": ["object", "null"],
        "properties": {
            "id": {"type": "string", "minLength": 1, "maxLength": 256},
            "value": {"type": "string", "minLength": 1, "maxLength": 4000},
            "evidence": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": {
                    "type": "object",
                    "properties": {
                        "block_id": {"type": "string"},
                        "excerpt": {"type": "string", "minLength": 1, "maxLength": 4000},
                    },
                    "required": ["block_id", "excerpt"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["id", "value", "evidence"],
        "additionalProperties": False,
    }


def _record_schema(fields: tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "id": {"type": "string", "minLength": 1, "maxLength": 256},
            **{name: _field_schema() for name in fields},
        },
        "required": ["id", *fields],
        "additionalProperties": False,
    }


def _candidate_body_schema(fields: tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {name: _field_schema() for name in fields},
        "required": list(fields),
        "additionalProperties": False,
    }


_employment_fields = ("organization", "role", "start_date", "end_date", "location", "relationship_type")
_education_fields = ("institution", "program", "degree", "certificate", "start_date", "end_date", "location")

PASS_SCHEMAS: dict[str, dict[str, Any]] = {
    "profile": {
        "type": "object",
        "properties": {
            "profile": {
                "type": "object",
                "properties": {
                    **{name: _field_schema() for name in ("candidate_name", "declared_location", "headline", "summary")},
                    "skills": {"type": "array", "maxItems": 200, "items": _field_schema()},
                    "languages": {"type": "array", "maxItems": 100, "items": _field_schema()},
                },
                "required": ["candidate_name", "declared_location", "headline", "summary", "skills", "languages"],
                "additionalProperties": False,
            }
        },
        "required": ["profile"],
        "additionalProperties": False,
    },
    "employment": {
        "type": "object",
        "properties": {"records": {"type": "array", "maxItems": 100, "items": _record_schema(_employment_fields)}},
        "required": ["records"],
        "additionalProperties": False,
    },
    "education": {
        "type": "object",
        "properties": {"records": {"type": "array", "maxItems": 100, "items": _record_schema(_education_fields)}},
        "required": ["records"],
        "additionalProperties": False,
    },
    "review": {
        "type": "object",
        "properties": {
            "accepted_record_ids": {"type": "array", "maxItems": 300, "items": {"type": "string"}},
            "rejected_records": {
                "type": "array", "maxItems": 300,
                "items": {"type": "object", "properties": {"id": {"type": "string"}, "reason_code": {"type": "string"}}, "required": ["id", "reason_code"], "additionalProperties": False},
            },
            "merge_groups": {"type": "array", "maxItems": 300, "items": {"type": "array", "minItems": 2, "items": {"type": "string"}}},
            "relation_patches": {
                "type": "array", "maxItems": 300,
                "items": {"type": "object", "properties": {"record_id": {"type": "string"}, "field_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["record_id", "field_ids"], "additionalProperties": False},
            },
            "added_profile_fields": {
                "type": "array", "maxItems": 20,
                "items": {
                    "type": "object",
                    "properties": {
                        "field_name": {"enum": ["candidate_name", "declared_location", "headline", "summary", "skills", "languages"]},
                        "field": _field_schema(),
                    },
                    "required": ["field_name", "field"],
                    "additionalProperties": False,
                },
            },
            "added_candidates": {
                "type": "array", "maxItems": 100,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "candidate_type": {"enum": ["employment", "education"]},
                        "reason_code": {"type": "string"},
                        "candidate": {"anyOf": [_candidate_body_schema(_employment_fields), _candidate_body_schema(_education_fields)]},
                    },
                    "required": ["id", "candidate_type", "reason_code", "candidate"],
                    "additionalProperties": False,
                },
            },
            "conflicts": {
                "type": "array", "maxItems": 300,
                "items": {
                    "type": "object",
                    "properties": {
                        "reason_code": {"type": "string"},
                        "record_ids": {"type": "array", "items": {"type": "string"}},
                        "field_ids": {"type": "array", "items": {"type": "string"}},
                        "source_block_ids": {"type": "array", "items": {"type": "string"}},
                        "summary": {"type": ["string", "null"]},
                    },
                    "required": ["reason_code", "record_ids", "field_ids", "source_block_ids", "summary"],
                    "additionalProperties": False,
                },
            },
            "coverage_gaps": {
                "type": "array", "maxItems": 100,
                "items": {
                    "type": "object",
                    "properties": {
                        "target": {"enum": ["profile", "employment", "education"]},
                        "reason_code": {"type": "string"},
                        "source_block_ids": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["target", "reason_code", "source_block_ids"],
                    "additionalProperties": False,
                },
            },
            "status": {"enum": ["completed", "partial"]},
        },
        "required": ["accepted_record_ids", "rejected_records", "merge_groups", "relation_patches", "added_profile_fields", "added_candidates", "conflicts", "coverage_gaps", "status"],
        "additionalProperties": False,
    },
}


PROMPTS = {
    "profile": """Extract only literal candidate profile facts from the supplied source blocks. Every non-null value must cite an exact excerpt and its block ID; never infer a value from layout, common practice, a filename, or another field. Keep missing or ambiguous values null. Do not extract contact details, employment, education, identity claims, demographic traits, residence, nationality, or work eligibility. Use concise literal values rather than summaries that add interpretation.""",
    "employment": """Extract employment relationships only. Require positive source evidence that each named organization is an employer, client, or project counterparty; technologies, skills, products, headings, and customers mentioned without a work relationship are not employers. Keep fields from different entries separate, preserve uncertainty by leaving unsupported fields null, and cite exact literal excerpts for every value. Do not infer dates, locations, seniority, employment status, candidate identity, or truthfulness.""",
    "education": """Extract education and certification records only. Keep a supported institution or certificate even when optional program, degree, dates, or location are absent. Never infer accreditation, completion, equivalence, institution identity, or candidate qualification. Keep separate entries separate, leave ambiguous fields null, and cite exact literal excerpts and block IDs for every non-null value.""",
    "review": """Adjudicate candidates by stable IDs after all specialists and mechanical detectors. Accept only records whose fields and relationships are supported by the cited source blocks. Reject technologies mistaken for employers, headings mistaken for facts, duplicates, and fields grouped across separate entries. Actively find material omissions, but add a candidate only when exact block evidence supports both its values and relationship; otherwise emit a concise coverage gap. Summaries must describe uncertainty without accusation or verification claims. Never write the final recruiter report, invent facts, assign confidence, or alter mechanical facts.""",
}
