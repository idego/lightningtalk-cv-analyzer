from __future__ import annotations

import json
from importlib.resources import files
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import openai

from cv_validator.research.domain import CompanyResearchClientError, CompanyResearchInvalidResponse, CompanyResearchRequest, CompanyResearchTimeout, EducationResearchClientError, EducationResearchInvalidResponse, EducationResearchRequest, EducationResearchTimeout, LinkedInDiscoveryRequest, LinkedInResearchClientError, LinkedInResearchInvalidResponse, LinkedInResearchTimeout
from cv_validator.research.linkedin import DEFAULT_MAX_PROFILES, MAX_PROFILES_LIMIT


class OpenAIResponsesCompanyResearcher:
    def __init__(self, *, client=None, api_key: str | None = None, timeout_seconds: float = 120.0):
        self._client = client or openai.OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)

    def research(self, request: CompanyResearchRequest):
        prompt = files("cv_validator.research.contracts").joinpath("prompt.md").read_text()
        schema = json.loads(files("cv_validator.research.contracts").joinpath("company-research.schema.json").read_text())
        try:
            response = self._client.responses.create(
                model="gpt-5.6-luna",
                reasoning={"effort": "medium"},
                instructions=prompt,
                input=json.dumps({"organization_facts": request.input_facts}, ensure_ascii=False),
                tools=[{"type": "web_search", "search_context_size": "low"}],
                include=["web_search_call.action.sources"],
                max_tool_calls=4,
                text={"format": {"type": "json_schema", "name": "company_research", "strict": True, "schema": schema}},
                store=False,
                max_output_tokens=4096,
            )
        except openai.APITimeoutError as exc:
            raise CompanyResearchTimeout() from exc
        except openai.APIError as exc:
            raise CompanyResearchClientError() from exc
        try:
            payload = json.loads(response.output_text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise CompanyResearchInvalidResponse("invalid_json") from exc
        source_urls = _source_urls(response)
        actual_queries = _search_queries(response)
        if not actual_queries or len(actual_queries) > 4:
            raise CompanyResearchInvalidResponse("search_count")
        payload["searches_performed"] = actual_queries
        if len(payload.get("organizations", [])) == len(request.input_facts):
            for organization, input_fact in zip(
                payload["organizations"], request.input_facts, strict=True
            ):
                organization["query_subject"] = input_fact["organization"]
        _retain_cited_company_urls(payload, source_urls)
        usage = response.usage.model_dump() if response.usage is not None else {}
        return payload, response.model, usage


class OpenAIResponsesEducationResearcher:
    def __init__(self, *, client=None, api_key: str | None = None, timeout_seconds: float = 120.0):
        self._client = client or openai.OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)

    def research(self, request: EducationResearchRequest):
        prompt = files("cv_validator.research.contracts").joinpath("education-prompt.md").read_text()
        schema = json.loads(files("cv_validator.research.contracts").joinpath("education-research.schema.json").read_text())
        try:
            response = self._client.responses.create(
                model="gpt-5.6-luna", reasoning={"effort": "medium"}, instructions=prompt,
                input=json.dumps({"education_facts": request.input_facts}, ensure_ascii=False),
                tools=[{"type": "web_search", "search_context_size": "low"}],
                include=["web_search_call.action.sources"], max_tool_calls=4,
                text={"format": {"type": "json_schema", "name": "education_research", "strict": True, "schema": schema}},
                store=False, max_output_tokens=4096,
            )
        except openai.APITimeoutError as exc:
            raise EducationResearchTimeout() from exc
        except openai.APIError as exc:
            raise EducationResearchClientError() from exc
        try:
            payload = json.loads(response.output_text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise EducationResearchInvalidResponse() from exc
        source_urls = _source_urls(response)
        actual_queries = _search_queries(response)
        if not actual_queries or len(actual_queries) > 4:
            raise EducationResearchInvalidResponse()
        payload["searches_performed"] = actual_queries
        if len(payload.get("credentials", [])) == len(request.input_facts):
            for credential, input_fact in zip(
                payload["credentials"], request.input_facts, strict=True
            ):
                for field in ("institution", "program", "certificate"):
                    credential[field] = input_fact.get(field)
        _retain_cited_education_findings(payload, source_urls)
        usage = response.usage.model_dump() if response.usage is not None else {}
        return payload, response.model, usage


class OpenAIResponsesLinkedInResearcher:
    def __init__(
        self,
        *,
        client=None,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
        connection_threshold: int = 500,
        max_profiles: int = DEFAULT_MAX_PROFILES,
    ):
        if not 1 <= max_profiles <= MAX_PROFILES_LIMIT:
            raise ValueError("linkedin_max_profiles_out_of_range")
        self._client = client or openai.OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)
        self._connection_threshold = connection_threshold
        self._max_profiles = max_profiles

    def discover(self, request: LinkedInDiscoveryRequest):
        return self._call(
            "linkedin-discovery.schema.json",
            "linkedin_discovery",
            {
                "candidate_name": request.candidate["name"],
                "search_hints": request.candidate.get("search_hints", []),
                "max_profiles": self._max_profiles,
            },
        )

    def _call(self, schema_file: str, schema_name: str, input_payload: dict[str, Any]):
        prompt = files("cv_validator.research.contracts").joinpath("linkedin-prompt.md").read_text()
        schema = json.loads(files("cv_validator.research.contracts").joinpath(schema_file).read_text())
        try:
            response = self._client.responses.create(
                model="gpt-5.6-luna", reasoning={"effort": "medium"}, instructions=prompt,
                input=json.dumps(input_payload, ensure_ascii=False),
                tools=[{"type": "web_search", "search_context_size": "low"}],
                include=["web_search_call.action.sources"], max_tool_calls=4,
                text={"format": {"type": "json_schema", "name": schema_name, "strict": True, "schema": schema}},
                store=False, max_output_tokens=4096,
            )
        except openai.APITimeoutError as exc:
            raise LinkedInResearchTimeout() from exc
        except openai.APIError as exc:
            raise LinkedInResearchClientError() from exc
        try:
            payload = json.loads(response.output_text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise LinkedInResearchInvalidResponse("json_parse") from exc
        searches = _search_queries(response)
        if not searches or len(searches) > 4:
            raise LinkedInResearchInvalidResponse("search_count")
        payload["searches_performed"] = searches
        sources = _source_urls(response)
        if schema_name == "linkedin_discovery":
            _retain_sourced_linkedin_profiles(
                payload, sources, connection_threshold=self._connection_threshold
            )
        usage = response.usage.model_dump() if response.usage is not None else {}
        return payload, response.model, usage


def _source_urls(response: Any) -> set[str]:
    urls: set[str] = set()
    for item in getattr(response, "output", ()):
        if getattr(item, "type", None) == "web_search_call":
            for source in getattr(getattr(item, "action", None), "sources", ()) or ():
                url = source.get("url") if isinstance(source, dict) else getattr(source, "url", None)
                if url: urls.add(url)
        for content in getattr(item, "content", ()) or ():
            for annotation in getattr(content, "annotations", ()) or ():
                url = getattr(annotation, "url", None)
                if url: urls.add(url)
    return urls


def _search_queries(response: Any) -> list[str]:
    searches: list[str] = []
    for item in getattr(response, "output", ()):
        if getattr(item, "type", None) != "web_search_call":
            continue
        action_queries: list[str] = []
        query = getattr(getattr(item, "action", None), "query", None)
        if isinstance(query, str) and query:
            action_queries.append(query)
        for query in getattr(getattr(item, "action", None), "queries", ()) or ():
            if isinstance(query, str) and query and query not in action_queries:
                action_queries.append(query)
        if action_queries:
            searches.append(" | ".join(action_queries))
    return searches


def _retain_cited_company_urls(payload: dict[str, Any], sources: set[str]) -> None:
    canonical_sources = {_canonical_source_url(url) for url in sources}
    source_origins = {_source_origin(url) for url in sources}
    normalized = False
    for organization in payload.get("organizations", []):
        for key in ("company_pages", "registries"):
            retained = [
                url
                for url in organization.get(key, [])
                if _canonical_source_url(url) in canonical_sources
                or _source_origin(url) in source_origins
            ]
            normalized = normalized or retained != organization.get(key, [])
            organization[key] = retained
        retained_findings: list[dict[str, Any]] = []
        for finding in organization.get("findings", []):
            retained = [
                url
                for url in finding.get("source_urls", [])
                if _canonical_source_url(url) in canonical_sources
                or _source_origin(url) in source_origins
            ]
            normalized = normalized or retained != finding.get("source_urls", [])
            finding["source_urls"] = retained
            if retained:
                retained_findings.append(finding)
            else:
                normalized = True
        organization["findings"] = retained_findings
        official_website = organization.get("official_website")
        if official_website and _source_origin(official_website) not in source_origins:
            organization["official_website"] = None
            normalized = True
        if not retained_findings:
            organization.update({
                "existence": "insufficient_evidence",
                "activity": None,
                "operating_dates": None,
                "location": None,
                "relationship": None,
                "official_website": None,
                "company_pages": [],
                "registries": [],
                "confidence": "low",
                "limited_online_presence": True,
                "limited_online_presence_reason": (
                    "The returned web sources did not support a retained finding. "
                    "This does not establish existence or absence."
                ),
            })
            normalized = True
    if normalized:
        payload.setdefault("search_limitations", []).append(
            "Some URLs not supported by returned web-search origins were omitted."
        )


def _retain_cited_education_findings(
    payload: dict[str, Any], sources: set[str]
) -> None:
    canonical_sources = {_canonical_source_url(url) for url in sources}
    source_origins = {_source_origin(url) for url in sources}
    normalized = False
    for credential in payload.get("credentials", []):
        retained_findings: list[dict[str, Any]] = []
        for finding in credential.get("findings", []):
            retained_urls = [
                url
                for url in finding.get("source_urls", [])
                if _canonical_source_url(url) in canonical_sources
                or _source_origin(url) in source_origins
            ]
            normalized = normalized or retained_urls != finding.get("source_urls", [])
            finding["source_urls"] = retained_urls
            if retained_urls:
                retained_findings.append(finding)
            else:
                normalized = True
        credential["findings"] = retained_findings
        retained_kinds = {finding["kind"] for finding in retained_findings}
        for field, kind in (
            ("institution_exists", "institution"),
            ("program_exists", "program"),
            ("degree_exists", "degree"),
            ("certificate_exists", "certificate"),
        ):
            if kind not in retained_kinds:
                credential[field] = "evidence_unavailable"
        if "dates" not in retained_kinds:
            credential["dates"] = None
        if "accreditation" not in retained_kinds:
            credential["accreditation_status"] = "evidence_unavailable"
        if "location" not in retained_kinds:
            credential["city"] = None
            credential["country"] = None
        if "cv_consistency" not in retained_kinds:
            credential["cv_consistency"] = "evidence_unavailable"
            credential["location_difference_for_review"] = None
        if not retained_findings:
            credential["confidence"] = "low"
            credential["uncertainty"] = (
                "The returned web sources did not support a retained finding."
            )
    if normalized:
        payload.setdefault("search_limitations", []).append(
            "Some claims without support from returned web-search origins were omitted."
        )


def _canonical_source_url(url: str) -> str:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").casefold()
    netloc = parsed.netloc.casefold()
    if hostname == "linkedin.com" or hostname.endswith(".linkedin.com"):
        netloc = "www.linkedin.com"
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.casefold(), netloc, path, "", ""))


def _source_origin(url: str) -> tuple[str, str]:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").casefold()
    if hostname == "linkedin.com" or hostname.endswith(".linkedin.com"):
        hostname = "www.linkedin.com"
    return parsed.scheme.casefold(), hostname


def _retain_sourced_linkedin_profiles(
    payload: dict[str, Any],
    sources: set[str],
    *,
    connection_threshold: int,
) -> None:
    canonical_sources = {_canonical_source_url(url) for url in sources}

    def sourced(url: Any) -> bool:
        return isinstance(url, str) and _canonical_source_url(url) in canonical_sources

    retained_profiles: list[dict[str, Any]] = []
    normalized = False
    for profile in payload.get("possible_profiles", []):
        if not sourced(profile.get("profile_url")):
            normalized = True
            continue

        profile["source_urls"] = list(dict.fromkeys([
            profile["profile_url"],
            *[
            url for url in profile.get("source_urls", []) if sourced(url)
            ],
        ]))
        if not sourced(profile.get("photo_source_url")):
            profile["photo_visible"] = "unknown"
            profile["photo_source_url"] = None
        count = profile.get("connection_count", {})
        count_is_complete = (
            count.get("visibility") == "visible"
            and isinstance(count.get("minimum"), int)
            and sourced(count.get("source_url"))
        )
        if not count_is_complete:
            count.update({
                "visibility": "unknown",
                "minimum": None,
                "maximum": None,
                "display": None,
                "source_url": None,
            })
            profile["connection_completeness_flag"] = False
        else:
            maximum = count.get("maximum")
            if maximum is not None and (
                not isinstance(maximum, int) or maximum < count["minimum"]
            ):
                count["maximum"] = None
                normalized = True
            profile["connection_completeness_flag"] = (
                count["minimum"] < connection_threshold
            )

        if profile["source_urls"]:
            retained_profiles.append(profile)
        else:
            normalized = True

    payload["possible_profiles"] = retained_profiles
    payload["linkedin_not_found"] = not retained_profiles
    if retained_profiles and payload.get("outcome") == "insufficient_evidence":
        payload["outcome"] = "ambiguous"
    if not retained_profiles:
        payload["outcome"] = "insufficient_evidence"
        payload["not_found_caveat"] = (
            "No sufficiently sourced public LinkedIn profile was retained. "
            "This does not prove that no profile exists."
        )
    if normalized:
        payload.setdefault("search_limitations", []).append(
            "Unsourced profile details were omitted from the retained result."
        )
