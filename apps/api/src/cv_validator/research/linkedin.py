from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.resources import files
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

from jsonschema import Draft202012Validator, FormatChecker

from cv_validator.research.domain import (
    LinkedInComparisonRequest,
    LinkedInDiscoveryRequest,
    LinkedInResearchInvalidResponse,
)

DISCOVERY_VERSION = "linkedin-discovery-v1"
COMPARISON_VERSION = "linkedin-comparison-v1"
PROMPT_VERSION = "linkedin-research-prompt-v1"
DISCOVERY_SCHEMA_VERSION = "linkedin-discovery-schema-v1"
COMPARISON_SCHEMA_VERSION = "linkedin-comparison-schema-v1"
MAX_SEARCHES = 4
DEFAULT_CONNECTION_THRESHOLD = 500


class LinkedInResearcher(Protocol):
    def discover(self, request: LinkedInDiscoveryRequest) -> tuple[dict[str, Any], str, dict[str, Any]]: ...
    def compare(self, request: LinkedInComparisonRequest) -> tuple[dict[str, Any], str, dict[str, Any]]: ...


@dataclass(frozen=True)
class LinkedInDiscoveryService:
    researcher: LinkedInResearcher
    connection_threshold: int = DEFAULT_CONNECTION_THRESHOLD

    def run(self, stored_report: dict[str, Any]) -> dict[str, Any]:
        request = build_discovery_request(stored_report)
        payload, response_model, usage = self.researcher.discover(request)
        validate_discovery(payload, request=request, connection_threshold=self.connection_threshold)
        return _completed(payload, DISCOVERY_VERSION, DISCOVERY_SCHEMA_VERSION, response_model, usage)


@dataclass(frozen=True)
class LinkedInComparisonService:
    researcher: LinkedInResearcher

    def run(self, stored_report: dict[str, Any], profile_url: str) -> dict[str, Any]:
        request = build_comparison_request(stored_report, profile_url)
        payload, response_model, usage = self.researcher.compare(request)
        validate_comparison(payload, request=request)
        return _completed(payload, COMPARISON_VERSION, COMPARISON_SCHEMA_VERSION, response_model, usage)


def build_discovery_request(stored_report: dict[str, Any]) -> LinkedInDiscoveryRequest:
    ai = stored_report.get("ai_analysis") or {}
    names = [c.get("query_subject", "").strip() for c in ai.get("research_candidates") or []
             if c.get("category") == "linkedin" and isinstance(c.get("query_subject"), str)]
    names = [name for name in names if _safe_text(name, 160)]
    if len({name.casefold() for name in names}) != 1:
        raise ValueError("no_unambiguous_linkedin_candidate")
    candidate: dict[str, Any] = {"name": names[0]}
    employment = []
    for item in (ai.get("facts") or {}).get("employment", [])[:4]:
        if not isinstance(item, dict): continue
        fact = {key: item[key].strip() for key in ("organization", "role", "location")
                if isinstance(item.get(key), str) and _safe_text(item[key], 200)}
        if isinstance(item.get("employment_dates"), str) and _safe_date_text(item["employment_dates"]): fact["employment_dates"] = item["employment_dates"].strip()
        if fact: employment.append(fact)
    education = []
    for item in (ai.get("facts") or {}).get("education", [])[:3]:
        if not isinstance(item, dict): continue
        fact = {target: item[source].strip() for source, target in (("institution", "institution"), ("program", "program"))
                if isinstance(item.get(source), str) and _safe_text(item[source], 200)}
        if isinstance(item.get("study_dates"), str) and _safe_date_text(item["study_dates"]): fact["dates"] = item["study_dates"].strip()
        if fact: education.append(fact)
    locations = [x.get("value") for x in (ai.get("facts") or {}).get("contact", [])
                 if isinstance(x, dict) and x.get("kind") == "stated_location" and isinstance(x.get("value"), str) and _safe_text(x["value"], 160)]
    if employment: candidate["employment"] = employment
    if education: candidate["education"] = education
    if locations: candidate["stated_location"] = locations[0].strip()
    return LinkedInDiscoveryRequest(candidate)


def build_comparison_request(stored_report: dict[str, Any], profile_url: str) -> LinkedInComparisonRequest:
    normalized = normalize_linkedin_url(profile_url)
    discovery = stored_report.get("linkedin_discovery") or {}
    urls = {normalize_linkedin_url(p["profile_url"]) for p in discovery.get("possible_profiles", []) if isinstance(p, dict)}
    if normalized not in urls:
        raise ValueError("profile_not_in_discovery")
    return LinkedInComparisonRequest(build_discovery_request(stored_report).candidate, normalized)


def validate_discovery(payload: Any, *, request: LinkedInDiscoveryRequest, connection_threshold: int) -> None:
    _validate_schema(payload, "linkedin-discovery.schema.json")
    profiles = payload["possible_profiles"]
    urls = [normalize_linkedin_url(p["profile_url"]) for p in profiles]
    if len(urls) != len(set(urls)): raise LinkedInResearchInvalidResponse()
    if payload["linkedin_not_found"] != (not profiles): raise LinkedInResearchInvalidResponse()
    if not payload["searches_performed"] or not payload["search_limitations"]: raise LinkedInResearchInvalidResponse()
    if payload["linkedin_not_found"] and "does not prove" not in payload["not_found_caveat"].casefold():
        raise LinkedInResearchInvalidResponse()
    _reject_protected_claims([payload["not_found_caveat"], *payload["search_limitations"]])
    for profile in profiles:
        if not profile["match_evidence"] or not profile["source_urls"] or not profile["uncertainty"]:
            raise LinkedInResearchInvalidResponse()
        if profile["photo_visible"] == "unknown" and profile["photo_source_url"] is not None: raise LinkedInResearchInvalidResponse()
        if profile["photo_visible"] != "unknown" and profile["photo_source_url"] is None: raise LinkedInResearchInvalidResponse()
        count = profile["connection_count"]
        if count["visibility"] == "unknown" and (count["minimum"] is not None or count["maximum"] is not None or count["source_url"] is not None):
            raise LinkedInResearchInvalidResponse()
        if count["visibility"] == "visible" and (count["source_url"] is None or count["display"] is None or count["minimum"] is None):
            raise LinkedInResearchInvalidResponse()
        if count["maximum"] is not None and (count["minimum"] is None or count["maximum"] < count["minimum"]): raise LinkedInResearchInvalidResponse()
        expected = count["visibility"] == "visible" and count["minimum"] is not None and count["minimum"] < connection_threshold
        if profile["connection_completeness_flag"] != expected: raise LinkedInResearchInvalidResponse()
        _reject_protected_claims([profile["uncertainty"], *(x["summary"] for x in profile["conflicts"])])


def validate_comparison(payload: Any, *, request: LinkedInComparisonRequest) -> None:
    _validate_schema(payload, "linkedin-comparison.schema.json")
    if normalize_linkedin_url(payload["profile_url"]) != request.profile_url: raise LinkedInResearchInvalidResponse()
    if {item["field"] for item in payload["comparisons"]} != {"companies", "roles", "dates", "stated_location", "education"} or len(payload["comparisons"]) != 5:
        raise LinkedInResearchInvalidResponse()
    for comparison in payload["comparisons"]:
        if not comparison["source_urls"] or not comparison["uncertainty"]:
            raise LinkedInResearchInvalidResponse()
        _reject_protected_claims([comparison["summary"], comparison["uncertainty"]])
    _reject_protected_claims(payload["limitations"])


def normalize_linkedin_url(value: str) -> str:
    if not isinstance(value, str): raise ValueError("invalid_linkedin_profile_url")
    parts = urlsplit(value.strip())
    if parts.scheme != "https" or parts.hostname not in {"linkedin.com", "www.linkedin.com"} or not re.fullmatch(r"/in/[A-Za-z0-9_%.-]+/?", parts.path):
        raise ValueError("invalid_linkedin_profile_url")
    return urlunsplit(("https", "www.linkedin.com", parts.path.rstrip("/"), "", ""))


def _validate_schema(payload: Any, filename: str) -> None:
    schema = json.loads(files("cv_validator.research.contracts").joinpath(filename).read_text())
    if list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload)):
        raise LinkedInResearchInvalidResponse()


def _completed(payload: dict[str, Any], version: str, schema: str, response_model: str, usage: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(payload)
    result.update({"status": "completed", "authority": "ai_research", "source": "openai_web_search", "accessed_at": datetime.now(timezone.utc).isoformat(),
                   "versions": {"research": version, "prompt": PROMPT_VERSION, "schema": schema},
                   "model": {"provider": "openai", "configured": "gpt-5.6-luna", "response": response_model}, "usage": deepcopy(usage)})
    return result


def _safe_text(value: str, limit: int) -> bool:
    stripped = value.strip()
    return bool(stripped) and len(stripped) <= limit and not any(ord(c) < 32 for c in stripped) and "@" not in stripped and not re.search(r"(?:https?://|www\.)|\+?\d[\d\s().-]{6,}\d", stripped, re.I)


def _safe_date_text(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and len(stripped) <= 100 and not any(ord(c) < 32 for c in stripped) and "@" not in stripped and not re.search(r"(?:https?://|www\.)", stripped, re.I)


def _reject_protected_claims(values: list[str]) -> None:
    blocked = re.compile(r"(?:definit(?:e|ely).{0,30}(?:candidate|person|identity)|photo.{0,30}(?:look|resembl|identical|same person)|appearance|fraud|decept|fake (?:person|candidate|cv)|ethnic|nationalit|race|racial|origin|gender|\bage\b|\bsex\b)", re.I)
    def authored_claim(value: str) -> str:
        return re.sub(r"(?:does not|do not|not|never|cannot|must not).{0,35}(?:fraud|decept|appearance|ethnic|nationalit|race|racial|origin|gender|age|sex|identity)", "", value, flags=re.I)
    if any(blocked.search(authored_claim(value)) for value in values): raise LinkedInResearchInvalidResponse()
