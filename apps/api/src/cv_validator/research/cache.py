from __future__ import annotations

import hashlib
import json
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from cv_validator.research.company import PROMPT_VERSION as COMPANY_PROMPT_VERSION
from cv_validator.research.company import RESEARCH_VERSION as COMPANY_RESEARCH_VERSION
from cv_validator.research.company import SCHEMA_VERSION as COMPANY_SCHEMA_VERSION
from cv_validator.research.domain import CompanyResearchRequest, EducationResearchRequest
from cv_validator.research.education import PROMPT_VERSION as EDUCATION_PROMPT_VERSION
from cv_validator.research.education import RESEARCH_VERSION as EDUCATION_RESEARCH_VERSION
from cv_validator.research.education import SCHEMA_VERSION as EDUCATION_SCHEMA_VERSION

CACHE_FORMAT_VERSION = "public-research-cache-v1"
MODEL_VERSION = "gpt-5.6-luna"
SEARCH_POLICY_VERSION = "openai-web-search-low-max4-v1"
CacheCategory = Literal["company", "education"]


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


def education_cache_descriptor(request: EducationResearchRequest) -> CacheDescriptor:
    subjects = tuple(sorted(
        "|".join(_normalize(str(fact.get(field) or "")) for field in ("institution", "program", "certificate"))
        for fact in request.input_facts
    ))
    return _descriptor("education", subjects, EDUCATION_RESEARCH_VERSION, EDUCATION_PROMPT_VERSION, EDUCATION_SCHEMA_VERSION)


def reusable_payload(category: CacheCategory, result: dict[str, Any]) -> dict[str, Any]:
    common = {
        "schema_version": result["schema_version"],
        "outcome": result["outcome"],
        "searches_performed": deepcopy(result["searches_performed"]),
        "search_limitations": deepcopy(result["search_limitations"]),
        "accessed_at": result["accessed_at"],
        "source": result["source"],
    }
    if category == "company":
        common["organizations"] = []
        for item in result["organizations"]:
            cached = {key: deepcopy(item[key]) for key in (
                "query_subject", "existence", "activity", "operating_dates", "location",
                "official_website", "company_pages", "registries", "confidence", "uncertainty",
                "findings", "limited_online_presence", "limited_online_presence_reason",
            )}
            cached["findings"] = [finding for finding in cached["findings"] if finding["kind"] != "relationship"]
            cached["relationship"] = None
            common["organizations"].append(cached)
    else:
        common["credentials"] = []
        for item in result["credentials"]:
            public_findings = [deepcopy(finding) for finding in item["findings"] if finding["kind"] not in {"dates", "cv_consistency"}]
            cached = {key: deepcopy(item[key]) for key in (
                "institution", "program", "degree", "certificate", "institution_exists",
                "program_exists", "degree_exists", "certificate_exists", "accreditation_status",
                "city", "country", "confidence", "uncertainty",
            )}
            cached.update({"dates": None, "cv_consistency": "evidence_unavailable", "location_difference_for_review": None, "findings": public_findings})
            common["credentials"].append(cached)
    return common


def materialize_cache_hit(category: CacheCategory, payload: dict[str, Any], *, descriptor: CacheDescriptor) -> dict[str, Any]:
    result = deepcopy(payload)
    result.update({
        "status": "completed", "authority": "ai_research", "source": "openai_web_search_cache",
        "versions": {"research": descriptor.research_version, "prompt": descriptor.prompt_version, "schema": descriptor.schema_version},
        "model": {"provider": "openai", "configured": descriptor.model_version, "response": descriptor.model_version},
        "usage": {"input_tokens": 0, "output_tokens": 0, "cached": True},
        "cache": {"status": "hit", "format_version": descriptor.cache_format_version},
    })
    return result


def _descriptor(category: CacheCategory, subjects: tuple[str, ...], research: str, prompt: str, schema: str) -> CacheDescriptor:
    material = {"cache_format": CACHE_FORMAT_VERSION, "category": category, "subjects": subjects, "research": research,
                "prompt": prompt, "schema": schema, "model": MODEL_VERSION, "search_policy": SEARCH_POLICY_VERSION}
    key = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return CacheDescriptor(key, category, subjects, research, prompt, schema)


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())
