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
    LinkedInDiscoveryRequest,
    LinkedInResearchInvalidResponse,
)
from cv_validator.research.subjects import (
    accepted_records,
    supported_field,
    supported_profile_field,
)

DISCOVERY_VERSION = "linkedin-discovery-v3"
COMPARISON_VERSION = "linkedin-comparison-v2"
PROMPT_VERSION = "linkedin-research-prompt-v5"
DISCOVERY_SCHEMA_VERSION = "linkedin-discovery-schema-v3"
MAX_SEARCHES = 4
DEFAULT_CONNECTION_THRESHOLD = 500
DEFAULT_MAX_PROFILES = 3
MAX_PROFILES_LIMIT = 20


class LinkedInResearcher(Protocol):
    def discover(self, request: LinkedInDiscoveryRequest) -> tuple[dict[str, Any], str, dict[str, Any]]: ...


@dataclass(frozen=True)
class LinkedInDiscoveryService:
    researcher: LinkedInResearcher
    connection_threshold: int = DEFAULT_CONNECTION_THRESHOLD
    max_profiles: int = DEFAULT_MAX_PROFILES

    def run(self, stored_report: dict[str, Any]) -> dict[str, Any]:
        request = build_discovery_request(stored_report)
        payload, response_model, usage = self.researcher.discover(request)
        if isinstance(payload, dict) and isinstance(payload.get("possible_profiles"), list):
            payload["possible_profiles"] = sorted(
                payload["possible_profiles"],
                key=lambda profile: str(profile.get("profile_url", "")) if isinstance(profile, dict) else "",
            )[: self.max_profiles]
        validate_discovery(
            payload,
            request=request,
            connection_threshold=self.connection_threshold,
            max_profiles=self.max_profiles,
        )
        return _completed(payload, DISCOVERY_VERSION, DISCOVERY_SCHEMA_VERSION, response_model, usage)


def build_discovery_request(stored_report: dict[str, Any]) -> LinkedInDiscoveryRequest:
    name = supported_profile_field(stored_report, "candidate_name")
    if name is None or not _safe_text(name, 160):
        raise ValueError("no_unambiguous_linkedin_candidate")
    candidate: dict[str, Any] = {"name": name}
    search_hints = []
    for record in accepted_records(stored_report, "employment")[:4]:
        hint: dict[str, str] = {}
        for key in ("organization", "role"):
            value = supported_field(record, key)
            if value is not None and _safe_text(value, 200):
                hint[key] = value
        if hint:
            search_hints.append(hint)
    if search_hints:
        candidate["search_hints"] = search_hints
    return LinkedInDiscoveryRequest(candidate)


def validate_discovery(
    payload: Any,
    *,
    request: LinkedInDiscoveryRequest,
    connection_threshold: int,
    max_profiles: int = DEFAULT_MAX_PROFILES,
) -> None:
    _validate_schema(payload, "linkedin-discovery.schema.json")
    profiles = payload["possible_profiles"]
    if not 1 <= max_profiles <= MAX_PROFILES_LIMIT:
        raise ValueError("linkedin_max_profiles_out_of_range")
    if len(profiles) > max_profiles:
        raise LinkedInResearchInvalidResponse("profile_limit_exceeded")
    urls = [normalize_linkedin_url(p["profile_url"]) for p in profiles]
    if len(urls) != len(set(urls)): raise LinkedInResearchInvalidResponse("duplicate_profile")
    if payload["linkedin_not_found"] != (not profiles): raise LinkedInResearchInvalidResponse("not_found_mismatch")
    if not payload["searches_performed"] or not payload["search_limitations"]: raise LinkedInResearchInvalidResponse("missing_search_context")
    if payload["linkedin_not_found"] and "does not prove" not in payload["not_found_caveat"].casefold():
        raise LinkedInResearchInvalidResponse("unsafe_not_found_caveat")
    _reject_protected_claims([payload["not_found_caveat"], *payload["search_limitations"]])
    for profile in profiles:
        if profile.get("match_evidence") or profile.get("conflicts"):
            raise LinkedInResearchInvalidResponse("comparison_not_allowed")
        if (
            not profile["source_urls"]
            or not profile["uncertainty"]
        ):
            raise LinkedInResearchInvalidResponse("missing_profile_evidence")
        if profile["photo_visible"] == "unknown" and profile["photo_source_url"] is not None: raise LinkedInResearchInvalidResponse("photo_source_mismatch")
        if profile["photo_visible"] != "unknown" and profile["photo_source_url"] is None: raise LinkedInResearchInvalidResponse("photo_source_mismatch")
        count = profile["connection_count"]
        if count["visibility"] == "unknown" and (count["minimum"] is not None or count["maximum"] is not None or count["source_url"] is not None):
            raise LinkedInResearchInvalidResponse("connection_count_mismatch")
        if count["visibility"] == "visible" and (count["source_url"] is None or count["display"] is None or count["minimum"] is None):
            raise LinkedInResearchInvalidResponse("connection_count_mismatch")
        if count["maximum"] is not None and (count["minimum"] is None or count["maximum"] < count["minimum"]): raise LinkedInResearchInvalidResponse("connection_count_range")
        expected = count["visibility"] == "visible" and count["minimum"] is not None and count["minimum"] < connection_threshold
        if profile["connection_completeness_flag"] != expected: raise LinkedInResearchInvalidResponse("connection_flag_mismatch")
        _reject_protected_claims([profile["uncertainty"]])


def normalize_linkedin_url(value: str) -> str:
    if not isinstance(value, str): raise ValueError("invalid_linkedin_profile_url")
    parts = urlsplit(value.strip())
    if parts.scheme != "https" or parts.hostname not in {"linkedin.com", "www.linkedin.com"} or not re.fullmatch(r"/in/[A-Za-z0-9_%.-]+/?", parts.path):
        raise ValueError("invalid_linkedin_profile_url")
    return urlunsplit(("https", "www.linkedin.com", parts.path.rstrip("/"), "", ""))


def _validate_schema(payload: Any, filename: str) -> None:
    schema = json.loads(files("cv_validator.research.contracts").joinpath(filename).read_text())
    if list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload)):
        raise LinkedInResearchInvalidResponse("schema")


def _completed(payload: dict[str, Any], version: str, schema: str, response_model: str, usage: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(payload)
    result.update({"status": "completed", "authority": "ai_research", "source": "openai_web_search", "accessed_at": datetime.now(timezone.utc).isoformat(),
                   "versions": {"research": version, "prompt": PROMPT_VERSION, "schema": schema},
                   "model": {"provider": "openai", "configured": "gpt-5.6-luna", "response": response_model}, "usage": deepcopy(usage)})
    return result


def _safe_text(value: str, limit: int) -> bool:
    stripped = value.strip()
    return bool(stripped) and len(stripped) <= limit and not any(ord(c) < 32 for c in stripped) and "@" not in stripped and not re.search(r"(?:https?://|www\.)|\+?\d[\d\s().-]{6,}\d", stripped, re.I)


def _reject_protected_claims(values: list[str]) -> None:
    blocked = re.compile(r"(?:definit(?:e|ely).{0,30}(?:candidate|person|identity)|photo.{0,30}(?:look|resembl|identical|same person)|appearance|fraud|decept|fake (?:person|candidate|cv)|ethnic|nationalit|race|racial|origin|gender|\bage\b|\bsex\b)", re.I)
    def authored_claim(value: str) -> str:
        return re.sub(r"(?:does not|do not|not|never|cannot|must not).{0,35}(?:fraud|decept|appearance|ethnic|nationalit|race|racial|origin|gender|age|sex|identity)", "", value, flags=re.I)
    if any(blocked.search(authored_claim(value)) for value in values): raise LinkedInResearchInvalidResponse("protected_claim")
