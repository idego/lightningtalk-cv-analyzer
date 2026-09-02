from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.resources import files
from typing import Any, Protocol

from jsonschema import Draft202012Validator, FormatChecker

from cv_validator.location import Ambiguous, LocationResolver, Resolved, ResolutionLevel
from cv_validator.research.domain import EducationResearchInvalidResponse, EducationResearchRequest
from cv_validator.research.subjects import accepted_records, supported_field

RESEARCH_VERSION = "education-research-v3"
PROMPT_VERSION = "education-research-prompt-v4"
SCHEMA_VERSION = "education-research-schema-v2"
MAX_CREDENTIALS = 12


class EducationResearcher(Protocol):
    def research(self, request: EducationResearchRequest) -> tuple[dict[str, Any], str, dict[str, Any]]: ...


@dataclass(frozen=True)
class EducationResearchService:
    researcher: EducationResearcher

    def run(
        self,
        stored_report: dict[str, Any],
        *,
        request: EducationResearchRequest | None = None,
    ) -> dict[str, Any]:
        request = request or build_education_research_request(stored_report)
        payload, response_model, usage = self.researcher.research(request)
        try:
            validate_education_research(payload, request=request)
        except EducationResearchInvalidResponse as exc:
            exc.usage = usage
            exc.model = response_model
            raise
        result = normalize_public_education_result(payload)
        result.update({
            "status": "completed", "authority": "ai_research", "source": "openai_web_search",
            "accessed_at": datetime.now(timezone.utc).isoformat(),
            "versions": {"research": RESEARCH_VERSION, "prompt": PROMPT_VERSION, "schema": SCHEMA_VERSION},
            "model": {"provider": "openai", "configured": "gpt-5.6-luna", "response": response_model},
            "usage": deepcopy(usage),
        })
        return result


def normalize_public_education_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove candidate-context claims that public institution research cannot support."""
    result = deepcopy(payload)
    for credential in result.get("credentials", []):
        credential["cv_consistency"] = "evidence_unavailable"
        credential["location_difference_for_review"] = None
        credential["findings"] = [
            finding for finding in credential.get("findings", [])
            if finding.get("kind") != "cv_consistency"
        ]
    return result


def apply_owner_scoped_education_context(
    public_result: dict[str, Any],
    stored_report: dict[str, Any],
    *,
    location_resolver: LocationResolver | None,
) -> dict[str, Any]:
    """Compare cited institution countries with the owner's code-owned location."""
    result = normalize_public_education_result(public_result)
    if location_resolver is None:
        return result
    claimed_country = _declared_country_code(stored_report)
    if not claimed_country:
        return result

    for credential in result.get("credentials", []):
        country = credential.get("country")
        if not isinstance(country, str) or not country.strip():
            continue
        location_findings = [
            finding
            for finding in credential.get("findings", [])
            if finding.get("kind") == "location" and finding.get("source_urls")
        ]
        if not location_findings:
            continue
        resolution = location_resolver.resolve(
            country.strip(),
            level=ResolutionLevel.COUNTRY,
        )
        researched_country = None
        if isinstance(resolution, Resolved):
            researched_country = resolution.resolution.country_code
        elif isinstance(resolution, Ambiguous) and resolution.common_resolution:
            researched_country = resolution.common_resolution.country_code
        if not researched_country:
            continue

        if researched_country == claimed_country:
            credential["cv_consistency"] = "supported"
            credential["location_difference_for_review"] = None
            continue

        summary = (
            f"Public sources place this education entry in {country.strip()}, while "
            f"the code-owned stated-location country is {claimed_country}. Review "
            "whether the education history explains this difference."
        )
        credential["cv_consistency"] = "mismatch"
        credential["location_difference_for_review"] = summary
        source_urls = list(
            dict.fromkeys(
                url
                for finding in location_findings
                for url in finding["source_urls"]
            )
        )
        credential["findings"].append(
            {
                "kind": "cv_consistency",
                "summary": summary,
                "source_urls": source_urls,
                "confidence": credential.get("confidence", "low"),
                "uncertainty": (
                    "A different education country is not evidence of a false claim; "
                    "study history may explain it."
                ),
            }
        )
    return result


def build_education_research_request(stored_report: dict[str, Any]) -> EducationResearchRequest:
    facts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for record in accepted_records(stored_report, "education"):
        institution = supported_field(record, "institution")
        program = supported_field(record, "program")
        certificate = supported_field(record, "certificate")
        if institution is not None and not _safe_subject(institution):
            continue
        if certificate is not None and not _safe_subject(certificate):
            certificate = None
        if institution is None and certificate is None:
            continue
        fact: dict[str, Any] = {}
        if institution is not None:
            fact["institution"] = institution
        if program is not None and _safe_subject(program):
            fact["program"] = program[:200]
        if certificate is not None:
            fact["certificate"] = certificate
        key = _key(fact)
        if key in seen:
            continue
        seen.add(key)
        facts.append(fact)
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
        for field, kind in (("program_exists", "program"), ("degree_exists", "degree"), ("certificate_exists", "certificate")):
            if credential[field] != "evidence_unavailable": required.add(kind)
        if credential["dates"] is not None: required.add("dates")
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


def _declared_country_code(stored_report: dict[str, Any]) -> str:
    mechanical = stored_report.get("mechanical")
    if not isinstance(mechanical, dict):
        return ""
    resolutions = mechanical.get("location_resolution")
    if not isinstance(resolutions, list):
        return ""
    for item in resolutions:
        if not isinstance(item, dict) or item.get("subject") != "declared_location":
            continue
        country_code = item.get("country_code")
        if isinstance(country_code, str) and country_code.strip():
            return country_code.strip().upper()
    return ""
