import json

import pytest

from cv_validator.ai.config import AISettings
from cv_validator.ai.application import analyze_report_with_ai, run_document_analysis
from cv_validator.ai.application import (
    DocumentAnalyzerClientError,
    DocumentAnalyzerTimeoutError,
)
from cv_validator.ai.domain import (
    AIAnalysisStatus,
    AIFailureReason,
    DocumentAnalyzerResponse,
)
from cv_validator.ai.request import (
    DETERMINISTIC_OBSERVATIONS_VERSION,
    SCHEMA_VERSION,
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
    return {
        "schema_version": SCHEMA_VERSION,
        "facts": {
            "contact": [],
            "education": [
                {
                    "kind": "education",
                    "institution": {
                        "value": "Example University",
                        "line_ids": ["page-0002-line-0002"],
                    },
                    "program": {"value": None, "line_ids": []},
                    "study_dates": {"value": None, "line_ids": []},
                    "status": "present",
                }
            ],
            "employment": [],
        },
        "findings": [],
        "unknowns": [],
        "analysis_limitations": ["Only literal CV content was analyzed."],
    }


def _malformed_response(kind: str):
    if kind == "root-array":
        return ["PRIVATE CANDIDATE TEXT"]
    response = _valid_response()
    if kind == "page-id-array":
        response["facts"]["education"][0]["institution"]["line_ids"] = [[]]
    elif kind == "line-id-array":
        response["facts"]["education"][0]["institution"]["line_ids"] = [[]]
    elif kind == "facts-array":
        response["facts"] = ["PRIVATE CANDIDATE TEXT"]
    else:  # pragma: no cover - test helper misuse
        raise AssertionError(f"unknown malformed response kind: {kind}")
    return response


def _field(value: str | None, *line_ids: str) -> dict:
    return {"value": value, "line_ids": list(line_ids)}


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


class SequenceDocumentAnalyzer:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.requests = []

    def analyze(self, request):
        self.requests.append(request)
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _prompt_instructions() -> str:
    _, redacted = _documents()
    deterministic = analyze_deterministically(redacted, "1.0.0")
    return build_document_analysis_request(
        AISettings(enabled=True, api_key="test-key"),
        redacted,
        deterministic,
    ).openai_payload["instructions"]


def test_document_analysis_retries_transport_then_invalid_with_absolute_cap() -> None:
    _, redacted = _documents()
    deterministic = analyze_deterministically(redacted, "1.0.0")
    valid = DocumentAnalyzerResponse(
        payload=_valid_response(),
        response_model="gpt-5.6-luna-runtime",
        usage={"input_tokens": 10, "output_tokens": 5},
    )
    analyzer = SequenceDocumentAnalyzer(
        [
            DocumentAnalyzerTimeoutError(),
            DocumentAnalyzerResponse(
                payload=["invalid"],
                response_model="gpt-5.6-luna-runtime",
                usage={"input_tokens": 10, "output_tokens": 2},
            ),
            valid,
        ]
    )

    outcome = run_document_analysis(
        AISettings(enabled=True, api_key="test-key"),
        analyzer,
        redacted,
        deterministic,
    )

    assert outcome.status is AIAnalysisStatus.SUCCEEDED
    assert outcome.attempt_count == 3
    assert len(analyzer.requests) == 3
    assert outcome.usage == {"input_tokens": 20, "output_tokens": 7}


def test_non_retryable_client_error_stops_after_one_safe_attempt() -> None:
    _, redacted = _documents()
    deterministic = analyze_deterministically(redacted, "1.0.0")
    analyzer = SequenceDocumentAnalyzer(
        [
            DocumentAnalyzerClientError(
                retryable=False,
                http_status_class="4xx",
                provider_request_id="req-safe-123",
            ),
            AssertionError("must not retry"),
        ]
    )

    outcome = run_document_analysis(
        AISettings(enabled=True, api_key="test-key"),
        analyzer,
        redacted,
        deterministic,
    )

    assert outcome.status is AIAnalysisStatus.FAILED
    assert outcome.failure_reason is AIFailureReason.CLIENT_ERROR
    assert outcome.failure_stage == "transport"
    assert outcome.retryable is False
    assert outcome.http_status_class == "4xx"
    assert outcome.provider_request_id == "req-safe-123"
    assert outcome.attempt_count == 1
    assert len(analyzer.requests) == 1


def test_invalid_then_non_retryable_client_error_keeps_accumulated_usage() -> None:
    _, redacted = _documents()
    deterministic = analyze_deterministically(redacted, "1.0.0")
    analyzer = SequenceDocumentAnalyzer(
        [
            DocumentAnalyzerResponse(
                payload=["invalid"],
                response_model="gpt-5.6-luna-runtime",
                usage={"input_tokens": 11, "output_tokens": 3},
            ),
            DocumentAnalyzerClientError(
                retryable=False,
                http_status_class="4xx",
                provider_request_id="req-safe-final",
            ),
        ]
    )

    outcome = run_document_analysis(
        AISettings(enabled=True, api_key="test-key"),
        analyzer,
        redacted,
        deterministic,
    )

    assert outcome.status is AIAnalysisStatus.FAILED
    assert outcome.failure_reason is AIFailureReason.CLIENT_ERROR
    assert outcome.attempt_count == 2
    assert outcome.usage == {"input_tokens": 11, "output_tokens": 3}


def test_invalid_then_timeout_keeps_accumulated_usage() -> None:
    _, redacted = _documents()
    deterministic = analyze_deterministically(redacted, "1.0.0")
    analyzer = SequenceDocumentAnalyzer(
        [
            DocumentAnalyzerResponse(
                payload=["invalid"],
                response_model="gpt-5.6-luna-runtime",
                usage={"input_tokens": 13, "output_tokens": 4},
            ),
            DocumentAnalyzerTimeoutError(),
            DocumentAnalyzerTimeoutError(),
        ]
    )

    outcome = run_document_analysis(
        AISettings(enabled=True, api_key="test-key"),
        analyzer,
        redacted,
        deterministic,
    )

    assert outcome.status is AIAnalysisStatus.FAILED
    assert outcome.failure_reason is AIFailureReason.TIMEOUT
    assert outcome.attempt_count == 3
    assert outcome.usage == {"input_tokens": 13, "output_tokens": 4}


def test_invalid_response_retry_is_bounded_and_diagnostics_contain_no_payload() -> None:
    _, redacted = _documents()
    deterministic = analyze_deterministically(redacted, "1.0.0")
    invalid = DocumentAnalyzerResponse(
        payload=["PRIVATE MODEL OUTPUT"],
        response_model="gpt-5.6-luna-runtime",
        usage={"input_tokens": 10, "output_tokens": 2},
    )
    analyzer = SequenceDocumentAnalyzer([invalid, invalid])

    outcome = run_document_analysis(
        AISettings(enabled=True, api_key="test-key"),
        analyzer,
        redacted,
        deterministic,
    )

    assert outcome.status is AIAnalysisStatus.FAILED
    assert outcome.failure_reason is AIFailureReason.INVALID_RESPONSE
    assert outcome.failure_stage == "schema"
    assert outcome.attempt_count == 2
    assert len(analyzer.requests) == 2
    assert "PRIVATE" not in repr(outcome)


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
    assert "<!-- line: page-0001-line-0001 -->" in input_text
    assert "<!-- line: page-0002-line-0002 -->" in input_text
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
    assert "Prompt version:" not in payload["instructions"]
    assert "Schema version:" not in payload["instructions"]
    assert "Input contract:" not in payload["instructions"]
    assert "previous_response_id" not in payload
    assert "conversation" not in payload
    assert request.timeout_seconds == 120.0
    assert request.max_retries == 0


def test_prompt_requires_a_final_evidence_and_relationship_audit() -> None:
    instructions = _prompt_instructions()

    assert "ensure each field's line IDs" in instructions
    assert "support that field's literal value" in instructions
    assert "relationship ambiguity" in instructions
    assert "internal fact conflicts" in instructions
    assert "model-only" in instructions
    assert "do not add authority, source, versions, excerpts" in instructions
    assert "research candidates" in instructions


def test_prompt_treats_missing_stated_location_as_neutral_completeness() -> None:
    instructions = " ".join(_prompt_instructions().split())

    assert "missing_contact_data" in instructions


def test_prompt_treats_an_unlabeled_header_phone_as_candidate_contact() -> None:
    instructions = " ".join(_prompt_instructions().split())

    assert "phone in the CV header or contact line" in instructions
    assert "even when it has no `Phone:` label or ownership statement" in instructions
    assert "Do not emit `missing_contact_data` merely because such a phone is unlabeled" in instructions
    assert "status `missing`" in instructions
    assert "`worth_knowing` or `remaining`" in instructions
    assert "never as suspicion or a score signal" in instructions


def test_prompt_defines_semantic_outlier_as_contextual_responsibility_mismatch() -> None:
    instructions = " ".join(_prompt_instructions().split())

    assert "materially unrelated" in instructions
    assert "specific surrounding role or context" in instructions
    assert "unusual technology alone is not enough" in instructions


def test_prompt_keeps_meaningful_concatenation_out_of_document_artifacts() -> None:
    instructions = " ".join(_prompt_instructions().split())

    assert "word concatenation whose meaning survives extraction" in instructions
    assert "never `document_artifact`" in instructions
    assert "literal malformed content" in instructions


def test_prompt_requires_structural_material_fields_for_every_finding() -> None:
    instructions = " ".join(_prompt_instructions().split())

    assert "For every finding, always return both `material_effect` and `affected_fact`" in instructions
    assert "`material_effect: none` and `affected_fact: not_applicable`" in instructions


def test_prompt_surfaces_explicit_education_outside_eu_as_neutral_context() -> None:
    instructions = " ".join(_prompt_instructions().split())

    assert "education_outside_eu" in instructions
    assert "worth_knowing" in instructions
    assert "does not establish nationality" in instructions
    assert "Candidate name must not affect this finding" in instructions


def test_education_outside_eu_finding_is_name_and_score_invariant(
    location_resolver,
) -> None:
    def analyze_named_cv(name: str):
        raw = RawDocument(
            pages=(
                SourcePage(
                    "page-0001",
                    1,
                    (
                        f"{name}\nCurrent location: Opole, Poland\n"
                        "Phone: +48 732 080 047\n45-061\n"
                        "Education\nCity University of Hong Kong"
                    ),
                ),
            ),
            source_format="docx",
        )
        redacted = redact_national_ids(raw)
        deterministic = analyze_deterministically(
            redacted,
            "1.0.0",
            location_resolver=location_resolver,
        )
        report = score_deterministic(deterministic, load_weights())
        response = _valid_response()
        response["facts"]["education"] = [
            {
                "kind": "education",
                "institution": _field(
                    "City University of Hong Kong",
                    "page-0001-line-0006",
                ),
                "program": _field(None),
                "study_dates": _field(None),
                "status": "present",
            }
        ]
        response["findings"] = [
            {
                "category": "education_outside_eu",
                "status": "observed",
                "observation": "The CV lists education in Hong Kong.",
                "reason": "This is international education history outside the EU.",
                "importance": "worth_knowing",
                "confidence": "high",
                "limitation": (
                    "This education record alone does not establish the "
                    "candidate's current location."
                ),
                "material_effect": "none",
                "affected_fact": "not_applicable",
                "evidence": [
                    {
                        "page_id": "page-0001",
                        "line_id": "page-0001-line-0006",
                    }
                ],
            }
        ]
        composed = analyze_report_with_ai(
            AISettings(enabled=True, api_key="test-key"),
            FakeDocumentAnalyzer(
                DocumentAnalyzerResponse(
                    payload=response,
                    response_model="gpt-5.6-luna-runtime",
                    usage={"input_tokens": 10, "output_tokens": 5},
                )
            ),
            redacted,
            report,
        )
        return composed

    first = analyze_named_cv("Alex Example")
    second = analyze_named_cv("Rhea Example")

    assert first.ai_outcome.status is AIAnalysisStatus.SUCCEEDED
    assert second.ai_outcome.status is AIAnalysisStatus.SUCCEEDED
    assert first.ai_outcome.analysis.payload["findings"] == (
        second.ai_outcome.analysis.payload["findings"]
    )
    assert first.ai_outcome.analysis.payload["findings"][0]["category"] == (
        "education_outside_eu"
    )
    assert first.deterministic_report.score == second.deterministic_report.score
    assert first.deterministic_report.band is second.deterministic_report.band


@pytest.mark.parametrize(
    ("material_effect", "affected_fact"),
    (("meaning_changed", "timeline"), ("none", "timeline")),
)
def test_validator_rejects_material_effect_on_non_document_artifact(
    material_effect: str,
    affected_fact: str,
) -> None:
    _, redacted = _documents()
    response = _valid_response()
    response["findings"] = [
        {
            "category": "timeline_overlap",
            "status": "unconfirmed",
            "observation": "Two roles overlap.",
            "reason": "The work periods overlap.",
            "importance": "worth_knowing",
            "confidence": "medium",
            "limitation": "The roles may have been part-time.",
            "material_effect": material_effect,
            "affected_fact": affected_fact,
            "evidence": [
                {"page_id": "page-0001", "line_id": "page-0001-line-0001"}
            ],
        }
    ]

    with pytest.raises(DocumentAnalysisValidationError, match="finding classification"):
        validate_document_analysis_response(response, redacted)


def test_validator_rejects_not_applicable_document_artifact_fact() -> None:
    raw = RawDocument(
        pages=(SourcePage("page-0001", 1, "Employment date: 20??-0?"),),
        source_format="text",
    )
    response = _valid_response()
    response["facts"]["education"] = []
    response["findings"] = [
        {
            "category": "document_artifact",
            "status": "unconfirmed",
            "observation": "The employment date is unreadable.",
            "reason": "Malformed characters block the date.",
            "importance": "worth_knowing",
            "confidence": "high",
            "limitation": "The original document must be checked.",
            "material_effect": "important_fact_unreadable",
            "affected_fact": "not_applicable",
            "evidence": [
                {"page_id": "page-0001", "line_id": "page-0001-line-0001"}
            ],
        }
    ]

    with pytest.raises(DocumentAnalysisValidationError, match="finding classification"):
        validate_document_analysis_response(response, redact_national_ids(raw))


def test_validator_suppresses_understandable_document_artifact_finding() -> None:
    raw = RawDocument(
        pages=(
            SourcePage(
                "page-0001",
                1,
                "Alex Example\nExperience\nSoftwareEngineer\nCurrent location: Berlin",
            ),
        ),
        source_format="text",
    )
    response = _valid_response()
    response["facts"]["education"] = []
    response["findings"] = [
        {
            "category": "document_artifact",
            "status": "unconfirmed",
            "observation": "Two words are joined in SoftwareEngineer.",
            "reason": "The spacing is malformed, but the job title remains understandable.",
            "importance": "worth_knowing",
            "confidence": "high",
            "limitation": "The meaning is still clear.",
            "material_effect": "important_fact_unreadable",
            "affected_fact": "employment",
            "evidence": [
                {"page_id": "page-0001", "line_id": "page-0001-line-0003"}
            ],
        }
    ]

    validated = validate_document_analysis_response(
        response, redact_national_ids(raw)
    )

    assert validated.payload["findings"] == []
    document_check = validated.payload["checklist"]["document_quality"]
    assert document_check["issue_count"] == 0


def test_validator_rejects_question_marker_classified_as_non_material_artifact() -> None:
    raw = RawDocument(
        pages=(
            SourcePage(
                "page-0001",
                1,
                "Alex Example\nQuestion?? Available to start in June: Yes\nSoftware engineer",
            ),
        ),
        source_format="text",
    )
    response = _valid_response()
    response["facts"]["education"] = []
    response["findings"] = [
        {
            "category": "document_artifact",
            "status": "unconfirmed",
            "observation": "The Question label contains two question marks.",
            "reason": "The answer and meaning remain clear.",
            "importance": "worth_knowing",
            "confidence": "high",
            "limitation": "No important fact is blocked.",
            "material_effect": "none",
            "affected_fact": "not_applicable",
            "evidence": [
                {"page_id": "page-0001", "line_id": "page-0001-line-0002"}
            ],
        }
    ]

    with pytest.raises(DocumentAnalysisValidationError, match="finding classification"):
        validate_document_analysis_response(response, redact_national_ids(raw))


def test_validator_keeps_meaning_blocking_document_artifact_finding() -> None:
    raw = RawDocument(
        pages=(
            SourcePage(
                "page-0001",
                1,
                "Alex Example\nEmployment date: 20??-0?\nCurrent location: Berlin",
            ),
        ),
        source_format="text",
    )
    response = _valid_response()
    response["facts"]["education"] = []
    response["findings"] = [
        {
            "category": "document_artifact",
            "status": "unconfirmed",
            "observation": "The employment date is unreadable.",
            "reason": "Malformed characters block the employment date fact.",
            "importance": "worth_knowing",
            "confidence": "high",
            "limitation": "The original document must be checked.",
            "material_effect": "important_fact_unreadable",
            "affected_fact": "employment_dates",
            "evidence": [
                {"page_id": "page-0001", "line_id": "page-0001-line-0002"}
            ],
        }
    ]

    validated = validate_document_analysis_response(
        response, redact_national_ids(raw)
    )

    assert [finding["category"] for finding in validated.payload["findings"]] == [
        "document_artifact"
    ]


def test_validator_materializes_exact_excerpt_on_the_cited_page() -> None:
    _, redacted = _documents()
    response = _valid_response()

    validated = validate_document_analysis_response(response, redacted)

    assert validated.payload["facts"]["education"][0]["institution"] == (
        "Example University"
    )
    assert validated.payload["facts"]["education"][0]["field_evidence"][
        "institution"
    ] == [
        {
            "page_id": "page-0002",
            "line_id": "page-0002-line-0002",
            "excerpt": "Example University",
        }
    ]

    response["facts"]["education"][0]["institution"]["line_ids"] = [
        "page-0001-line-0001"
    ]
    partial = validate_document_analysis_response(response, redacted)
    assert partial.payload["facts"]["education"] == []
    assert partial.payload["validation_warnings"]


def test_model_authored_excerpt_is_rejected_before_code_materialization() -> None:
    _, redacted = _documents()
    response = _valid_response()
    response["facts"]["education"][0]["institution"]["excerpt"] = (
        "Example University"
    )

    with pytest.raises(DocumentAnalysisValidationError, match="schema"):
        validate_document_analysis_response(response, redacted)


def test_existing_but_unrelated_source_line_cannot_support_a_fact() -> None:
    _, redacted = _documents()
    response = _valid_response()
    response["facts"]["education"][0]["institution"]["line_ids"] = [
        "page-0002-line-0001"
    ]
    partial = validate_document_analysis_response(response, redacted)
    assert partial.payload["facts"]["education"] == []
    assert partial.payload["validation_warnings"]


def test_model_contract_leaves_checklist_and_research_derivation_to_code() -> None:
    _, redacted = _documents()
    deterministic = analyze_deterministically(redacted, "1.0.0")
    settings = AISettings(enabled=True, api_key="test-key")

    request = build_document_analysis_request(settings, redacted, deterministic)
    schema = request.openai_payload["text"]["format"]["schema"]
    assert "checklist" not in schema["properties"]
    assert "research_candidates" not in schema["properties"]
    assert schema["$defs"]["factField"]["required"] == ["value", "line_ids"]


def test_every_strict_object_requires_every_declared_property() -> None:
    _, redacted = _documents()
    deterministic = analyze_deterministically(redacted, "1.0.0")
    request = build_document_analysis_request(
        AISettings(enabled=True, api_key="test-key"),
        redacted,
        deterministic,
    )

    def assert_strict_objects(schema_node: object, path: str = "$") -> None:
        if isinstance(schema_node, dict):
            properties = schema_node.get("properties")
            if isinstance(properties, dict):
                assert schema_node.get("additionalProperties") is False, path
                assert set(schema_node.get("required", [])) == set(properties), path
            for key, value in schema_node.items():
                assert_strict_objects(value, f"{path}.{key}")
        elif isinstance(schema_node, list):
            for index, value in enumerate(schema_node):
                assert_strict_objects(value, f"{path}[{index}]")

    assert_strict_objects(request.openai_payload["text"]["format"]["schema"])


def test_evidence_can_support_one_literal_value_split_across_source_lines() -> None:
    raw = RawDocument(
        pages=(
            SourcePage(
                "page-0001",
                1,
                "Education\nExample University\nMaster of\nComputer Science",
            ),
        ),
        source_format="pdf",
    )
    response = _valid_response()
    education = response["facts"]["education"][0]
    education["institution"] = _field("Example University", "page-0001-line-0002")
    education["program"] = _field(
        "Master of Computer Science",
        "page-0001-line-0002",
        "page-0001-line-0003",
        "page-0001-line-0004",
    )

    validated = validate_document_analysis_response(
        response,
        redact_national_ids(raw),
    )

    assert validated.payload["facts"]["education"][0]["program"] == (
        "Master of Computer Science"
    )


def test_multiline_semantic_value_ignores_flattened_parenthesis_spacing() -> None:
    raw = RawDocument(
        pages=(
            SourcePage(
                "page-0001",
                1,
                (
                    "Education\nExample University\n"
                    "Master of Computer Systems (\nDistributed Systems)"
                ),
            ),
        ),
        source_format="pdf",
    )
    response = _valid_response()
    education = response["facts"]["education"][0]
    education["institution"] = _field("Example University", "page-0001-line-0002")
    education["program"] = _field(
        "Master of Computer Systems (Distributed Systems)",
        "page-0001-line-0002",
        "page-0001-line-0003",
        "page-0001-line-0004",
    )

    validated = validate_document_analysis_response(
        response,
        redact_national_ids(raw),
    )

    assert validated.payload["facts"]["education"][0]["program"] == (
        "Master of Computer Systems (Distributed Systems)"
    )


def test_multiline_semantic_value_allows_interleaved_flattened_column_text() -> None:
    raw = RawDocument(
        pages=(
            SourcePage(
                "page-0001",
                1,
                (
                    "Education\n"
                    "Cloud work, Information Technology\n"
                    "pipeline text, Software Systems, Example University"
                ),
            ),
        ),
        source_format="pdf",
    )
    response = _valid_response()
    education = response["facts"]["education"][0]
    education["institution"] = _field("Example University", "page-0001-line-0003")
    education["program"] = _field(
        "Information Technology (Software Systems)",
        "page-0001-line-0002",
        "page-0001-line-0003",
    )

    validated = validate_document_analysis_response(
        response,
        redact_national_ids(raw),
    )

    assert validated.payload["facts"]["education"][0]["program"] == (
        "Information Technology (Software Systems)"
    )


def test_semantic_value_cannot_be_assembled_from_distant_source_lines() -> None:
    raw = RawDocument(
        pages=(
            SourcePage(
                "page-0001",
                1,
                (
                    "Example Org\nSenior\nunrelated\nData\nunrelated\n"
                    "Visualization\nunrelated\nEngineer"
                ),
            ),
        ),
        source_format="pdf",
    )
    response = _valid_response()
    response["facts"]["education"] = []
    response["facts"]["employment"] = [
        {
            "kind": "employment",
            "organization": _field("Example Org", "page-0001-line-0001"),
            "role": _field(
                "Senior Data Visualization Engineer",
                "page-0001-line-0001",
                "page-0001-line-0002",
                "page-0001-line-0004",
                "page-0001-line-0006",
                "page-0001-line-0008",
            ),
            "employment_dates": _field(None),
            "location": _field(None),
            "relationship_type": _field(None),
            "status": "present",
        }
    ]

    validated = validate_document_analysis_response(response, redact_national_ids(raw))
    assert validated.payload["facts"]["employment"] == []
    assert validated.payload["validation_warnings"]


def test_single_line_semantic_value_does_not_ignore_changed_punctuation() -> None:
    raw = RawDocument(
        pages=(SourcePage("page-0001", 1, "Example Org — Data Engineer"),),
        source_format="pdf",
    )
    response = _valid_response()
    response["facts"]["education"] = []
    response["facts"]["employment"] = [
        {
            "kind": "employment",
            "organization": _field("Example Org", "page-0001-line-0001"),
                "role": _field("Data-Engineer", "page-0001-line-0001"),
            "employment_dates": _field(None),
            "location": _field(None),
            "relationship_type": _field(None),
            "status": "present",
        }
    ]

    validated = validate_document_analysis_response(response, redact_national_ids(raw))
    assert validated.payload["facts"]["employment"] == []
    assert validated.payload["validation_warnings"]


def test_multiline_semantic_value_rejects_reordered_source_tokens() -> None:
    raw = RawDocument(
        pages=(
            SourcePage(
                "page-0001",
                1,
                "Example University, Software Systems\nInformation Technology",
            ),
        ),
        source_format="pdf",
    )
    response = _valid_response()
    education = response["facts"]["education"][0]
    education["institution"] = _field("Example University", "page-0001-line-0001")
    education["program"] = _field(
        "Information Technology Software Systems",
        "page-0001-line-0001",
        "page-0001-line-0002",
    )

    validated = validate_document_analysis_response(response, redact_national_ids(raw))
    assert validated.payload["facts"]["education"][0]["program"] is None
    assert validated.payload["validation_warnings"]


def test_checklist_issue_count_is_derived_from_findings() -> None:
    _, redacted = _documents()
    response = _valid_response()
    response["findings"] = [
        {
            "category": "timeline_overlap",
            "status": "conflicting",
            "observation": "Two entries overlap.",
            "reason": "The cited entries use overlapping dates.",
            "importance": "worth_knowing",
                "confidence": "medium",
                "limitation": "The document alone does not explain the overlap.",
                "material_effect": "none",
                "affected_fact": "not_applicable",
            "evidence": [
                {
                    "page_id": "page-0001",
                    "line_id": "page-0001-line-0002",
                }
            ],
        }
    ]
    validated = validate_document_analysis_response(response, redacted)
    assert validated.payload["findings"][0]["check_id"] == "timeline"
    assert validated.payload["checklist"]["timeline"] == {
        "checked": True,
        "issue_count": 1,
    }


def test_code_derives_research_candidates_only_from_accepted_facts() -> None:
    _, redacted = _documents()
    response = _valid_response()

    validated = validate_document_analysis_response(response, redacted)

    candidates = validated.payload["research_candidates"]
    assert candidates == [
        {
            "category": "education_or_certification",
            "query_subject": "Example University",
            "question": "Check the public institution and credential details.",
            "authority": "ai",
            "source": "document_analyzer",
            "evidence": {
                "page_id": "page-0002",
                "line_id": "page-0002-line-0002",
                "excerpt": "Example University",
            },
        }
    ]


def test_partial_field_validation_keeps_valid_finding_and_fact_fields() -> None:
    _, redacted = _documents()
    response = _valid_response()
    education = response["facts"]["education"][0]
    education["program"] = _field("Unsupported program", "page-0001-line-0001")
    response["findings"] = [
        {
            "category": "timeline_gap",
            "status": "unconfirmed",
            "observation": "A timeline detail needs review.",
            "reason": "The cited work history is incomplete.",
            "importance": "worth_knowing",
                "confidence": "medium",
                "limitation": "The available dates do not establish the cause.",
                "material_effect": "none",
                "affected_fact": "not_applicable",
            "evidence": [
                {"page_id": "page-0001", "line_id": "page-0001-line-0004"}
            ],
        }
    ]

    validated = validate_document_analysis_response(response, redacted)

    fact = validated.payload["facts"]["education"][0]
    assert fact["institution"] == "Example University"
    assert fact["program"] is None
    assert validated.payload["findings"][0]["category"] == "timeline_gap"
    assert validated.payload["validation_warnings"]


def test_rejected_field_value_cannot_leak_through_finding_or_audit_text() -> None:
    raw = RawDocument(
        pages=(
            SourcePage(
                "page-0001",
                1,
                "Education\nExample University\nEducation artifact\nTimeline",
            ),
        ),
        source_format="text",
    )
    response = _valid_response()
    response["facts"]["education"][0]["institution"] = _field(
        "Example University", "page-0001-line-0002"
    )
    response["facts"]["education"][0]["program"] = _field(
        "UNSUPPORTED PRIVATE TEXT", "page-0001-line-0001"
    )
    response["findings"] = [
        {
            "category": "document_artifact",
            "status": "unconfirmed",
            "observation": "UNSUPPORTED PRIVATE TEXT appears in this finding.",
            "reason": "UNSUPPORTED PRIVATE TEXT was not confirmed in the field.",
            "importance": "worth_knowing",
                "confidence": "medium",
                "limitation": "The source is incomplete.",
                "material_effect": "meaning_changed",
                "affected_fact": "document_meaning",
            "evidence": [
                {"page_id": "page-0001", "line_id": "page-0001-line-0004"}
            ],
        }
    ]

    validated = validate_document_analysis_response(response, redact_national_ids(raw))
    serialized = json.dumps(validated.payload, ensure_ascii=False)

    assert "UNSUPPORTED PRIVATE TEXT" not in serialized
    assert validated.payload["facts"]["education"][0]["institution"] == (
        "Example University"
    )


def test_same_literal_keeps_supported_fact_when_another_fact_field_is_rejected() -> None:
    raw = RawDocument(
        pages=(
            SourcePage(
                "page-0001",
                1,
                "Education\nUni A\nComputer Science\nUni B\nEconomics",
            ),
        ),
        source_format="text",
    )
    response = _valid_response()
    response["facts"]["education"] = [
        {
            "kind": "education",
            "institution": _field("Uni A", "page-0001-line-0002"),
            "program": _field("Computer Science", "page-0001-line-0003"),
            "study_dates": _field(None),
            "status": "present",
        },
        {
            "kind": "education",
            "institution": _field("Uni B", "page-0001-line-0004"),
            "program": _field("Computer Science", "page-0001-line-0005"),
            "study_dates": _field(None),
            "status": "present",
        },
    ]

    validated = validate_document_analysis_response(response, redact_national_ids(raw))

    facts = validated.payload["facts"]["education"]
    assert len(facts) == 2
    assert facts[0]["institution"] == "Uni A"
    assert facts[0]["program"] == "Computer Science"
    assert facts[1]["institution"] == "Uni B"
    assert facts[1]["program"] is None
    assert validated.payload["validation_warnings"]


def test_multiline_evidence_deduplicates_duplicate_source_line_ids() -> None:
    raw = RawDocument(
        pages=(SourcePage("page-0001", 1, "Example Org — Data Engineer"),),
        source_format="pdf",
    )
    response = _valid_response()
    response["facts"]["education"] = []
    response["facts"]["employment"] = [
        {
            "kind": "employment",
            "organization": _field("Example Org", "page-0001-line-0001"),
            "role": _field("Data Engineer", "page-0001-line-0001"),
            "employment_dates": _field(None),
            "location": _field(None),
            "relationship_type": _field(None),
            "status": "present",
        }
    ]

    validated = validate_document_analysis_response(response, redact_national_ids(raw))
    employment = validated.payload["facts"]["employment"][0]
    assert len(employment["field_evidence"]["role"]) == 1


def test_multiline_evidence_rejects_gap_larger_than_two_source_lines() -> None:
    raw = RawDocument(
        pages=(
            SourcePage(
                "page-0001",
                1,
                "Example Org\nSenior\nunrelated\nunrelated\nEngineer",
            ),
        ),
        source_format="pdf",
    )
    response = _valid_response()
    response["facts"]["education"] = []
    response["facts"]["employment"] = [
        {
            "kind": "employment",
            "organization": _field("Example Org", "page-0001-line-0001"),
            "role": _field(
                "Senior Engineer",
                "page-0001-line-0001",
                "page-0001-line-0002",
                "page-0001-line-0005",
            ),
            "employment_dates": _field(None),
            "location": _field(None),
            "relationship_type": _field(None),
            "status": "present",
        }
    ]

    validated = validate_document_analysis_response(response, redact_national_ids(raw))
    assert validated.payload["facts"]["employment"] == []
    assert validated.payload["validation_warnings"]


def test_finding_check_id_is_code_owned_by_category() -> None:
    _, redacted = _documents()
    response = _valid_response()
    response["findings"] = [
        {
            "category": "timeline_gap",
            "status": "unconfirmed",
            "observation": "A timeline gap is present.",
            "reason": "The cited entries leave a gap.",
            "importance": "worth_knowing",
                "confidence": "medium",
                "limitation": "The document may omit relevant activity.",
                "material_effect": "none",
                "affected_fact": "not_applicable",
            "evidence": [
                {
                    "page_id": "page-0001",
                    "line_id": "page-0001-line-0002",
                }
            ],
        }
    ]
    validated = validate_document_analysis_response(response, redacted)
    assert validated.payload["findings"][0]["check_id"] == "timeline"
    assert validated.payload["checklist"]["timeline"]["issue_count"] == 1


@pytest.mark.parametrize(
    ("mutate", "error_kind"),
    (
        (lambda result: result.update({"research_candidates": []}), "schema"),
        (lambda result: result["facts"]["education"][0].update({"authority": "ai"}), "schema"),
        (lambda result: result.update({"score": 87}), "schema"),
    ),
)
def test_validator_rejects_fields_outside_the_structured_contract(
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
def test_validator_preserves_model_conclusions_for_human_review(
    authored_conclusion,
) -> None:
    _, redacted = _documents()
    response = _valid_response()
    response["analysis_limitations"] = [authored_conclusion]

    validated = validate_document_analysis_response(response, redacted)

    assert validated.payload["analysis_limitations"] == [authored_conclusion]
    assert validated.payload["validation_warnings"]


def test_application_keeps_paid_response_instead_of_retrying_for_model_wording() -> None:
    _, redacted = _documents()
    deterministic = analyze_deterministically(redacted, "1.0.0")
    response = _valid_response()
    response["analysis_limitations"] = [
        "Education history does not establish nationality or current location."
    ]
    analyzer = FakeDocumentAnalyzer(
        DocumentAnalyzerResponse(
            payload=response,
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
    assert outcome.attempt_count == 1
    assert len(analyzer.requests) == 1
    assert outcome.analysis is not None
    assert outcome.analysis.payload["analysis_limitations"] == response["analysis_limitations"]
    assert outcome.analysis.payload["validation_warnings"]


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
    education["institution"] = _field("Origin University", "page-0001-line-0003")

    validated = validate_document_analysis_response(response, redacted)

    assert validated.payload["facts"]["education"][0]["institution"] == "Origin University"


@pytest.mark.parametrize(
    ("field", "bad_value", "expected_error"),
    (
        ("category", "people_search", "schema"),
        ("authority", "code", "schema"),
        ("source", "web_search", "schema"),
        ("evidence", [], "schema"),
        ("evidence.page_id", "page-9999", "schema"),
        ("evidence.line_id", "page-9999-line-0001", "schema"),
    ),
    ids=(
        "category",
        "authority",
        "source",
        "evidence-shape",
        "evidence-page",
        "evidence-line-id",
    ),
)
def test_model_owned_metadata_mutations_fail_closed_with_safe_diagnostics(
    field,
    bad_value,
    expected_error,
) -> None:
    _, redacted = _documents()
    response = _valid_response()
    if field == "evidence":
        response["facts"]["education"][0]["institution"]["evidence"] = bad_value
    elif field.startswith("evidence."):
        response["facts"]["education"][0]["institution"][field.removeprefix("evidence.")] = bad_value
    else:
        response["facts"]["education"][0][field] = bad_value

    with pytest.raises(DocumentAnalysisValidationError) as captured:
        validate_document_analysis_response(response, redacted)

    assert str(captured.value) == f"AI document analysis response failed validation: {expected_error}"
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


def test_candidate_name_is_neutral_except_for_literal_linkedin_discovery_query(
    location_resolver,
) -> None:
    def analyze_named_cv(name: str):
        raw = RawDocument(
            pages=(
                SourcePage(
                    "page-0001",
                    1,
                    f"{name}\nCurrent location: Berlin, Germany\nPhone: +49 30 123456\nExperience\nEngineer",
                ),
                SourcePage("page-0002", 2, "Education\nExample University"),
            ),
            source_format="pdf",
        )
        redacted = redact_national_ids(raw)
        deterministic = analyze_deterministically(
            redacted,
            "1.0.0",
            location_resolver=location_resolver,
        )
        report = score_deterministic(deterministic, load_weights())
        response = _valid_response()
        response["facts"]["contact"] = [
            {
                "kind": "candidate_name",
                "value": name,
                "status": "present",
                "evidence": [
                    {
                        "page_id": "page-0001",
                        "line_id": "page-0001-line-0001",
                    }
                ],
            }
        ]
        composed = analyze_report_with_ai(
            AISettings(enabled=True, api_key="test-key"),
            FakeDocumentAnalyzer(
                DocumentAnalyzerResponse(
                    payload=response,
                    response_model="gpt-5.6-luna-runtime",
                    usage={"input_tokens": 10, "output_tokens": 5},
                )
            ),
            redacted,
            report,
        )
        return composed

    first = analyze_named_cv("Alex Example")
    second = analyze_named_cv("Rhea Example")

    assert serialize_report_payload(first.deterministic_report) == (
        serialize_report_payload(second.deterministic_report)
    )
    assert first.deterministic_report.score == second.deterministic_report.score
    assert first.deterministic_report.band is second.deterministic_report.band
    assert first.deterministic_report.findings == second.deterministic_report.findings

    first_ai = first.ai_outcome.analysis.payload
    second_ai = second.ai_outcome.analysis.payload
    assert first_ai["findings"] == second_ai["findings"] == []
    assert first_ai["checklist"] == second_ai["checklist"]
    assert [item["category"] for item in first_ai["research_candidates"]] == [
        item["category"] for item in second_ai["research_candidates"]
    ]
    first_linkedin = next(item for item in first_ai["research_candidates"] if item["category"] == "linkedin")
    second_linkedin = next(item for item in second_ai["research_candidates"] if item["category"] == "linkedin")
    assert first_linkedin["query_subject"] == "Alex Example"
    assert second_linkedin["query_subject"] == "Rhea Example"
    assert first_linkedin["question"] == second_linkedin["question"]


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
        invalid["findings"] = [
            {
                "category": "timeline_gap",
                "status": "unconfirmed",
                "observation": "A gap may be present.",
                "reason": "The cited entries leave a gap.",
                "importance": "worth_knowing",
                "confidence": "medium",
                "limitation": "The document may omit activity.",
                "evidence": [
                    {
                        "page_id": "page-0002",
                        "line_id": "page-0002-line-9999",
                    }
                ],
            }
        ]
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
    invalid["findings"] = [
        {
            "category": "timeline_gap",
            "status": "unconfirmed",
            "observation": "A gap may be present.",
            "reason": "The cited entries leave a gap.",
            "importance": "worth_knowing",
            "confidence": "medium",
            "limitation": "The document may omit activity.",
            "evidence": [
                {"page_id": "page-0002", "line_id": "page-0002-line-9999"}
            ],
        }
    ]
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
    ("root-array", "page-id-array", "line-id-array", "facts-array"),
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
