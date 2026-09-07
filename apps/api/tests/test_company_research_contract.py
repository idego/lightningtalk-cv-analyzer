import pytest

from cv_validator.research.company import CompanyResearchRequest, validate_company_research
from cv_validator.research.domain import CompanyResearchInvalidResponse


def company_payload() -> dict:
    return {
        "schema_version": "company-research-schema-v3",
        "outcome": "completed",
        "organizations": [{
            "query_subject": "Example Systems",
            "entity_match": "ambiguous", "continuity_unclear": True, "lifecycle_events": [],
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


@pytest.mark.parametrize("period", [
    {"from": None, "to": None, "ongoing": False, "comment": "No dates."},
    {"from": "2013", "to": "2020", "ongoing": True, "comment": None},
])
def test_optional_invalid_period_does_not_discard_sourced_company(period: dict) -> None:
    payload = company_payload()
    company = payload["organizations"][0]
    valid_period = company["operating_periods"][0].copy()
    company["operating_periods"].append(period)
    validate_company_research(payload, request=CompanyResearchRequest(({"organization": "Example Systems"},)))
    assert company["operating_periods"] == [valid_period]
    assert company["existence"] == "supported"
    assert company["official_website"] == "https://example.com/"
    assert company["findings"]


@pytest.mark.parametrize("finding_level", ["medium", "low"])
def test_overall_confidence_is_lowered_instead_of_discarding_research(finding_level) -> None:
    payload = company_payload()
    company = payload["organizations"][0]
    company["confidence"] = "high"
    company["findings"][0]["confidence"] = finding_level
    validate_company_research(payload, request=CompanyResearchRequest(({"organization": "Example Systems"},)))
    assert company["confidence"] == finding_level
    assert company["existence"] == "supported"
    assert company["findings"][0]["source_urls"] == ["https://example.com/"]


def test_missing_evidence_is_still_rejected() -> None:
    payload = company_payload()
    payload["organizations"][0]["findings"] = []
    with pytest.raises(CompanyResearchInvalidResponse, match="claims_without_findings"):
        validate_company_research(payload, request=CompanyResearchRequest(({"organization": "Example Systems"},)))


def test_wrong_subject_is_still_rejected() -> None:
    with pytest.raises(CompanyResearchInvalidResponse, match="subject_mismatch"):
        validate_company_research(company_payload(), request=CompanyResearchRequest(({"organization": "Different Company"},)))
