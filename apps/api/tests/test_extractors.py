from cv_validator.config import load_weights
from cv_validator.extraction.claim import identify_claim
from cv_validator.extraction.signals import extract_all_signals
from cv_validator.ingestion import ParsedCV
from cv_validator.ingestion.redaction import redact_national_ids
from cv_validator.ingestion.regions import split_contact_and_body


def _parsed(text: str) -> ParsedCV:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    contact, body = split_contact_and_body(lines)
    return ParsedCV(tuple(lines), tuple(contact), tuple(body), "text")


def test_phone_extractor_strong():
    weights = load_weights()
    parsed = _parsed(
        """Jane\nBerlin, Germany\n+1 415 555 0100\n\nExperience\n"""
    )
    claim = identify_claim(parsed)
    signals = extract_all_signals(parsed, claim, weights)
    phone = next(s for s in signals if s.name == "phone_country")
    assert phone.inferred_country == "US"
    assert phone.direction.value == "conflicts"


def test_national_id_redaction_in_metadata():
    weights = load_weights()
    raw_id = "123" + "-45-" + "6789"
    parsed = redact_national_ids(_parsed(f"Jane\nBerlin\n{raw_id}\n\nExperience\n"))
    claim = identify_claim(parsed)
    signals = extract_all_signals(parsed, claim, weights)
    nid = next(s for s in signals if s.name == "national_id")
    assert nid.metadata["present"] is True
    assert "123" not in nid.observed


def test_right_to_work_surfaced():
    weights = load_weights()
    parsed = _parsed("Jane\nBerlin\nEligible to work in Germany\n\nExperience\n")
    claim = identify_claim(parsed)
    signals = extract_all_signals(parsed, claim, weights)
    assert any(s.name == "right_to_work" for s in signals)
