from __future__ import annotations

import json
import io
import sqlite3
from dataclasses import replace

from docx import Document
from fastapi.testclient import TestClient

from cv_validator.ai.config import AISettings
from cv_validator.ai.domain import (
    AIAnalysisStatus,
    AIDocumentAnalysisOutcome,
    AIFailureReason,
    ValidatedDocumentAnalysis,
    DocumentAnalyzerResponse,
)
from cv_validator.ai.request import (
    DETERMINISTIC_OBSERVATIONS_VERSION,
    INPUT_CONTRACT_VERSION,
    PROMPT_VERSION,
    SCHEMA_VERSION,
)
from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.pipeline import analyze_cv_text_result
from cv_validator.serialization import serialize_analysis_payload


CHECK_IDS = (
    "contact",
    "education",
    "employment",
    "timeline",
    "duration_claims",
    "relationships",
    "document_quality",
    "protected_boundaries",
)


def _successful_result():
    result = analyze_cv_text_result(
        "Candidate Example\nExperience Experience\nSoftware engineer profile"
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "facts": {"contact": [], "education": [], "employment": []},
        "findings": [
            {
                "category": "document_artifact",
                "check_id": "document_quality",
                "status": "unconfirmed",
                "observation": "A heading is repeated.",
                "reason": "The same heading appears twice on one line.",
                "importance": "worth_knowing",
                "confidence": "high",
                "limitation": "Formatting may explain the repetition.",
                "authority": "ai",
                "source": "document_analyzer",
                "evidence": [
                    {
                        "page_id": "page-0001",
                        "line_id": "page-0001-line-0002",
                        "excerpt": "Experience Experience",
                    }
                ],
            }
        ],
        "unknowns": [],
        "research_candidates": [],
        "checklist": {
            check_id: {
                "checked": True,
                "issue_count": 1 if check_id == "document_quality" else 0,
            }
            for check_id in CHECK_IDS
        },
        "analysis_limitations": ["Only the supplied document was analyzed."],
    }
    return replace(
        result,
        ai_outcome=AIDocumentAnalysisOutcome(
            status=AIAnalysisStatus.SUCCEEDED,
            analysis=ValidatedDocumentAnalysis(
                schema_version=SCHEMA_VERSION,
                payload=payload,
            ),
            response_model="gpt-5.6-luna-runtime",
            usage={"input_tokens": 123, "output_tokens": 45},
        ),
    )


def _docx_bytes(text: str) -> bytes:
    document = Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


class _Analyzer:
    def __init__(self) -> None:
        self.requests = []

    def analyze(self, request):
        self.requests.append(request)
        return DocumentAnalyzerResponse(
            payload={
                "schema_version": SCHEMA_VERSION,
                "facts": {"contact": [], "education": [], "employment": []},
                "findings": [],
                "unknowns": [],
                "research_candidates": [],
                "checklist": {
                    check_id: {"checked": True, "issue_count": 0}
                    for check_id in CHECK_IDS
                },
                "analysis_limitations": [],
            },
            response_model="gpt-5.6-luna-runtime",
            usage={"input_tokens": 20, "output_tokens": 5},
        )


def test_analysis_payload_is_additive_complete_and_deterministic_invariant() -> None:
    result = _successful_result()
    deterministic_before = result.report.to_dict()

    payload = serialize_analysis_payload(
        result,
        AISettings(enabled=True, api_key="test-key"),
        analysis_id="analysis-test-1",
    )

    assert {key: payload[key] for key in deterministic_before} == deterministic_before
    assert result.report.to_dict() == deterministic_before
    assert payload["analysis_id"] == "analysis-test-1"
    assert payload["ai_analysis"]["status"] == "succeeded"
    assert payload["ai_analysis"]["authority"] == "ai"
    assert payload["ai_analysis"]["versions"] == {
        "prompt": PROMPT_VERSION,
        "schema": SCHEMA_VERSION,
        "input_contract": INPUT_CONTRACT_VERSION,
        "deterministic_observations": DETERMINISTIC_OBSERVATIONS_VERSION,
    }
    assert payload["ai_analysis"]["usage"] == {
        "input_tokens": 123,
        "output_tokens": 45,
    }
    assert set(payload["checklist"]["checks"]) == set(CHECK_IDS)
    assert payload["checklist"]["checks"]["document_quality"] == {
        "checked": True,
        "issue_count": 1,
    }
    ai_flag = next(flag for flag in payload["checklist"]["flags"] if flag["source"] == "ai")
    assert ai_flag["importance"] == "worth_knowing"
    assert ai_flag["evidence"][0]["excerpt"] == "Experience Experience"


def test_failed_analysis_has_a_complete_graceful_contract() -> None:
    result = analyze_cv_text_result("Candidate Example\nSoftware engineer profile")
    result = replace(
        result,
        ai_outcome=AIDocumentAnalysisOutcome(
            status=AIAnalysisStatus.FAILED,
            failure_reason=AIFailureReason.REFUSAL,
            response_model="gpt-5.6-luna-runtime",
            usage={"input_tokens": 10, "output_tokens": 0},
        ),
    )

    payload = serialize_analysis_payload(
        result,
        AISettings(enabled=True, api_key="test-key"),
        analysis_id="analysis-test-2",
    )

    assert payload["ai_analysis"]["status"] == "failed"
    assert payload["ai_analysis"]["failure_reason"] == "refusal"
    assert payload["ai_analysis"]["findings"] == []
    assert payload["ai_analysis"]["facts"] == {
        "contact": [],
        "education": [],
        "employment": [],
    }
    assert all(
        check == {"checked": False, "issue_count": 0}
        for check in payload["checklist"]["checks"].values()
    )


def test_ai_analysis_is_linked_to_report_and_audit_in_sqlite(tmp_path) -> None:
    result = _successful_result()
    settings = AISettings(enabled=True, api_key="test-key")
    payload = serialize_analysis_payload(
        result,
        settings,
        analysis_id="analysis-test-3",
    )
    store = PersistenceStore(PersistenceConfig(tmp_path / "analysis.db"))

    stored_id = store.persist_report(
        result.document_identity,
        result.report,
        report_payload=payload,
        analysis_id="analysis-test-3",
        ai_analysis=payload["ai_analysis"],
    )

    assert stored_id == "analysis-test-3"
    audit = store.get_audit_entries()[0]
    assert audit["analysis_id"] == stored_id
    assert json.loads(audit["output_json"]) == payload
    stored_ai = store.get_ai_analysis(stored_id)
    assert stored_ai is not None
    assert stored_ai["status"] == "succeeded"
    assert stored_ai["prompt_version"] == PROMPT_VERSION
    assert stored_ai["schema_version"] == SCHEMA_VERSION
    assert stored_ai["deterministic_observations_version"] == (
        DETERMINISTIC_OBSERVATIONS_VERSION
    )
    assert json.loads(stored_ai["usage_json"])["input_tokens"] == 123
    assert json.loads(stored_ai["result_json"])["findings"][0]["authority"] == "ai"


def test_existing_database_is_migrated_without_losing_old_rows(tmp_path) -> None:
    db_path = tmp_path / "old.db"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                input_hash TEXT NOT NULL,
                ruleset_version TEXT NOT NULL,
                score INTEGER NOT NULL,
                band TEXT NOT NULL,
                findings_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                input_hash TEXT NOT NULL,
                ruleset_version TEXT NOT NULL,
                output_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            INSERT INTO reports VALUES (1, 'old', '1.0.0', 50, 'gray', '[]', '2026-08-21T00:00:00+00:00');
            INSERT INTO audit_log VALUES (1, 'old', '1.0.0', '{"band":"gray"}', '2026-08-21T00:00:00+00:00');
            """
        )

    store = PersistenceStore(PersistenceConfig(db_path, retention_days=36500))

    with sqlite3.connect(db_path) as connection:
        report = connection.execute(
            "SELECT input_hash, analysis_id FROM reports WHERE id = 1"
        ).fetchone()
        audit = connection.execute(
            "SELECT input_hash, analysis_id FROM audit_log WHERE id = 1"
        ).fetchone()
        ai_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ai_analyses'"
        ).fetchone()
    assert report == ("old", "legacy-1")
    assert audit == ("old", "legacy-1")
    assert ai_table == ("ai_analyses",)
    assert json.loads(store.get_audit_entries()[0]["output_json"]) == {"band": "gray"}


def test_http_response_and_audit_share_one_stable_analysis_id(tmp_path) -> None:
    from cv_validator.api.app import create_app

    app = create_app(
        db_path=tmp_path / "api.db",
        ai_settings=AISettings(enabled=True, api_key="test-key"),
        document_analyzer=_Analyzer(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/analyze",
            files={
                "file": (
                    "candidate.docx",
                    _docx_bytes("Candidate Example\nSoftware engineer profile"),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    analysis_id = payload["analysis_id"]
    assert analysis_id
    assert payload["ai_analysis"]["status"] == "succeeded"
    assert payload["ai_analysis"]["model"]["response"] == "gpt-5.6-luna-runtime"
    audit = app.state.store.get_audit_entries()[0]
    assert audit["analysis_id"] == analysis_id
    assert json.loads(audit["output_json"]) == payload
    assert app.state.store.get_ai_analysis(analysis_id)["analysis_id"] == analysis_id


def test_enabled_ai_cannot_change_deterministic_api_fields(tmp_path) -> None:
    from cv_validator.api.app import create_app

    content = _docx_bytes(
        "Candidate Example\nCurrent location: Berlin, Germany\n"
        "Phone: +49 30 123456\nSoftware engineer profile"
    )
    disabled_app = create_app(db_path=tmp_path / "disabled.db")
    enabled_app = create_app(
        db_path=tmp_path / "enabled.db",
        ai_settings=AISettings(enabled=True, api_key="test-key"),
        document_analyzer=_Analyzer(),
    )

    with TestClient(disabled_app) as disabled_client:
        disabled = disabled_client.post(
            "/analyze",
            files={"file": ("cv.docx", content, "application/octet-stream")},
        ).json()
    with TestClient(enabled_app) as enabled_client:
        enabled = enabled_client.post(
            "/analyze",
            files={"file": ("cv.docx", content, "application/octet-stream")},
        ).json()

    immutable_keys = (
        "score",
        "band",
        "claimed_location",
        "findings",
        "ruleset_version",
        "signal_count",
        "supporting_count",
        "conflicting_count",
        "deterministic",
    )
    disabled_bytes = json.dumps(
        {key: disabled[key] for key in immutable_keys},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    enabled_bytes = json.dumps(
        {key: enabled[key] for key in immutable_keys},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert enabled_bytes == disabled_bytes


def test_bounded_four_cv_batch_has_independent_ids_and_persisted_ai(tmp_path) -> None:
    from cv_validator.api.app import create_app

    analyzer = _Analyzer()
    app = create_app(
        db_path=tmp_path / "batch.db",
        ai_settings=AISettings(enabled=True, api_key="test-key"),
        document_analyzer=analyzer,
        batch_max_files=4,
    )
    files = [
        (
            "files",
            (
                f"candidate-{number}.docx",
                _docx_bytes(
                    f"Candidate {number}\nExperienced software engineer profile"
                ),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        )
        for number in range(4)
    ]

    with TestClient(app) as client:
        response = client.post("/analyze/batch", files=files)

    assert response.status_code == 200
    results = response.json()["results"]
    assert all(item["status"] == "ok" for item in results)
    analysis_ids = [item["report"]["analysis_id"] for item in results]
    assert len(set(analysis_ids)) == 4
    assert len(analyzer.requests) == 4
    assert len(app.state.store.get_audit_entries()) == 4
    assert all(app.state.store.get_ai_analysis(item) is not None for item in analysis_ids)
