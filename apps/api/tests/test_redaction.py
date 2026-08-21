import pytest

from cv_validator.domain import CandidateKind
from cv_validator.extraction.deterministic import analyze_deterministically
from cv_validator.ingestion import RawDocument, SourcePage
from cv_validator.ingestion.redaction import MASK_CHARACTER, redact_national_ids
from cv_validator.ingestion.text import to_page_markdown
from cv_validator.pipeline import analyze_cv_text_result


def _raw(*page_texts: str) -> RawDocument:
    return RawDocument(
        pages=tuple(
            SourcePage(f"page-{number:04d}", number, text)
            for number, text in enumerate(page_texts, start=1)
        ),
        source_format="text",
    )


def test_masks_every_national_id_with_same_length_and_offsets():
    first_id = "123" + "-45-" + "6789"
    second_id = "AB" + "123456" + "C"
    raw = _raw("Alpha bravo charlie delta echo", f"SSN: {first_id}\nNINO: {second_id}")

    redacted = redact_national_ids(raw)

    assert len(redacted.redactions) == 2
    for redaction in redacted.redactions:
        page = redacted.pages[redaction.page_number - 1]
        masked = page.text[redaction.start_offset : redaction.end_offset]
        assert masked == MASK_CHARACTER * (redaction.end_offset - redaction.start_offset)
    assert first_id not in redacted.markdown
    assert second_id not in redacted.markdown


def test_labeled_incomplete_id_is_masked_defensively():
    incomplete_id = "12" + "-34-" + "5"
    redacted = redact_national_ids(
        _raw(f"Alpha bravo charlie delta echo\nNational ID: {incomplete_id}")
    )

    assert len(redacted.redactions) == 1
    assert redacted.redactions[0].type_hints == ("LABELED_NATIONAL_ID",)
    assert incomplete_id not in redacted.pages[0].text


def test_labeled_id_longer_than_fifteen_digits_is_never_partially_revealed():
    raw_id = "1234567890123456"
    redacted = redact_national_ids(
        _raw(f"Alpha bravo charlie delta echo\nNational ID: {raw_id}")
    )

    assert raw_id not in redacted.pages[0].text
    assert redacted.pages[0].text.endswith(MASK_CHARACTER * len(raw_id))
    assert redacted.redactions[-1].end_offset == len(redacted.pages[0].text)


@pytest.mark.parametrize(
    "raw_id",
    (
        "ABC123456",
        "ABC123456789XYZ987654321",
        "AB 12-34 56-CD",
        "PL-ABC 12-34/56.XYZ",
    ),
)
def test_labeled_alphanumeric_id_masks_the_complete_remaining_line(raw_id):
    prefix = "Alpha bravo charlie delta echo\nNational ID: "
    redacted = redact_national_ids(_raw(prefix + raw_id))

    redaction = redacted.redactions[-1]
    page = redacted.pages[0]
    masked = page.text[redaction.start_offset : redaction.end_offset]

    assert page.text[: redaction.start_offset] == prefix
    assert redaction.end_offset == len(page.text)
    assert masked == MASK_CHARACTER * len(raw_id)
    assert raw_id not in page.text
    assert raw_id not in redacted.markdown


def test_unlabelled_invalid_eleven_digits_are_not_masked_as_generic_id():
    phone_like_value = "481" + "234" + "56789"
    raw = _raw(f"Alpha bravo charlie delta echo\n{phone_like_value}")

    redacted = redact_national_ids(raw)

    assert redacted.redactions == ()
    assert phone_like_value in redacted.pages[0].text


def test_valid_unlabelled_pesel_is_masked_before_phone_extraction():
    pesel = "440" + "514" + "01458"
    redacted = redact_national_ids(
        _raw(f"Alpha bravo charlie delta echo\n{pesel}")
    )

    result = analyze_deterministically(redacted, "1.0.0")

    assert redacted.redactions[0].type_hints == ("PL_PESEL",)
    assert not any(
        candidate.kind is CandidateKind.PHONE
        for candidate in result.candidates
    )


def test_national_id_candidate_contains_only_safe_value_and_redacted_evidence():
    raw_id = "123" + "-45-" + "6789"
    redacted = redact_national_ids(
        _raw(f"Alpha bravo charlie delta echo\nSSN: {raw_id}")
    )

    result = analyze_deterministically(redacted, "1.0.0")
    candidate = next(
        candidate
        for candidate in result.candidates
        if candidate.kind is CandidateKind.NATIONAL_ID
    )

    assert candidate.value.startswith("present:")
    assert raw_id not in candidate.value
    assert set(candidate.provenance.evidence[0].excerpt) == {MASK_CHARACTER}


def test_raw_document_cannot_be_formatted_as_markdown():
    raw = _raw("Alpha bravo charlie delta echo")

    assert not hasattr(raw, "markdown")
    with pytest.raises(TypeError, match="redacted"):
        to_page_markdown(raw)  # type: ignore[arg-type]


def test_redacted_identity_is_stable_and_page_boundary_sensitive():
    first = redact_national_ids(_raw("Alpha bravo", "charlie delta echo"))
    second = redact_national_ids(_raw("Alpha bravo", "charlie delta echo"))
    different_boundaries = redact_national_ids(
        _raw("Alpha bravo\ncharlie delta echo")
    )

    assert first.identity == second.identity
    assert first.identity.digest != different_boundaries.identity.digest
    assert first.identity.algorithm == "sha256"
    assert first.identity.format_version == "v1"


def test_same_length_raw_ids_produce_the_same_redacted_identity():
    first_id = "ABC123456789XYZ"
    second_id = "XYZ987654321ABC"

    first = analyze_cv_text_result(
        f"Alpha bravo charlie delta echo\nNational ID: {first_id}"
    )
    second = analyze_cv_text_result(
        f"Alpha bravo charlie delta echo\nNational ID: {second_id}"
    )

    assert len(first_id) == len(second_id)
    assert first.document_identity == second.document_identity
    assert first_id not in repr(first)
    assert second_id not in repr(second)


def test_raw_national_id_is_absent_from_repr_report_and_logs(caplog):
    raw_id = "ABC123456789XYZ987654321"
    raw = _raw(f"Alpha bravo charlie delta echo\nSSN: {raw_id}")

    result = analyze_cv_text_result(raw.pages[0].text)

    assert raw_id not in repr(raw)
    assert raw_id not in repr(result)
    assert raw_id not in str(result.report.to_dict())
    assert raw_id not in caplog.text
