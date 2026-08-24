from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.resources import files
from typing import Any, Protocol

from jsonschema import Draft202012Validator, FormatChecker

from cv_validator.research.domain import EducationResearchInvalidResponse, EducationResearchRequest

RESEARCH_VERSION = "education-research-v1"
PROMPT_VERSION = "education-research-prompt-v1"
SCHEMA_VERSION = "education-research-schema-v1"
MAX_CREDENTIALS = 12


class EducationResearcher(Protocol):
    def research(self, request: EducationResearchRequest) -> tuple[dict[str, Any], str, dict[str, Any]]: ...


@dataclass(frozen=True)
class EducationResearchService:
    researcher: EducationResearcher

    def run(self, stored_report: dict[str, Any]) -> dict[str, Any]:
        request = build_education_research_request(stored_report)
        payload, response_model, usage = self.researcher.research(request)
        validate_education_research(payload, request=request)
        result = deepcopy(payload)
        result.update({
            "status": "completed", "authority": "ai_research", "source": "openai_web_search",
            "accessed_at": datetime.now(timezone.utc).isoformat(),
            "versions": {"research": RESEARCH_VERSION, "prompt": PROMPT_VERSION, "schema": SCHEMA_VERSION},
            "model": {"provider": "openai", "configured": "gpt-5.6-luna", "response": response_model},
            "usage": deepcopy(usage),
        })
        return result


def build_education_research_request(stored_report: dict[str, Any]) -> EducationResearchRequest:
    ai = stored_report.get("ai_analysis") or {}
    candidates = ai.get("research_candidates") or []
    education = ai.get("facts", {}).get("education", [])
    allowed = {
        candidate.get("query_subject", "").strip().casefold(): candidate.get("query_subject", "").strip()
        for candidate in candidates
        if candidate.get("category") == "education_or_certification"
        and isinstance(candidate.get("query_subject"), str)
        and _safe_subject(candidate["query_subject"])
    }
    facts: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in education:
        if not isinstance(item, dict):
            continue
        institution = item.get("institution")
        program = item.get("program")
        if not isinstance(institution, str) or not _safe_subject(institution):
            continue
        matching_subjects = {institution.strip().casefold()}
        if isinstance(program, str) and _safe_subject(program):
            matching_subjects.add(program.strip().casefold())
        if not (matching_subjects & set(allowed)):
            continue
        key = (institution.strip().casefold(), program.strip().casefold() if isinstance(program, str) else "")
        if key in seen:
            continue
        seen.add(key)
        fact: dict[str, Any] = {"institution": institution.strip()}
        if isinstance(program, str) and program.strip():
            fact["program"] = program.strip()[:200]
        # CV dates and evidence are never inputs to reusable public research.
        facts.append(fact)
        if len(facts) == MAX_CREDENTIALS:
            break
    matched = {_key(fact) for fact in facts}
    for normalized, subject in allowed.items():
        if any(normalized in key for key in matched):
            continue
        facts.append({"certificate": subject})
        if len(facts) == MAX_CREDENTIALS:
            break
    if not facts:
        raise ValueError("no_education_research_candidates")
    return EducationResearchRequest(tuple(facts))


def validate_education_research(payload: Any, *, request: EducationResearchRequest) -> None:
    schema = json.loads(files("cv_validator.research.contracts").joinpath("education-research.schema.json").read_text())
    if list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload)):
        raise EducationResearchInvalidResponse()
    expected = {_key(item) for item in request.input_facts}
    returned = {_key(item) for item in payload["credentials"]}
    if returned != expected or len(returned) != len(payload["credentials"]):
        raise EducationResearchInvalidResponse()
    for credential in payload["credentials"]:
        kinds = {finding["kind"] for finding in credential["findings"]}
        required: set[str] = set()
        for field, kind in (("institution_exists", "institution"), ("program_exists", "program"), ("degree_exists", "degree"), ("certificate_exists", "certificate")):
            if credential[field] != "evidence_unavailable": required.add(kind)
        if credential["dates"] is not None: required.add("dates")
        if credential["accreditation_status"] == "established": required.add("accreditation")
        if credential["city"] is not None or credential["country"] is not None: required.add("location")
        if credential["cv_consistency"] != "evidence_unavailable": required.add("cv_consistency")
        if not required.issubset(kinds):
            raise EducationResearchInvalidResponse()
        if credential["cv_consistency"] == "mismatch" and not credential["location_difference_for_review"]:
            raise EducationResearchInvalidResponse()


def _key(item: dict[str, Any]) -> tuple[str, str, str]:
    return tuple(str(item.get(field) or "").strip().casefold() for field in ("institution", "program", "certificate"))


def _safe_subject(value: str) -> bool:
    stripped = value.strip()
    if not stripped or len(stripped) > 200 or any(ord(char) < 32 for char in stripped):
        return False
    if "@" in stripped or re.search(r"(?:https?://|www\.)|\+?\d[\d\s().-]{6,}\d", stripped, re.I):
        return False
    return len(re.findall(r"[^\W\d_]", stripped, re.UNICODE)) >= 2
