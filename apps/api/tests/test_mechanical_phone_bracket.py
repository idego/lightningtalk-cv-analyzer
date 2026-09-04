from cv_validator.analysis.source import TextSegment
from cv_validator.mechanical import extract_mechanical


def test_phone_keeps_bracketed_country_prefix() -> None:
    result = extract_mechanical([
        TextSegment(
            id="segment-1",
            text="Tel: (+48) 732070862, alt (0048) 501 234 567",
        )
    ])

    values = [phone["value"] for phone in result["phones"]]
    assert values == ["(+48) 732070862", "(0048) 501 234 567"]
    assert {phone["country_code"] for phone in result["phones"]} == {"PL"}
    assert result["phones"][0]["evidence"][0]["start_offset"] == 5
