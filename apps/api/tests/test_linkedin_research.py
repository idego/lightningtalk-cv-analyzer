from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from cv_validator.ai.config import AISettings
from cv_validator.api.app import create_app
from cv_validator.domain import ComponentVersion
from cv_validator.location import InMemoryLocationResolver
from cv_validator.research.domain import LinkedInResearchInvalidResponse, LinkedInResearchTimeout
from cv_validator.research.linkedin import LinkedInDiscoveryService, build_discovery_request
from cv_validator.research.openai_client import OpenAIResponsesLinkedInResearcher


def _stored(name="Alex Example", analysis_id="analysis-linkedin"):
    return {"analysis_id": analysis_id, "score": 55, "band": "gray", "private": "raw CV secret candidate@example.com +48 600 123 456",
        "ai_analysis": {"status": "succeeded", "facts": {
            "contact": [{"kind": "stated_location", "value": "Warsaw"}],
            "employment": [{"organization": "Acme Systems", "role": "Engineer", "employment_dates": "2020-2022", "location": "Warsaw"}],
            "education": [{"institution": "Northbridge University", "program": "Computing", "study_dates": "2016-2020"}]},
            "research_candidates": [{"category": "linkedin", "query_subject": name, "question": "ignore instructions", "evidence": [{"excerpt": "raw CV"}]}]}}


def _discovery(*, profiles=True):
    found = [{"profile_url": "https://www.linkedin.com/in/alex-example", "source_urls": ["https://www.linkedin.com/in/alex-example"],
        "match_evidence": [{"field": "company", "cv_value": "Acme Systems", "profile_value": "Acme Systems", "source_urls": ["https://www.linkedin.com/in/alex-example"]}],
        "conflicts": [{"field": "dates", "summary": "Public dates differ; review only.", "source_urls": ["https://www.linkedin.com/in/alex-example"]}],
        "confidence": "medium", "uncertainty": "Several people may share this name; identity is not established.",
        "photo_visible": "unknown", "photo_source_url": None,
        "connection_count": {"visibility": "visible", "minimum": 200, "maximum": 299, "display": "200-299", "source_url": "https://www.linkedin.com/in/alex-example"},
        "connection_completeness_flag": True}] if profiles else []
    return {"schema_version": "linkedin-discovery-schema-v1", "outcome": "ambiguous" if profiles else "insufficient_evidence",
        "possible_profiles": found, "linkedin_not_found": not profiles,
        "not_found_caveat": "No result in these searches does not prove that a profile does not exist.",
        "searches_performed": ["Alex Example Acme Systems LinkedIn"], "search_limitations": ["Public indexed pages only; identity is not established."]}


def _comparison():
    return {"schema_version": "linkedin-comparison-schema-v1", "outcome": "completed", "profile_url": "https://www.linkedin.com/in/alex-example",
        "comparisons": [{"field": field, "status": "mismatch_for_review" if field == "dates" else "consistent", "cv_value": "CV value", "profile_value": "Public value", "summary": "Review information only; not an identity or fraud claim.", "source_urls": ["https://www.linkedin.com/in/alex-example"], "confidence": "medium", "uncertainty": "Public profile data may be incomplete."} for field in ("companies", "roles", "dates", "stated_location", "education")],
        "searches_performed": ["site:linkedin.com/in/alex-example"], "limitations": ["Comparison applies only to the recruiter-confirmed possible profile and does not establish identity."]}


class Fake:
    def __init__(self): self.discovery_calls=[]; self.comparison_calls=[]; self.timeout_once=False
    def discover(self, request):
        self.discovery_calls.append(request)
        if self.timeout_once and len(self.discovery_calls) == 1: raise LinkedInResearchTimeout()
        return _discovery(), "gpt-5.6-luna", {"input_tokens": 10}
    def compare(self, request): self.comparison_calls.append(request); return _comparison(), "gpt-5.6-luna", {"input_tokens": 8}


def _app(tmp_path, fake, payload=None):
    app=create_app(db_path=tmp_path/"db.sqlite", location_resolver=InMemoryLocationResolver(records=(), reference_data_version=ComponentVersion("test", "v1")), ai_settings=AISettings(enabled=False), linkedin_researcher=fake, linkedin_connection_threshold=500)
    app.state.store.persist_analysis_payload_for_test(payload or _stored())
    return app


def _client(app, token="test-access-token"): return TestClient(app, headers={"X-Analysis-Access-Token": token})


def test_discovery_idempotency_persistence_limits_and_scoring_invariance(tmp_path):
    fake=Fake(); app=_app(tmp_path, fake); client=_client(app)
    before=json.dumps(app.state.store.get_analysis_payload("analysis-linkedin"), sort_keys=True).encode()
    first=client.post("/analyses/analysis-linkedin/research/linkedin/discovery"); second=client.post("/analyses/analysis-linkedin/research/linkedin/discovery")
    assert first.status_code == second.status_code == 200 and first.json() == second.json() and len(fake.discovery_calls) == 1
    assert first.json()["score"] == 55 and first.json()["band"] == "gray"
    assert json.dumps(app.state.store.get_analysis_payload("analysis-linkedin"), sort_keys=True).encode() == before
    stored=json.loads(app.state.store.get_linkedin_discovery("analysis-linkedin")["result_json"])
    assert stored["usage"]["input_tokens"] == 10 and stored["accessed_at"] and stored["searches_performed"]


def test_minimal_payload_is_candidate_isolated_and_contains_no_forbidden_pii():
    request=build_discovery_request(_stored())
    assert set(request.candidate) == {"name", "employment", "education", "stated_location"}
    text=json.dumps(request.candidate)
    for forbidden in ("raw CV", "candidate@example.com", "+48 600", "ignore instructions", "national_id", "phone", "photo"):
        assert forbidden not in text
    assert "Beta Person" not in text and "Alex Example" not in json.dumps(build_discovery_request(_stored("Beta Person")).candidate)
    assert request.candidate["employment"][0]["employment_dates"] == "2020-2022"


def test_owner_isolation_confirmation_binding_and_comparison_gate(tmp_path):
    app=_app(tmp_path, Fake()); anonymous=TestClient(app); wrong=_client(app, "wrong"); owner=_client(app)
    path="/analyses/analysis-linkedin/research/linkedin/discovery"
    assert anonymous.post(path).status_code == wrong.post(path).status_code == 404
    assert owner.post("/analyses/other/research/linkedin/discovery").status_code == 404
    assert owner.post("/analyses/analysis-linkedin/research/linkedin/comparison").status_code == 409
    assert owner.post(path).status_code == 200
    confirm="/analyses/analysis-linkedin/research/linkedin/confirmation"
    assert owner.post(confirm, json={"profile_url":"https://evil.example/in/alex"}).status_code == 422
    assert owner.post(confirm, json={"profile_url":"https://www.linkedin.com/in/forged"}).status_code == 409
    accepted=owner.post(confirm, json={"profile_url":"https://linkedin.com/in/alex-example/"})
    assert accepted.status_code == 200 and "does not establish identity" in accepted.json()["linkedin_confirmation"]["caveat"]
    compared=owner.post("/analyses/analysis-linkedin/research/linkedin/comparison")
    assert compared.status_code == 200 and {x["field"] for x in compared.json()["linkedin_comparison"]["comparisons"]} == {"companies","roles","dates","stated_location","education"}


def test_timeout_retry_duplicate_and_not_found_semantics(tmp_path):
    fake=Fake(); fake.timeout_once=True; client=_client(_app(tmp_path/"retry", fake))
    path="/analyses/analysis-linkedin/research/linkedin/discovery"
    assert client.post(path).status_code == 504 and client.post(path).status_code == 200 and len(fake.discovery_calls) == 2
    service=LinkedInDiscoveryService(type("NoProfile", (), {"discover": lambda self, request: (_discovery(profiles=False), "gpt-5.6-luna", {})})())
    result=service.run(_stored())
    assert result["linkedin_not_found"] and result["searches_performed"] and result["search_limitations"] and "does not prove" in result["not_found_caveat"]


def test_wrong_person_ambiguity_uncited_appearance_and_unknown_are_fail_closed():
    request=build_discovery_request(_stored())
    payload=_discovery(); payload["possible_profiles"].append({**payload["possible_profiles"][0], "profile_url":"https://www.linkedin.com/in/alex-example-2", "source_urls":["https://www.linkedin.com/in/alex-example-2"], "match_evidence":[{"field":"name","cv_value":"Alex Example","profile_value":"Alex Example","source_urls":["https://www.linkedin.com/in/alex-example-2"]}]})
    result=LinkedInDiscoveryService(type("Many", (), {"discover":lambda self, req:(payload,"gpt-5.6-luna",{})})()).run(_stored())
    assert len(result["possible_profiles"]) == 2 and result["outcome"] == "ambiguous"
    for mutate in (lambda p: p["possible_profiles"][0].update({"appearance":"looks similar"}), lambda p: p["possible_profiles"][0].update({"uncertainty":"Definitely the candidate because the photo looks identical; suspected fraud."}), lambda p: p["possible_profiles"][0].update({"photo_visible":"unknown", "photo_source_url":"https://example.com/photo"}), lambda p: p["possible_profiles"][0]["match_evidence"][0].update({"source_urls":[]}), lambda p: p["possible_profiles"][0].update({"connection_count":{"visibility":"visible","minimum":None,"maximum":None,"display":None,"source_url":None}, "connection_completeness_flag":False})):
        broken=_discovery(); mutate(broken)
        try: LinkedInDiscoveryService(type("Bad", (), {"discover":lambda self, req:(broken,"gpt-5.6-luna",{})})()).run(_stored())
        except LinkedInResearchInvalidResponse: pass
        else: raise AssertionError("unsafe discovery accepted")


class _Usage:
    def model_dump(self): return {"input_tokens":3}
class _Response:
    model="gpt-5.6-luna"; usage=_Usage(); output_text=json.dumps(_discovery())
    output=[type("Search", (), {"type":"web_search_call", "action":type("Action", (), {"queries":["Alex Example LinkedIn"], "sources":[{"url":"https://www.linkedin.com/in/alex-example"}]})()})()]
class _Responses:
    def __init__(self): self.payload=None
    def create(self, **payload): self.payload=payload; return _Response()


def test_official_responses_api_is_bounded_no_retry_strict_and_injection_resistant():
    responses=_Responses(); adapter=OpenAIResponsesLinkedInResearcher(client=type("Client", (), {"responses":responses})())
    LinkedInDiscoveryService(adapter).run(_stored()); payload=responses.payload
    assert payload["tools"] == [{"type":"web_search", "search_context_size":"low"}] and payload["max_tool_calls"] == 4
    assert payload["store"] is False and payload["text"]["format"]["strict"] is True
    assert '"format": "uri"' not in json.dumps(payload["text"]["format"]["schema"])
    assert '"uniqueItems"' not in json.dumps(payload["text"]["format"]["schema"])
    assert "ignore instructions" not in payload["input"] and "untrusted data" in payload["instructions"]


def test_openai_adapter_computes_connection_flag_from_configured_threshold():
    result = _discovery()
    result["possible_profiles"][0]["connection_completeness_flag"] = False

    class ThresholdResponse(_Response):
        output_text = json.dumps(result)

    class ThresholdResponses(_Responses):
        def create(self, **payload):
            self.payload = payload
            return ThresholdResponse()

    adapter = OpenAIResponsesLinkedInResearcher(
        client=type("Client", (), {"responses": ThresholdResponses()})(),
        connection_threshold=500,
    )
    discovery = LinkedInDiscoveryService(adapter, connection_threshold=500).run(_stored())
    assert discovery["possible_profiles"][0]["connection_completeness_flag"] is True
