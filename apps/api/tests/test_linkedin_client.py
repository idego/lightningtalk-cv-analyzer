import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cv_validator.research.domain import LinkedInDiscoveryRequest, LinkedInResearchInvalidResponse
from cv_validator.research.openai_client import OpenAIResponsesLinkedInResearcher


def response(*, status="completed", output_text=None, searches=1):
    url = "https://www.linkedin.com/in/synthetic-example"
    payload = {
        "possible_profiles": [
            {"profile_url": url, "confidence": "high", "uncertainty": "Name only"},
            {"profile_url": "https://www.linkedin.com/in/unsupported-example"},
        ],
        "search_limitations": [],
    }
    return SimpleNamespace(
        status=status,
        output_text=json.dumps(payload) if output_text is None else output_text,
        output=[SimpleNamespace(
            type="web_search_call",
            action=SimpleNamespace(query="synthetic query", sources=[{"url": url}]),
        ) for _ in range(searches)],
        usage=SimpleNamespace(model_dump=lambda: {"input_tokens": 12}),
        model="synthetic-model",
    )


def test_discovery_preserves_request_limits_and_normalizes_sourced_profiles():
    client = Mock()
    client.responses.create.return_value = response()
    researcher = OpenAIResponsesLinkedInResearcher(client=client, max_profiles=2)
    request = LinkedInDiscoveryRequest({"name": "Synthetic Example"})

    payload, model, usage = researcher.discover(request)

    sent = client.responses.create.call_args.kwargs
    assert json.loads(sent["input"]) == {
        "candidate_name": "Synthetic Example", "search_hints": [], "max_profiles": 2,
    }
    assert sent["store"] is False
    assert sent["max_tool_calls"] == 4
    assert sent["max_output_tokens"] == 6000
    assert sent["text"]["format"]["name"] == "linkedin_discovery"
    assert len(payload["possible_profiles"]) == 1
    assert payload["possible_profiles"][0]["confidence"] == "medium"
    assert payload["searches_performed"] == ["synthetic query"]
    assert (model, usage) == ("synthetic-model", {"input_tokens": 12})


@pytest.mark.parametrize(("overrides", "reason"), [
    ({"status": "incomplete"}, "truncated"),
    ({"output_text": "invalid"}, "json_parse"),
    ({"searches": 0}, "search_count"),
    ({"searches": 5}, "search_count"),
])
def test_discovery_preserves_response_failure_reasons(overrides, reason):
    client = Mock()
    client.responses.create.return_value = response(**overrides)
    with pytest.raises(LinkedInResearchInvalidResponse, match=reason):
        OpenAIResponsesLinkedInResearcher(client=client).discover(
            LinkedInDiscoveryRequest({"name": "Synthetic Example"})
        )
