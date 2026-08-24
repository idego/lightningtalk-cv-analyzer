import json

import pytest

from cv_validator.ai.config import AISettings
from cv_validator.ai.application import analyze_report_with_ai, run_document_analysis
from cv_validator.ai.application import DocumentAnalyzerTimeoutError
from cv_validator.ai.domain import (
    AIAnalysisStatus,
    AIFailureReason,
    DocumentAnalyzerResponse,
)
from cv_validator.ai.request import (
    DETERMINISTIC_OBSERVATIONS_VERSION,
    build_document_analysis_request,
)
from cv_validator.ai.validation import (
    DocumentAnalysisValidationError,
    validate_document_analysis_response,
)
from cv_validator.extraction.deterministic import analyze_deterministically
from cv_validator.config import load_weights
from cv_validator.ingestion import RawDocument, SourcePage
from cv_validator.ingestion.redaction import redact_national_ids
from cv_validator.scoring.engine import score_deterministic
from cv_validator.serialization import serialize_report_payload


def _documents():
    raw = RawDocument(
        pages=(
            SourcePage(
                "page-0001",
                1,
                (
                    "Alex Example\n"
                    "Current location: Berlin, Germany\n"
                    "Phone: +49 30 123456\n"
                    "Experience\nEngineer"
                ),
            ),
            SourcePage("page-0002", 2, "Education\nExample University"),
        ),
        source_format="pdf",
    )
    return raw, redact_national_ids(raw)


def _valid_response() -> dict:
    check_ids = (
        "contact",
        "education",
        "employment",
        "timeline",
        "duration_claims",
        "relationships",
        "document_quality",
        "protected_boundaries",
    )
    return {
        "schema_version": "document-analysis-schema-v3",
        "facts": {
            "contact": [],
            "education": [
                {
                    "kind": "education",
                    "institution": "Example University",
                    "program": None,
                    "study_dates": None,
                    "status": "present",
                    "authority": "ai",
                    "source": "document_analyzer",
                    "evidence": [
                        {
                            "page_id": "page-0002",
                            "excerpt": "Example University",
                        }
                    ],
                }
            ],
            "employment": [],
        },
        "findings": [],
        "unknowns": [],
        "research_candidates": [],
        "checklist": [
            {"id": check_id, "checked": True, "issue_count": 0}
            for check_id in check_ids
        ],
        "analysis_limitations": ["Only literal CV content was analyzed."],
    }


def _malformed_response(kind: str):
    if kind == "root-array":
        return ["PRIVATE CANDIDATE TEXT"]
    response = _valid_response()
    if kind == "page-id-array":
        response["facts"]["education"][0]["evidence"][0]["page_id"] = []
    elif kind == "excerpt-array":
        response["facts"]["education"][0]["evidence"][0]["excerpt"] = []
    elif kind == "facts-array":
        response["facts"] = ["PRIVATE CANDIDATE TEXT"]
    else:  # pragma: no cover - test helper misuse
        raise AssertionError(f"unknown malformed response kind: {kind}")
    return response


def _response_with_valid_research_candidate() -> dict:
    response = _valid_response()
    response["research_candidates"] = [
        {
            "category": "education_or_certification",
            "query_subject": "Example University",
            "question": "Confirm the institution's public details.",
            "authority": "ai",
            "source": "document_analyzer",
            "evidence": {
                "page_id": "page-0002",
                "excerpt": "Example University",
            },
        }
    ]
    return response


class FakeDocumentAnalyzer:
    def __init__(self, response: DocumentAnalyzerResponse) -> None:
        self.response = response
        self.requests = []

    def analyze(self, request):
        self.requests.append(request)
        return self.response


class TimeoutDocumentAnalyzer:
    def analyze(self, request):
        raise DocumentAnalyzerTimeoutError()


def test_request_builder_accepts_only_redacted_page_aware_documents() -> None:
    raw, redacted = _documents()
    deterministic = analyze_deterministically(redacted, "1.0.0")
    settings = AISettings(enabled=True, api_key="test-key")

    with pytest.raises(TypeError, match="RedactedDocument"):
        build_document_analysis_request(settings, raw, deterministic)  # type: ignore[arg-type]

    request = build_document_analysis_request(settings, redacted, deterministic)
    payload = request.openai_payload
    input_text = payload["input"][0]["content"][0]["text"]

    assert request.page_ids == ("page-0001", "page-0002")
    assert "<!-- page: page-0001 -->" in input_text
    assert "<!-- page: page-0002 -->" in input_text
    assert DETERMINISTIC_OBSERVATIONS_VERSION in input_text
    assert json.dumps(
        deterministic.to_dict()["observations"],
        ensure_ascii=False,
        sort_keys=True,
    ) in input_text
    assert payload["model"] == "gpt-5.6-luna"
    assert payload["reasoning"] == {"effort": "medium"}
    assert payload["tools"] == []
    assert payload["store"] is False
    assert payload["max_output_tokens"] == settings.max_output_tokens
    assert payload["text"]["format"]["strict"] is True
    assert "previous_response_id" not in payload
    assert "conversation" not in payload
    assert request.timeout_seconds == 120.0
    assert request.max_retries == 0


def test_validator_requires_exact_excerpt_on_the_cited_page() -> None:
    _, redacted = _documents()
    response = _valid_response()

    validated = validate_document_analysis_response(response, redacted)

    assert validated.payload["facts"]["education"][0]["institution"] == (
        "Example University"
    )

    response["facts"]["education"][0]["evidence"][0]["page_id"] = "page-0001"
    with pytest.raises(DocumentAnalysisValidationError, match="exact excerpt"):
        validate_document_analysis_response(response, redacted)


@pytest.mark.parametrize(
    ("mutate", "error_kind"),
    (
        (
            lambda result: result["research_candidates"].append(
                {
                    "category": "people_search",
                    "query_subject": "Alex Example",
                    "question": "Find this person",
                }
            ),
            "schema",
        ),
        (lambda result: result.update({"score": 87}), "schema"),
        (
            lambda result: result["analysis_limitations"].append(
                "The candidate's nationality is inferred from their name."
            ),
            "protected boundary",
        ),
    ),
)
def test_validator_rejects_research_verdict_and_demographic_outputs(
    mutate,
    error_kind,
) -> None:
    _, redacted = _documents()
    response = _valid_response()
    mutate(response)

    with pytest.raises(DocumentAnalysisValidationError, match=error_kind):
        validate_document_analysis_response(response, redacted)


@pytest.mark.parametrize(
    "authored_conclusion",
    (
        "The candidate is Polish based on their name.",
        "The candidate is Asian based on their name.",
        "Do not interview this candidate.",
    ),
)
def test_validator_rejects_proxy_inferences_and_hiring_decisions(
    authored_conclusion,
) -> None:
    _, redacted = _documents()
    response = _valid_response()
    response["analysis_limitations"] = [authored_conclusion]

    with pytest.raises(
        DocumentAnalysisValidationError,
        match="protected boundary",
    ):
        validate_document_analysis_response(response, redacted)


def test_validator_allows_protected_word_inside_literal_entity_and_evidence() -> None:
    raw = RawDocument(
        pages=(
            SourcePage(
                "page-0001",
                1,
                "Alex Example\nEducation\nOrigin University",
            ),
        ),
        source_format="pdf",
    )
    redacted = redact_national_ids(raw)
    response = _valid_response()
    education = response["facts"]["education"][0]
    education["institution"] = "Origin University"
    education["evidence"] = [
        {"page_id": "page-0001", "excerpt": "Origin University"}
    ]

    validated = validate_document_analysis_response(response, redacted)

    assert validated.payload["facts"]["education"][0]["institution"] == (
        "Origin University"
    )


@pytest.mark.parametrize(
    ("field", "bad_value", "expected_error"),
    (
        ("category", "people_search", "schema"),
        ("authority", "code", "schema"),
        ("source", "web_search", "schema"),
        ("evidence", [], "schema"),
        ("evidence.page_id", "page-9999", "exact excerpt"),
        ("evidence.excerpt", "invented excerpt", "exact excerpt"),
    ),
    ids=(
        "category",
        "authority",
        "source",
        "evidence-shape",
        "evidence-page",
        "evidence-excerpt",
    ),
)
def test_research_candidate_mutations_fail_closed_with_safe_diagnostics(
    field,
    bad_value,
    expected_error,
) -> None:
    _, redacted = _documents()
    response = _response_with_valid_research_candidate()
    validate_document_analysis_response(response, redacted)
    candidate = response["research_candidates"][0]
    if field.startswith("evidence."):
        candidate["evidence"][field.removeprefix("evidence.")] = bad_value
    else:
        candidate[field] = bad_value

    with pytest.raises(DocumentAnalysisValidationError) as captured:
        validate_document_analysis_response(response, redacted)

    assert str(captured.value) == (
        f"AI document analysis response failed validation: {expected_error}"
    )
    assert "Example University" not in str(captured.value)


def test_application_boundary_is_disabled_no_call_and_preserves_deterministic_bytes(
    location_resolver,
) -> None:
    _, redacted = _documents()
    deterministic = analyze_deterministically(
        redacted,
        "1.0.0",
        location_resolver=location_resolver,
    )
    report = score_deterministic(deterministic, load_weights())
    before = json.dumps(
        serialize_report_payload(report),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    analyzer = FakeDocumentAnalyzer(
        DocumentAnalyzerResponse(
            payload=_valid_response(),
            response_model="gpt-5.6-luna-runtime",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
    )

    composed = analyze_report_with_ai(
        AISettings(),
        analyzer,
        redacted,
        report,
    )

    after = json.dumps(
        serialize_report_payload(composed.deterministic_report),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert composed.ai_outcome.status is AIAnalysisStatus.DISABLED
    assert analyzer.requests == []
    assert report.deterministic is not None
    assert report.deterministic.facts
    assert report.deterministic.scoring_signals
    assert report.findings
    assert composed.deterministic_report.score == report.score
    assert composed.deterministic_report.band is report.band
    assert composed.deterministic_report.deterministic.facts == (
        report.deterministic.facts
    )
    assert composed.deterministic_report.deterministic.scoring_signals == (
        report.deterministic.scoring_signals
    )
    assert composed.deterministic_report.findings == report.findings
    assert after == before


@pytest.mark.parametrize(
    ("outcome_kind", "expected_status", "expected_failure"),
    (
        ("success", AIAnalysisStatus.SUCCEEDED, None),
        (
            "invalid",
            AIAnalysisStatus.FAILED,
            AIFailureReason.INVALID_RESPONSE,
        ),
        ("timeout", AIAnalysisStatus.FAILED, AIFailureReason.TIMEOUT),
        ("refusal", AIAnalysisStatus.FAILED, AIFailureReason.REFUSAL),
    ),
)
def test_composer_preserves_deterministic_bytes_for_every_enabled_outcome(
    outcome_kind,
    expected_status,
    expected_failure,
    location_resolver,
) -> None:
    _, redacted = _documents()
    deterministic = analyze_deterministically(
        redacted,
        "1.0.0",
        location_resolver=location_resolver,
    )
    report = score_deterministic(deterministic, load_weights())
    before = json.dumps(
        serialize_report_payload(report),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if outcome_kind == "success":
        analyzer = FakeDocumentAnalyzer(
            DocumentAnalyzerResponse(
                payload=_valid_response(),
                response_model="gpt-5.6-luna-runtime",
                usage={"input_tokens": 10, "output_tokens": 5},
            )
        )
    elif outcome_kind == "invalid":
        invalid = _valid_response()
        invalid["facts"]["education"][0]["evidence"][0]["excerpt"] = "invented"
        analyzer = FakeDocumentAnalyzer(
            DocumentAnalyzerResponse(
                payload=invalid,
                response_model="gpt-5.6-luna-runtime",
                usage={"input_tokens": 10, "output_tokens": 5},
            )
        )
    elif outcome_kind == "timeout":
        analyzer = TimeoutDocumentAnalyzer()
    else:
        analyzer = FakeDocumentAnalyzer(
            DocumentAnalyzerResponse(
                payload=None,
                response_model="gpt-5.6-luna-runtime",
                usage={"input_tokens": 10, "output_tokens": 0},
                refused=True,
            )
        )

    composed = analyze_report_with_ai(
        AISettings(enabled=True, api_key="test-key"),
        analyzer,
        redacted,
        report,
    )
    after = json.dumps(
        serialize_report_payload(composed.deterministic_report),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    assert report.deterministic is not None
    assert report.deterministic.facts
    assert report.deterministic.scoring_signals
    assert report.findings
    assert after == before
    assert composed.deterministic_report.score == report.score
    assert composed.deterministic_report.band is report.band
    assert composed.deterministic_report.deterministic.facts == (
        report.deterministic.facts
    )
    assert composed.deterministic_report.deterministic.scoring_signals == (
        report.deterministic.scoring_signals
    )
    assert composed.deterministic_report.findings == report.findings
    assert composed.ai_outcome.status is expected_status
    assert composed.ai_outcome.failure_reason is expected_failure


def test_application_boundary_accepts_valid_fake_response_and_records_actual_model() -> None:
    _, redacted = _documents()
    deterministic = analyze_deterministically(redacted, "1.0.0")
    analyzer = FakeDocumentAnalyzer(
        DocumentAnalyzerResponse(
            payload=_valid_response(),
            response_model="gpt-5.6-luna-runtime",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
    )

    outcome = run_document_analysis(
        AISettings(enabled=True, api_key="test-key"),
        analyzer,
        redacted,
        deterministic,
    )

    assert outcome.status is AIAnalysisStatus.SUCCEEDED
    assert outcome.response_model == "gpt-5.6-luna-runtime"
    assert outcome.usage == {"input_tokens": 10, "output_tokens": 5}
    assert outcome.analysis is not None
    assert len(analyzer.requests) == 1


def test_application_boundary_converts_invalid_fake_response_to_safe_failure() -> None:
    _, redacted = _documents()
    deterministic = analyze_deterministically(redacted, "1.0.0")
    invalid = _valid_response()
    invalid["facts"]["education"][0]["evidence"][0]["excerpt"] = "invented"
    analyzer = FakeDocumentAnalyzer(
        DocumentAnalyzerResponse(
            payload=invalid,
            response_model="gpt-5.6-luna-runtime",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
    )

    outcome = run_document_analysis(
        AISettings(enabled=True, api_key="test-key"),
        analyzer,
        redacted,
        deterministic,
    )

    assert outcome.status is AIAnalysisStatus.FAILED
    assert outcome.failure_reason is AIFailureReason.INVALID_RESPONSE
    assert outcome.analysis is None
    assert outcome.response_model == "gpt-5.6-luna-runtime"


@pytest.mark.parametrize(
    "kind",
    ("root-array", "page-id-array", "excerpt-array", "facts-array"),
)
def test_application_boundary_converts_wrong_type_payloads_to_safe_failure(
    kind,
) -> None:
    _, redacted = _documents()
    deterministic = analyze_deterministically(redacted, "1.0.0")
    payload = _malformed_response(kind)
    analyzer = FakeDocumentAnalyzer(
        DocumentAnalyzerResponse(
            payload=payload,  # type: ignore[arg-type]
            response_model="gpt-5.6-luna-runtime",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
    )

    outcome = run_document_analysis(
        AISettings(enabled=True, api_key="test-key"),
        analyzer,
        redacted,
        deterministic,
    )

    assert outcome.status is AIAnalysisStatus.FAILED
    assert outcome.failure_reason is AIFailureReason.INVALID_RESPONSE
    assert outcome.analysis is None


def test_malformed_response_error_is_generic_and_contains_no_payload_text() -> None:
    _, redacted = _documents()

    with pytest.raises(DocumentAnalysisValidationError) as captured:
        validate_document_analysis_response(
            ["PRIVATE CANDIDATE TEXT"],  # type: ignore[arg-type]
            redacted,
        )

    assert str(captured.value) == (
        "AI document analysis response failed validation: schema"
    )
    assert "PRIVATE CANDIDATE TEXT" not in str(captured.value)


def test_application_boundary_converts_timeout_and_refusal_to_safe_failures() -> None:
    _, redacted = _documents()
    deterministic = analyze_deterministically(redacted, "1.0.0")
    settings = AISettings(enabled=True, api_key="test-key")

    timeout = run_document_analysis(
        settings,
        TimeoutDocumentAnalyzer(),
        redacted,
        deterministic,
    )
    refusal = run_document_analysis(
        settings,
        FakeDocumentAnalyzer(
            DocumentAnalyzerResponse(
                payload=None,
                response_model="gpt-5.6-luna-runtime",
                usage={"input_tokens": 10, "output_tokens": 0},
                refused=True,
            )
        ),
        redacted,
        deterministic,
    )

    assert timeout.status is AIAnalysisStatus.FAILED
    assert timeout.failure_reason is AIFailureReason.TIMEOUT
    assert refusal.status is AIAnalysisStatus.FAILED
    assert refusal.failure_reason is AIFailureReason.REFUSAL
