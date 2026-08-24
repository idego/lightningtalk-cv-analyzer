from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

import openai

from cv_validator.research.domain import CompanyResearchClientError, CompanyResearchInvalidResponse, CompanyResearchRequest, CompanyResearchTimeout


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
        for query in getattr(getattr(item, "action", None), "queries", ()) or ():
            if isinstance(query, str) and query and query not in queries:
                queries.append(query)
    return queries
