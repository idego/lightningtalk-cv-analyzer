from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from conftest import valid_report
from cv_validator.api.app import create_app
from cv_validator.openai_config import OpenAISettings


class FakeResearcher:
    def __init__(self, result: dict) -> None:
        self.calls = []
        self.result = result

    def research(self, request):
        self.calls.append(request)
        return deepcopy(self.result), "gpt-5.6-luna", {
            "input_tokens": 10,
            "output_tokens": 20,
        }


def company_result() -> dict:
    return {
        "schema_version": "company-research-schema-v1",
        "outcome": "completed",
        "organizations": [{
            "query_subject": "Example Systems",
            "existence": "supported",
            "activity": "Software services",
            "operating_dates": None,
            "location": None,
            "relationship": "employer",
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


def education_result() -> dict:
    return {
        "schema_version": "education-research-schema-v1",
        "outcome": "completed",
        "credentials": [{
            "institution": "Example University",
            "program": "Computer Science",
            "degree": None,
            "certificate": None,
            "institution_exists": "supported",
            "program_exists": "supported",
            "degree_exists": "evidence_unavailable",
            "certificate_exists": "evidence_unavailable",
            "dates": None,
            "accreditation_status": "evidence_unavailable",
            "city": None,
            "country": None,
            "cv_consistency": "evidence_unavailable",
            "location_difference_for_review": None,
            "confidence": "medium",
            "uncertainty": "Public sources only.",
            "findings": [
                {
                    "kind": kind,
                    "summary": f"A matching {kind} was found.",
                    "source_urls": ["https://example.edu/"],
                    "confidence": "medium",
                    "uncertainty": "Public sources only.",
                }
                for kind in ("institution", "program")
            ],
        }],
        "searches_performed": ["Example University Computer Science"],
        "search_limitations": ["Public indexed sources only."],
    }


def seed_two_reports(app) -> None:
    for index in (1, 2):
        report = valid_report(sha256=str(index) * 64)
        report["analysis_id"] = f"analysis-{index}"
        app.state.store.persist_analysis_payload_for_test(report)


def client_for(app) -> TestClient:
    return TestClient(
        app,
        headers={"X-Analysis-Access-Token": "test-access-token"},
    )


def test_company_research_reuses_public_cache_across_analyses(tmp_path) -> None:
    researcher = FakeResearcher(company_result())
    app = create_app(
        db_path=tmp_path / "reports.db",
        openai_settings=OpenAISettings(enabled=True, api_key="test-key"),
        company_researcher=researcher,
    )
    seed_two_reports(app)
    client = client_for(app)

    first = client.post("/analyses/analysis-1/research/company")
    second = client.post("/analyses/analysis-2/research/company")

    assert first.status_code == second.status_code == 200
    assert first.json()["company_research"]["cache"]["status"] == "miss"
    assert second.json()["company_research"]["cache"]["status"] == "hit"
    assert len(researcher.calls) == 1
    assert app.state.store.get_cache_audit("analysis-2")[0]["outcome"] == "hit"


def test_education_research_reuses_public_cache_across_analyses(tmp_path) -> None:
    researcher = FakeResearcher(education_result())
    app = create_app(
        db_path=tmp_path / "reports.db",
        openai_settings=OpenAISettings(enabled=True, api_key="test-key"),
        education_researcher=researcher,
    )
    seed_two_reports(app)
    client = client_for(app)

    first = client.post("/analyses/analysis-1/research/education")
    second = client.post("/analyses/analysis-2/research/education")

    assert first.status_code == second.status_code == 200
    assert first.json()["education_research"]["cache"]["status"] == "miss"
    assert second.json()["education_research"]["cache"]["status"] == "hit"
    assert len(researcher.calls) == 1
    assert app.state.store.get_cache_audit("analysis-2")[0]["outcome"] == "hit"
