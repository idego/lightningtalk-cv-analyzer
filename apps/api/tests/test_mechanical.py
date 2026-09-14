from cv_validator.analysis.source import SourceBlock, TextSegment
from cv_validator.mechanical import extract_mechanical, tag_link_sections


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


def _field(block_id: str) -> dict:
    return {"value": "x", "status": "supported", "evidence": [{"source_id": block_id}]}


def test_links_inside_record_sections_are_tagged() -> None:
    blocks = (
        SourceBlock("b-0", "Jane Example linkedin.com/in/jane github.com/jane", order=0),
        SourceBlock("b-1", "Experience", kind="section_header", order=1),
        SourceBlock("b-2", "Example Systems — Developer 2020-2024", order=2),
        SourceBlock("b-3", "Built a tool: github.com/jane/tool", order=3),
        SourceBlock("b-4", "Education", kind="section_header", order=4),
        SourceBlock("b-5", "Example University", order=5),
        SourceBlock("b-6", "Certificates", kind="section_header", order=6),
        SourceBlock("b-7", "AWS Certified: https://credly.com/badges/1", order=7),
        SourceBlock("b-8", "Links", kind="section_header", order=8),
        SourceBlock("b-9", "Portfolio https://jane.dev", order=9),
    )
    employment = [{"organization": _field("b-2"), "role": None}]
    education = [
        {"institution": _field("b-5"), "certificate": None},
        {"institution": None, "certificate": _field("b-7")},
    ]
    links = extract_mechanical(blocks)["literal_links"]

    tagged = tag_link_sections(links, blocks, employment, education)

    assert [(link["known_host"], link["section"]) for link in tagged] == [
        ("linkedin", None),
        ("github", None),
        ("github", "employment"),
        ("personal", "certification"),
        ("personal", None),
    ]


def test_postal_overlap_keeps_ambiguity() -> None:
    result = extract_mechanical([
        TextSegment(id="segment-1", text="Reference number 12345")
    ])

    assert result["postal_candidates"][0]["possible_country_codes"] == [
        "DE",
        "FR",
        "US",
    ]
