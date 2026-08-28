from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.resources import files
from typing import Any, Protocol

from jsonschema import Draft202012Validator, FormatChecker

from cv_validator.research.domain import (
    CompanyResearchInvalidResponse,
    CompanyResearchRequest,
)

RESEARCH_VERSION = "company-research-v1"
PROMPT_VERSION = "company-research-prompt-v2"
SCHEMA_VERSION = "company-research-schema-v1"
MAX_ORGANIZATIONS = 12


class CompanyResearcher(Protocol):
    def research(self, request: CompanyResearchRequest) -> tuple[dict[str, Any], str, dict[str, Any]]: ...


@dataclass(frozen=True)
class CompanyResearchService:
    researcher: CompanyResearcher

    def run(self, stored_report: dict[str, Any]) -> dict[str, Any]:
        request = build_company_research_request(stored_report)
        payload, response_model, usage = self.researcher.research(request)
        validate_company_research(payload, request=request)
        result = deepcopy(payload)
        result.update({
            "status": "completed",
            "authority": "ai_research",
            "source": "openai_web_search",
            "accessed_at": datetime.now(timezone.utc).isoformat(),
            "versions": {"research": RESEARCH_VERSION, "prompt": PROMPT_VERSION, "schema": SCHEMA_VERSION},
            "model": {"provider": "openai", "configured": "gpt-5.6-luna", "response": response_model},
            "usage": deepcopy(usage),
        })
        return result


def build_company_research_request(stored_report: dict[str, Any]) -> CompanyResearchRequest:
    ai = stored_report.get("ai_analysis") or {}
    candidates = ai.get("research_candidates") or []
    employment = ai.get("facts", {}).get("employment", [])
    facts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.get("category") != "company":
            continue
        subject = candidate.get("query_subject")
        if not isinstance(subject, str) or not _safe_organization_subject(subject):
            continue
        normalized = subject.strip().casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        match = next((item for item in employment if isinstance(item, dict) and str(item.get("organization", "")).strip().casefold() == normalized), None)
        if match is None:
            continue
        # Reusable public-web research receives only the public organization
        # subject. Candidate dates, locations and relations stay owner-scoped.
        facts.append({"organization": subject.strip()})
        if len(facts) == MAX_ORGANIZATIONS:
            break
    if not facts:
        raise ValueError("no_company_research_candidates")
    return CompanyResearchRequest(tuple(facts))


def validate_company_research(payload: Any, *, request: CompanyResearchRequest) -> None:
    schema = json.loads(files("cv_validator.research.contracts").joinpath("company-research.schema.json").read_text())
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload))
    if errors:
        raise CompanyResearchInvalidResponse()
    expected = {fact["organization"].strip().casefold() for fact in request.input_facts}
    returned = {item["query_subject"].strip().casefold() for item in payload["organizations"]}
    if returned != expected or len(returned) != len(payload["organizations"]):
        raise CompanyResearchInvalidResponse()
    for organization in payload["organizations"]:
        claims_public_facts = organization["existence"] != "insufficient_evidence" or any(
            organization[key] is not None
            for key in ("activity", "operating_dates", "location", "official_website")
        ) or bool(organization["company_pages"] or organization["registries"])
        if claims_public_facts and not organization["findings"]:
            raise CompanyResearchInvalidResponse()
        if organization["limited_online_presence"]:
            reason = organization["limited_online_presence_reason"]
            if (
                organization["existence"] != "insufficient_evidence"
                or not isinstance(reason, str)
                or "does not establish existence or absence" not in reason.casefold()
                or not payload["searches_performed"]
                or not payload["search_limitations"]
            ):
                raise CompanyResearchInvalidResponse()


def _safe_organization_subject(value: str) -> bool:
    stripped = value.strip()
    if not stripped or len(stripped) > 200 or any(ord(char) < 32 for char in stripped):
        return False
    if "@" in stripped or re.search(r"(?:https?://|www\.)", stripped, re.IGNORECASE):
        return False
    if re.search(r"\+?\d[\d\s().-]{6,}\d", stripped):
        return False
    normalized = re.sub(r"[^a-z]+", " ", stripped.casefold()).strip()
    if normalized in {"self employed", "self employment", "freelance", "freelancer"}:
        return False
    return len(re.findall(r"[^\W\d_]", stripped, re.UNICODE)) >= 2
