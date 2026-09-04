from __future__ import annotations

import hashlib
import json
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from cv_validator.openai_config import PINNED_OPENAI_MODEL
from cv_validator.research.company import PROMPT_VERSION as COMPANY_PROMPT_VERSION
from cv_validator.research.company import RESEARCH_VERSION as COMPANY_RESEARCH_VERSION
from cv_validator.research.company import SCHEMA_VERSION as COMPANY_SCHEMA_VERSION
from cv_validator.research.domain import CompanyResearchRequest, EducationResearchRequest
from cv_validator.research.education import PROMPT_VERSION as EDUCATION_PROMPT_VERSION
from cv_validator.research.education import RESEARCH_VERSION as EDUCATION_RESEARCH_VERSION
from cv_validator.research.education import SCHEMA_VERSION as EDUCATION_SCHEMA_VERSION

CACHE_FORMAT_VERSION = "public-research-per-subject-cache-v3"
MODEL_VERSION = PINNED_OPENAI_MODEL
SEARCH_POLICY_VERSION = "openai-web-search-low-max4-v1"
CacheCategory = Literal["company", "education"]
_RESULT_KEYS: dict[CacheCategory, str] = {
    "company": "organizations",
    "education": "credentials",
}


@dataclass(frozen=True)
class CacheDescriptor:
    cache_key: str
    category: CacheCategory
    normalized_subjects: tuple[str, ...]
    research_version: str
    prompt_version: str
    schema_version: str
    model_version: str = MODEL_VERSION
    search_policy_version: str = SEARCH_POLICY_VERSION
    cache_format_version: str = CACHE_FORMAT_VERSION


def company_cache_descriptor(request: CompanyResearchRequest) -> CacheDescriptor:
    subjects = tuple(sorted(_normalize(fact["organization"]) for fact in request.input_facts))
    return _descriptor("company", subjects, COMPANY_RESEARCH_VERSION, COMPANY_PROMPT_VERSION, COMPANY_SCHEMA_VERSION)


def company_subject_descriptors(request: CompanyResearchRequest) -> tuple[CacheDescriptor, ...]:
    return tuple(
        _descriptor(
            "company",
            (_normalize(fact["organization"]),),
            COMPANY_RESEARCH_VERSION,
            COMPANY_PROMPT_VERSION,
            COMPANY_SCHEMA_VERSION,
        )
        for fact in request.input_facts
    )


def education_cache_descriptor(request: EducationResearchRequest) -> CacheDescriptor:
    subjects = tuple(sorted(
        _education_subject(fact) for fact in request.input_facts
    ))
    return _descriptor("education", subjects, EDUCATION_RESEARCH_VERSION, EDUCATION_PROMPT_VERSION, EDUCATION_SCHEMA_VERSION)


def education_subject_descriptors(request: EducationResearchRequest) -> tuple[CacheDescriptor, ...]:
    return tuple(
        _descriptor(
            "education",
            (_education_subject(fact),),
            EDUCATION_RESEARCH_VERSION,
            EDUCATION_PROMPT_VERSION,
            EDUCATION_SCHEMA_VERSION,
        )
        for fact in request.input_facts
    )


def single_subject_result(category: CacheCategory, result: dict[str, Any], index: int) -> dict[str, Any]:
    key = _RESULT_KEYS[category]
    count = len(result.get(key, []))
    if count < 1 or not 0 <= index < count:
        raise ValueError("research_subject_index_out_of_range")
    single = deepcopy(result)
    single[key] = [deepcopy(result[key][index])]
    single["usage"] = _split_usage(result.get("usage", {}), index, count)
    return single


def merge_subject_results(
    category: CacheCategory,
    results: list[dict[str, Any]],
    descriptors: tuple[CacheDescriptor, ...],
) -> dict[str, Any]:
    if not results or len(results) != len(descriptors):
        raise ValueError("research_subject_merge_incomplete")
    key = _RESULT_KEYS[category]
    statuses = [result.get("cache", {}).get("status", "miss") for result in results]
    combined = deepcopy(results[0])
    combined[key] = [deepcopy(result[key][0]) for result in results]
    combined["searches_performed"] = list(dict.fromkeys(
        query for result in results for query in result.get("searches_performed", [])
    ))
    combined["search_limitations"] = list(dict.fromkeys(
        limit for result in results for limit in result.get("search_limitations", [])
    ))
    combined["usage"] = {
        token: sum(
            value
            for result in results
            for key_name, value in result.get("usage", {}).items()
            if key_name == token and isinstance(value, int)
        )
        for token in ("input_tokens", "output_tokens", "total_tokens")
    }
    combined["usage"]["cached"] = all(status == "hit" for status in statuses)
    aggregate_status = (
        "hit" if all(status == "hit" for status in statuses)
        else "miss" if all(status == "miss" for status in statuses)
        else "partial_hit"
    )
    combined["cache"] = {
        "status": aggregate_status,
        "format_version": CACHE_FORMAT_VERSION,
        "subjects": [
            {
                "normalized_subject": descriptor.normalized_subjects[0],
                "status": status,
                "accessed_at": result.get("accessed_at"),
                "saved_usage": deepcopy(result.get("cache", {}).get("saved_usage", {})),
            }
            for descriptor, status, result in zip(descriptors, statuses, results, strict=True)
        ],
    }
    return combined


def reusable_payload(category: CacheCategory, result: dict[str, Any]) -> dict[str, Any]:
    common = {
        "schema_version": result["schema_version"],
        "outcome": result["outcome"],
        "searches_performed": [],
        "search_limitations": [],
        "accessed_at": result["accessed_at"],
        "source": result["source"],
        "source_usage": deepcopy(result.get("usage", {})),
    }
    common.update(_REUSABLE_PAYLOAD_BUILDERS[category](result))
    return common


def _company_reusable_payload(result: dict[str, Any]) -> dict[str, Any]:
    organizations: list[dict[str, Any]] = []
    for item in result["organizations"]:
        cached = {
            key: deepcopy(item[key])
            for key in (
                "query_subject", "existence", "activity", "operating_periods",
                "offices", "official_website", "company_pages", "registries",
                "confidence", "uncertainty", "findings",
                "limited_online_presence", "limited_online_presence_reason",
            )
        }
        cached["findings"] = [
            finding
            for finding in cached["findings"]
            if finding["kind"] != "relationship"
        ]
        cached["relationship"] = None
        organizations.append(cached)
    return {"organizations": organizations}


def _education_reusable_payload(result: dict[str, Any]) -> dict[str, Any]:
    credentials: list[dict[str, Any]] = []
    for item in result["credentials"]:
        public_findings = [
            deepcopy(finding)
            for finding in item["findings"]
            if finding["kind"] not in {"dates", "cv_consistency"}
        ]
        cached = {
            key: deepcopy(item[key])
            for key in (
                "institution", "program", "certificate", "degree",
                "program_exists", "degree_exists", "certificate_exists",
                "city", "country", "confidence", "uncertainty",
            )
        }
        cached.update(
            {
                "dates": None,
                "cv_consistency": "evidence_unavailable",
                "location_difference_for_review": None,
                "findings": public_findings,
            }
        )
        credentials.append(cached)
    return {"credentials": credentials}


_REUSABLE_PAYLOAD_BUILDERS = {
    "company": _company_reusable_payload,
    "education": _education_reusable_payload,
}


def materialize_cache_hit(category: CacheCategory, payload: dict[str, Any], *, descriptor: CacheDescriptor) -> dict[str, Any]:
    result = deepcopy(payload)
    saved_usage = result.pop("source_usage", {})
    result.update({
        "status": "completed", "authority": "ai_research", "source": "openai_web_search_cache",
        "versions": {"research": descriptor.research_version, "prompt": descriptor.prompt_version, "schema": descriptor.schema_version},
        "model": {"provider": "openai", "configured": descriptor.model_version, "response": descriptor.model_version},
        "usage": {"input_tokens": 0, "output_tokens": 0, "cached": True},
        "cache": {
            "status": "hit",
            "format_version": descriptor.cache_format_version,
            "saved_usage": saved_usage,
        },
    })
    return result


def _descriptor(category: CacheCategory, subjects: tuple[str, ...], research: str, prompt: str, schema: str) -> CacheDescriptor:
    material = {"cache_format": CACHE_FORMAT_VERSION, "category": category, "subjects": subjects, "research": research,
                "prompt": prompt, "schema": schema, "model": MODEL_VERSION, "search_policy": SEARCH_POLICY_VERSION}
    key = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return CacheDescriptor(key, category, subjects, research, prompt, schema)


def _education_subject(fact: dict[str, Any]) -> str:
    parts = [
        _normalize(str(fact.get(field) or ""))
        for field in ("institution", "program", "certificate")
    ]
    return json.dumps(parts, ensure_ascii=False, separators=(",", ":"))


def _split_usage(usage: Any, index: int, count: int) -> dict[str, Any]:
    if not isinstance(usage, dict) or count < 1:
        return {}
    split: dict[str, Any] = {}
    for name, value in usage.items():
        if isinstance(value, bool):
            split[name] = value
        elif isinstance(value, int):
            base, remainder = divmod(value, count)
            split[name] = base + (1 if index < remainder else 0)
        else:
            split[name] = deepcopy(value)
    if isinstance(split.get("input_tokens"), int) and isinstance(split.get("output_tokens"), int):
        split["total_tokens"] = split["input_tokens"] + split["output_tokens"]
    return split


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())
