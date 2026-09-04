import pytest

from cv_validator.research.company import CompanyResearchRequest, validate_company_research
from cv_validator.research.domain import CompanyResearchInvalidResponse


def company_payload() -> dict:
    return {
        "schema_version": "company-research-schema-v2",
        "outcome": "completed",
        "organizations": [{
            "query_subject": "Example Systems",
            "existence": "supported",
            "activity": "Software services",
            "operating_periods": [{
                "from": "2013",
                "to": None,
                "ongoing": True,
                "comment": "A registry records incorporation in 2015.",
            }],
            "offices": [
                {"address": "1 Example Street, Warsaw, Poland", "comment": "Registered office."},
                {"address": "2 Sample Road, Krakow, Poland", "comment": None},
            ],
            "relationship": None,
            "official_website": "https://example.com/",
            "company_pages": [],
            "registries": [],
            "confidence": "medium",
            "uncertainty": "Public sources only.",
            "findings": [{
                "kind": "public_footprint",
                "summary": "A matching public footprint was found.",
                "source_urls": ["https://example.com/"],
                "confidence": "medium",
                "uncertainty": "Public sources only.",
            }],
            "limited_online_presence": False,
            "limited_online_presence_reason": None,
        }],
        "searches_performed": ["Example Systems official website"],
        "search_limitations": ["Public indexed sources only."],
    }


def test_company_research_accepts_separate_offices_and_optional_comments() -> None:
    validate_company_research(
        company_payload(),
        request=CompanyResearchRequest(({"organization": "Example Systems"},)),
    )


@pytest.mark.parametrize(
    ("period", "reason"),
    [
        ({"from": None, "to": None, "ongoing": False, "comment": "No dates."}, "empty_operating_period"),
        ({"from": "2013", "to": "2020", "ongoing": True, "comment": None}, "contradictory_operating_period"),
    ],
)
def test_company_research_rejects_invalid_operating_periods(period: dict, reason: str) -> None:
    payload = company_payload()
    payload["organizations"][0]["operating_periods"] = [period]

    with pytest.raises(CompanyResearchInvalidResponse) as info:
        validate_company_research(
            payload,
            request=CompanyResearchRequest(({"organization": "Example Systems"},)),
        )

    assert info.value.reason == reason
