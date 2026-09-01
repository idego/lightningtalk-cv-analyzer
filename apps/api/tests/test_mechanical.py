from cv_validator.analysis.source import TextSegment
from cv_validator.mechanical import extract_mechanical


def test_mechanical_extracts_only_literal_candidates() -> None:
    result = extract_mechanical([
        TextSegment(
            id="segment-1",
            text=(
                "Jane Example +48 501 234 567 jane@gmial.com "
                "https://github.com/jane Warsaw 00-001"
            ),
            page_number=1,
        )
    ])

    assert result["phones"][0]["country_code"] == "PL"
    assert result["emails"][0]["value"] == "jane@gmial.com"
    assert result["email_findings"][0]["suggested_domain"] == "gmail.com"
    assert result["literal_links"][0]["known_host"] == "github"
    assert result["postal_candidates"][0]["ownership_status"] == "candidate"
    assert result["accepted_postal_addresses"] == []


def test_postal_overlap_keeps_ambiguity() -> None:
    result = extract_mechanical([
        TextSegment(id="segment-1", text="Reference number 12345")
    ])

    assert result["postal_candidates"][0]["possible_country_codes"] == [
        "DE",
        "FR",
        "US",
    ]
