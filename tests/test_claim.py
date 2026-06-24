from cv_validator.extraction.claim import identify_claim
from cv_validator.ingestion.regions import split_contact_and_body
from cv_validator.ingestion import ParsedCV


def _parsed(text: str) -> ParsedCV:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    contact, body = split_contact_and_body(lines)
    return ParsedCV(tuple(lines), tuple(contact), tuple(body), "text")


def test_claim_present():
    claim = identify_claim(
        _parsed(
            """Jane Doe
Berlin, Germany
+49 30 12345678

Experience
Engineer
"""
        )
    )
    assert claim.raw == "Berlin, Germany"
    assert claim.country_code == "DE"
    assert claim.confidence == "high"


def test_claim_undetermined():
    claim = identify_claim(_parsed("Jane Doe\nSoftware Engineer\n\nExperience\nAcme"))
    assert claim.confidence == "undetermined"
    assert claim.country_code is None
