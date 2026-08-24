from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

import openai

from cv_validator.research.domain import CompanyResearchClientError, CompanyResearchInvalidResponse, CompanyResearchRequest, CompanyResearchTimeout, EducationResearchClientError, EducationResearchInvalidResponse, EducationResearchRequest, EducationResearchTimeout, LinkedInComparisonRequest, LinkedInDiscoveryRequest, LinkedInResearchClientError, LinkedInResearchInvalidResponse, LinkedInResearchTimeout


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
            raise CompanyResearchInvalidResponse() from exc
        source_urls = _source_urls(response)
        actual_queries = _search_queries(response)
        if not actual_queries or len(actual_queries) > 4:
            raise CompanyResearchInvalidResponse()
        payload["searches_performed"] = actual_queries
        cited = {url for org in payload.get("organizations", []) for finding in org.get("findings", []) for url in finding.get("source_urls", [])}
        cited.update(url for org in payload.get("organizations", []) for key in ("company_pages", "registries") for url in org.get(key, []))
        cited.update(org.get("official_website") for org in payload.get("organizations", []) if org.get("official_website"))
        if cited - source_urls:
            raise CompanyResearchInvalidResponse()
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
        cited = {url for item in payload.get("credentials", []) for finding in item.get("findings", []) for url in finding.get("source_urls", [])}
        if cited - source_urls:
            raise EducationResearchInvalidResponse()
        usage = response.usage.model_dump() if response.usage is not None else {}
        return payload, response.model, usage


class OpenAIResponsesLinkedInResearcher:
    def __init__(self, *, client=None, api_key: str | None = None, timeout_seconds: float = 120.0):
        self._client = client or openai.OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)

    def discover(self, request: LinkedInDiscoveryRequest):
        return self._call("linkedin-discovery.schema.json", "linkedin_discovery", {"candidate_facts": request.candidate})

    def compare(self, request: LinkedInComparisonRequest):
        return self._call("linkedin-comparison.schema.json", "linkedin_comparison", {"candidate_facts": request.candidate, "confirmed_profile_url": request.profile_url})

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
            raise LinkedInResearchInvalidResponse() from exc
        searches = _search_queries(response)
        if not searches or len(searches) > 4: raise LinkedInResearchInvalidResponse()
        payload["searches_performed"] = searches
        cited = _nested_source_urls(payload)
        if cited - _source_urls(response): raise LinkedInResearchInvalidResponse()
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
    queries: list[str] = []
    for item in getattr(response, "output", ()):
        if getattr(item, "type", None) != "web_search_call":
            continue
        query = getattr(getattr(item, "action", None), "query", None)
        if isinstance(query, str) and query and query not in queries:
            queries.append(query)
        for query in getattr(getattr(item, "action", None), "queries", ()) or ():
            if isinstance(query, str) and query and query not in queries:
                queries.append(query)
    return queries


def _nested_source_urls(value: Any) -> set[str]:
    urls: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"source_urls"} and isinstance(item, list):
                urls.update(url for url in item if isinstance(url, str))
            elif key in {"source_url", "photo_source_url", "profile_url"} and isinstance(item, str):
                urls.add(item)
            else: urls.update(_nested_source_urls(item))
    elif isinstance(value, list):
        for item in value: urls.update(_nested_source_urls(item))
    return urls
