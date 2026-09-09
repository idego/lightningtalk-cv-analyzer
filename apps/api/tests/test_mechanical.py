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


def test_links_are_tagged_linkedin_github_or_personal() -> None:
    result = extract_mechanical([
        TextSegment(
            id="segment-1",
            text=(
                "https://www.linkedin.com/in/jane https://github.com/jane "
                "www.jane.dev https://portfolio.example.org/work"
            ),
            page_number=1,
        )
    ])

    assert [link["known_host"] for link in result["literal_links"]] == [
        "linkedin",
        "github",
        "personal",
        "personal",
    ]


def test_schemeless_known_host_links_are_extracted() -> None:
    result = extract_mechanical([
        TextSegment(
            id="segment-1",
            text="LinkedIn: linkedin.com/in/jane-example | GitHub: github.com/jane. Skills: Node.js/Express, GitHub",
            page_number=1,
        )
    ])

    links = result["literal_links"]
    assert [link["known_host"] for link in links] == ["linkedin", "github"]
    assert links[0]["value"] == "linkedin.com/in/jane-example"
    assert links[0]["normalized_url"] == "https://linkedin.com/in/jane-example"
    assert links[1]["value"] == "github.com/jane"


def test_postal_overlap_keeps_ambiguity() -> None:
    result = extract_mechanical([
        TextSegment(id="segment-1", text="Reference number 12345")
    ])

    assert result["postal_candidates"][0]["possible_country_codes"] == [
        "DE",
        "FR",
        "US",
    ]
