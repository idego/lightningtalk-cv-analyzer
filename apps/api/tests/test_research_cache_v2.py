from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from conftest import valid_report
from cv_validator.api.app import create_app
from cv_validator.errors import PersistenceError
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


class AdaptiveCompanyResearcher:
    def __init__(self) -> None:
        self.calls = []

    def research(self, request):
        self.calls.append(request)
        base = company_result()
        template = base["organizations"][0]
        base["organizations"] = [
            {**deepcopy(template), "query_subject": fact["organization"]}
            for fact in request.input_facts
        ]
        return base, "gpt-5.6-luna", {"input_tokens": 10, "output_tokens": 20}


def company_result() -> dict:
    return {
        "schema_version": "company-research-schema-v2",
        "outcome": "completed",
        "organizations": [{
            "query_subject": "Example Systems",
            "existence": "supported",
            "activity": "Software services",
            "operating_periods": [],
            "offices": [],
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
        "schema_version": "education-research-schema-v3",
        "outcome": "completed",
        "credentials": [{
            "institution": "Example University",
            "program": "Computer Science",
            "degree": None,
            "program_exists": "supported",
            "degree_exists": "evidence_unavailable",
            "dates": None,
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
                for kind in ("program",)
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
    assert second.json()["company_research"]["usage"]["input_tokens"] == 0
    assert second.json()["company_research"]["usage"]["output_tokens"] == 0
    assert len(researcher.calls) == 1
    assert app.state.store.get_cache_audit("analysis-2")[0]["outcome"] == "hit"
    usage = app.state.store.get_usage_summary()
    assert usage["requests"] == 1
    assert usage["paid_requests"] == 1


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


def test_company_research_combines_subject_hit_with_miss(tmp_path) -> None:
    researcher = AdaptiveCompanyResearcher()
    app = create_app(
        db_path=tmp_path / "reports.db",
        openai_settings=OpenAISettings(enabled=True, api_key="test-key"),
        company_researcher=researcher,
    )
    first = valid_report(sha256="1" * 64)
    first["analysis_id"] = "analysis-1"
    second = valid_report(sha256="2" * 64)
    second["analysis_id"] = "analysis-2"
    extra = deepcopy(second["base_analysis"]["employment"][0])
    extra["id"] = "employment-2"
    extra["organization"]["value"] = "Another Systems"
    extra["organization"]["evidence"][0]["excerpt"] = "Another Systems"
    second["base_analysis"]["employment"].append(extra)
    second["base_analysis"]["review"]["accepted_ids"].append("employment-2")
    app.state.store.persist_analysis_payload_for_test(first)
    app.state.store.persist_analysis_payload_for_test(second)
    client = client_for(app)

    assert client.post("/analyses/analysis-1/research/company").status_code == 200
    mixed = client.post("/analyses/analysis-2/research/company")

    assert mixed.status_code == 200
    research = mixed.json()["company_research"]
    assert research["cache"]["status"] == "partial_hit"
    assert [item["status"] for item in research["cache"]["subjects"]] == ["hit", "miss"]
    assert len(researcher.calls) == 2
    assert researcher.calls[1].input_facts == ({"organization": "Another Systems"},)


def test_company_refresh_bypasses_and_replaces_cached_result(tmp_path) -> None:
    researcher = FakeResearcher(company_result())
    app = create_app(
        db_path=tmp_path / "reports.db",
        openai_settings=OpenAISettings(enabled=True, api_key="test-key"),
        company_researcher=researcher,
    )
    report = valid_report()
    report["analysis_id"] = "analysis-refresh"
    app.state.store.persist_analysis_payload_for_test(report)
    client = client_for(app)

    assert client.post("/analyses/analysis-refresh/research/company").status_code == 200
    refreshed = client.post(
        "/analyses/analysis-refresh/research/company",
        headers={"X-Research-Refresh": "true"},
    )

    assert refreshed.status_code == 200
    assert refreshed.json()["company_research"]["cache"]["status"] == "miss"
    assert len(researcher.calls) == 2
    assert app.state.store.get_usage_summary()["requests"] == 2


def test_paid_research_is_ledgered_before_mutable_result_persistence(tmp_path) -> None:
    researcher = FakeResearcher(company_result())
    app = create_app(
        db_path=tmp_path / "reports.db",
        openai_settings=OpenAISettings(enabled=True, api_key="test-key"),
        company_researcher=researcher,
    )
    report = valid_report()
    report["analysis_id"] = "analysis-persistence-failure"
    app.state.store.persist_analysis_payload_for_test(report)

    def fail_persist(*_args, **_kwargs):
        raise PersistenceError("forced persistence failure")

    app.state.store.persist_company_research = fail_persist
    response = client_for(app).post("/analyses/analysis-persistence-failure/research/company")

    assert response.status_code == 409
    assert len(researcher.calls) == 1
    usage = app.state.store.get_usage_summary()
    assert usage["requests"] == 1
    assert usage["paid_requests"] == 1
    assert usage["total_tokens"] == 30


def test_multi_subject_research_usage_is_not_multiplied(tmp_path) -> None:
    researcher = AdaptiveCompanyResearcher()
    app = create_app(
        db_path=tmp_path / "reports.db",
        openai_settings=OpenAISettings(enabled=True, api_key="test-key"),
        company_researcher=researcher,
    )
    report = valid_report()
    report["analysis_id"] = "analysis-multiple"
    extra = deepcopy(report["base_analysis"]["employment"][0])
    extra["id"] = "employment-2"
    extra["organization"]["value"] = "Another Systems"
    extra["organization"]["evidence"][0]["excerpt"] = "Another Systems"
    report["base_analysis"]["employment"].append(extra)
    report["base_analysis"]["review"]["accepted_ids"].append("employment-2")
    app.state.store.persist_analysis_payload_for_test(report)

    response = client_for(app).post("/analyses/analysis-multiple/research/company")

    assert response.status_code == 200
    usage = response.json()["company_research"]["usage"]
    assert usage["input_tokens"] == 10
    assert usage["output_tokens"] == 20
