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
