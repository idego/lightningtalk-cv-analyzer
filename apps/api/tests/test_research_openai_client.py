from __future__ import annotations

import json
from copy import deepcopy

from cv_validator.research.domain import CompanyResearchRequest, EducationResearchRequest
from cv_validator.research.openai_client import (
    OpenAIResponsesCompanyResearcher,
    OpenAIResponsesEducationResearcher,
)


class Usage:
    def model_dump(self):
        return {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}


class Action:
    def __init__(self, query: str, sources: list[str]) -> None:
        self.query = query
        self.queries = []
        self.sources = [{"url": source} for source in sources]


class WebSearchCall:
    type = "web_search_call"

    def __init__(self, query: str, sources: list[str]) -> None:
        self.action = Action(query, sources)
        self.content = []


class Response:
    status = "completed"
    model = "gpt-5.6-luna"
    usage = Usage()

    def __init__(self, payload: dict, sources: list[str]) -> None:
        self.output_text = json.dumps(payload)
        self.output = [WebSearchCall("bounded public research", sources)]


class Responses:
    def __init__(self, response: Response) -> None:
        self.response = response

    def create(self, **_kwargs):
        return self.response


class Client:
    def __init__(self, response: Response) -> None:
        self.responses = Responses(response)


def company_item(subject: str, source: str) -> dict:
    return {
        "query_subject": subject,
        "existence": "supported",
        "activity": "Software services",
        "operating_periods": [],
        "offices": [],
        "relationship": None,
        "official_website": source,
        "company_pages": [],
        "registries": [],
        "confidence": "medium",
        "uncertainty": "Public sources only.",
        "findings": [{
            "kind": "public_footprint",
            "summary": f"Public evidence for {subject}.",
            "source_urls": [source],
            "confidence": "medium",
            "uncertainty": "Public sources only.",
        }],
        "limited_online_presence": False,
        "limited_online_presence_reason": None,
    }


def education_item(institution: str, program: str, source: str) -> dict:
    return {
        "institution": institution,
        "program": program,
        "certificate": None,
        "degree": None,
        "program_exists": "supported",
        "degree_exists": "evidence_unavailable",
        "certificate_exists": "evidence_unavailable",
        "dates": None,
        "city": None,
        "country": None,
        "cv_consistency": "evidence_unavailable",
        "location_difference_for_review": None,
        "confidence": "medium",
        "uncertainty": "Public sources only.",
        "findings": [{
            "kind": "program",
            "summary": f"Public evidence for {program}.",
            "source_urls": [source],
            "confidence": "medium",
            "uncertainty": "Public sources only.",
        }],
    }


def test_company_research_maps_reversed_model_rows_by_echoed_subject() -> None:
    first_source = "https://first.example/"
    second_source = "https://second.example/"
    payload = {
        "schema_version": "company-research-schema-v2",
        "outcome": "completed",
        "organizations": [
            company_item("Second Systems", second_source),
            company_item("First Systems", first_source),
        ],
        "searches_performed": ["placeholder"],
        "search_limitations": ["Public indexed sources only."],
    }
    researcher = OpenAIResponsesCompanyResearcher(
        client=Client(Response(deepcopy(payload), [first_source, second_source]))
    )

    result, _, _ = researcher.research(CompanyResearchRequest((
        {"organization": "First Systems"},
        {"organization": "Second Systems"},
    )))

    assert [item["query_subject"] for item in result["organizations"]] == [
        "First Systems",
        "Second Systems",
    ]
    assert result["organizations"][0]["activity"] == "Software services"


def test_education_research_maps_reversed_model_rows_by_echoed_subject() -> None:
    first_source = "https://first.example.edu/"
    second_source = "https://second.example.edu/"
    payload = {
        "schema_version": "education-research-schema-v4",
        "outcome": "completed",
        "credentials": [
            education_item("Second University", "Physics", second_source),
            education_item("First University", "Computer Science", first_source),
        ],
        "searches_performed": ["placeholder"],
        "search_limitations": ["Public indexed sources only."],
    }
    researcher = OpenAIResponsesEducationResearcher(
        client=Client(Response(deepcopy(payload), [first_source, second_source]))
    )

    result, _, _ = researcher.research(EducationResearchRequest((
        {"institution": "First University", "program": "Computer Science", "certificate": None},
        {"institution": "Second University", "program": "Physics", "certificate": None},
    )))

    assert [item["institution"] for item in result["credentials"]] == [
        "First University",
        "Second University",
    ]
    assert [item["program"] for item in result["credentials"]] == [
        "Computer Science",
        "Physics",
    ]
