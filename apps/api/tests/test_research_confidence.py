from cv_validator.research.openai_client import _normalize_linkedin_confidence


def test_linkedin_high_confidence_requires_an_explicit_supported_hint() -> None:
    payload = {
        "possible_profiles": [{
            "confidence": "high",
            "uncertainty": "The full name is visible, but experience context is unavailable.",
        }]
    }

    _normalize_linkedin_confidence(
        payload,
        {"search_hints": [{"organization": "Idego", "role": "Engineer"}]},
    )

    assert payload["possible_profiles"][0]["confidence"] == "medium"


def test_linkedin_conflicting_experience_is_always_low_confidence() -> None:
    payload = {
        "possible_profiles": [{
            "confidence": "high",
            "uncertainty": "Idego is visible, but the supported role conflicts with the hint.",
        }]
    }

    _normalize_linkedin_confidence(
        payload,
        {"search_hints": [{"organization": "Idego", "role": "Engineer"}]},
    )

    assert payload["possible_profiles"][0]["confidence"] == "low"


def test_linkedin_high_confidence_survives_supported_name_and_experience() -> None:
    payload = {
        "possible_profiles": [{
            "confidence": "high",
            "uncertainty": "The full name and Idego employer are visible; identity remains unverified.",
        }]
    }

    _normalize_linkedin_confidence(
        payload,
        {"search_hints": [{"organization": "Idego", "role": "Engineer"}]},
    )

    assert payload["possible_profiles"][0]["confidence"] == "high"


def _linkedin_profile(url: str, confidence: str) -> dict:
    return {
        "profile_url": url,
        "source_urls": [url],
        "confidence": confidence,
        "uncertainty": "Public indexed profile; identity remains unverified.",
        "photo_visible": "unknown",
        "photo_source_url": None,
        "connection_count": {
            "visibility": "unknown",
            "minimum": None,
            "maximum": None,
            "display": None,
            "source_url": None,
        },
        "connection_completeness_flag": False,
    }


def test_linkedin_service_keeps_highest_confidence_profiles_when_model_returns_more_than_display_limit() -> None:
    from cv_validator.research.linkedin import LinkedInDiscoveryService

    class Researcher:
        def discover(self, _request):
            return {
                "schema_version": "linkedin-discovery-schema-v3",
                "outcome": "completed",
                "possible_profiles": [
                    _linkedin_profile("https://www.linkedin.com/in/low-one", "low"),
                    _linkedin_profile("https://www.linkedin.com/in/high-one", "high"),
                    _linkedin_profile("https://www.linkedin.com/in/medium-one", "medium"),
                    _linkedin_profile("https://www.linkedin.com/in/high-two", "high"),
                ],
                "linkedin_not_found": False,
                "not_found_caveat": "Possible public profiles only; this does not prove identity.",
                "searches_performed": ["Jane Example LinkedIn"],
                "search_limitations": ["Public indexed sources only."],
            }, "gpt-5.6-luna", {"input_tokens": 10, "output_tokens": 5}

    report = {
        "base_analysis": {
            "profile": {
                "candidate_name": {
                    "value": "Jane Example", "status": "supported", "evidence": []
                }
            },
            "employment": [],
        }
    }
    result = LinkedInDiscoveryService(Researcher(), max_profiles=3).run(report)

    assert [profile["confidence"] for profile in result["possible_profiles"]] == [
        "high", "high", "medium"
    ]
    assert all("low-one" not in profile["profile_url"] for profile in result["possible_profiles"])


def test_linkedin_protected_claim_regex_does_not_reject_unrelated_origin_substrings() -> None:
    from cv_validator.research.linkedin import _reject_protected_claims

    _reject_protected_claims([
        "The profile was originally indexed by a public search engine; identity remains unverified."
    ])
