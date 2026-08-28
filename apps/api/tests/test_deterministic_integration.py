import json
import sqlite3
import socket
from copy import deepcopy

from cv_validator.api.persistence import PersistenceConfig, PersistenceStore
from cv_validator.domain import ComponentVersion, FactKind
from cv_validator.location import (
    InMemoryLocationResolver,
    LocationMatch,
    MatchKind,
    ResolutionLevel,
)
from cv_validator.pipeline import analyze_cv_text_result
from cv_validator.serialization import serialize_report_payload


def _resolver() -> InMemoryLocationResolver:
    return InMemoryLocationResolver(
        records=(
            LocationMatch(
                record_id="place:munich",
                level=ResolutionLevel.LOCALITY,
                canonical_name="Munich",
                matched_name="Munich",
                match_kind=MatchKind.CANONICAL,
                country_code="DE",
                country_name="Germany",
            ),
        ),
        reference_data_version=ComponentVersion("test-locations", "v1"),
    )


def test_report_projects_legacy_claim_from_the_same_deterministic_result() -> None:
    result = analyze_cv_text_result(
        "Jane Example\nCurrent location: Munich\nSoftware engineer profile",
        location_resolver=_resolver(),
    )

    fact = next(fact for fact in result.deterministic.facts if fact.kind is FactKind.CLAIMED_LOCATION)
    assert result.report.deterministic is result.deterministic
    assert result.report.claimed_location.raw == "Munich"
    assert result.report.claimed_location.country_code == fact.value == "DE"
    assert result.report.claimed_location.region == "Munich"
    assert result.report.claimed_location.confidence == "high"


def test_missing_resolver_keeps_legacy_claim_projection_undetermined() -> None:
    result = analyze_cv_text_result(
        "Jane Example\nCurrent location: Munich\nSoftware engineer profile"
    )

    assert result.report.claimed_location.raw is None
    assert result.report.claimed_location.country_code is None
    assert result.report.claimed_location.region is None
    assert result.report.claimed_location.confidence == "undetermined"
    assert not any(
        fact.kind is FactKind.CLAIMED_LOCATION
        for fact in result.deterministic.facts
    )


def test_report_json_is_additive_and_deterministic_serialization_is_explicit() -> None:
    result = analyze_cv_text_result(
        "Jane Example\nCurrent location: Munich\nSoftware engineer profile",
        location_resolver=_resolver(),
    )
    payload = result.report.to_dict()

    assert set(payload) == {
        "score",
        "band",
        "claimed_location",
        "findings",
        "summary",
        "disclaimer",
        "ruleset_version",
        "signal_count",
        "supporting_count",
        "conflicting_count",
        "deterministic",
        "structural_audits",
    }
    deterministic = payload["deterministic"]
    assert set(deterministic) == {
        "ruleset_version",
        "candidates",
        "facts",
        "observations",
        "scoring_signals",
    }
    fact = next(item for item in deterministic["facts"] if item["kind"] == "claimed_location")
    assert fact["authority"] == "code"
    assert fact["extractor_version"] == {
        "name": "location-ownership",
        "version": "1",
    }
    assert fact["reference_data_version"] == {
        "name": "test-locations",
        "version": "v1",
    }
    assert fact["relation_evidence"][0]["excerpt"] == "Current location: Munich"
    assert fact["value_evidence"][0]["excerpt"] == "Munich"
    assert fact["resolved_level"] == "locality"
    assert payload["ruleset_version"]["version"] == "1.0.0"
    assert payload["ruleset_version"]["scoring_policy_version"] == (
        "deterministic-phone-postal-comparison-v2"
    )
    assert "__dataclass_fields__" not in json.dumps(payload)


def test_persistence_stores_the_same_nested_result_and_redacted_identity(tmp_path) -> None:
    raw_id = "123-45-6789"
    result = analyze_cv_text_result(
        f"Jane Example\nCurrent location: Munich\nSSN: {raw_id}\nSoftware engineer",
        location_resolver=_resolver(),
    )
    store = PersistenceStore(PersistenceConfig(tmp_path / "audit.db"))
    payload = serialize_report_payload(result.report)
    payload_before_persistence = deepcopy(payload)

    store.persist_report(
        result.document_identity,
        result.report,
        report_payload=payload,
    )

    entry = store.get_audit_entries()[0]
    assert payload == payload_before_persistence
    persisted_payload = json.loads(entry["output_json"])
    assert payload_before_persistence == serialize_report_payload(result.report)
    assert entry["input_hash"] == result.document_identity.digest
    assert persisted_payload["deterministic"] == result.deterministic.to_dict()
    assert raw_id not in entry["output_json"]
    assert raw_id.encode() not in (tmp_path / "audit.db").read_bytes()


def test_persistence_sanitizer_is_non_mutating_and_fails_closed_on_raw_id(
    tmp_path,
) -> None:
    raw_id = "123-45-6789"
    result = analyze_cv_text_result(
        f"Jane Example\nSSN: {raw_id}\n\nExperience\nEngineer profile"
    )
    store = PersistenceStore(PersistenceConfig(tmp_path / "audit.db"))
    unsafe_payload = serialize_report_payload(result.report)
    national_id = next(
        finding
        for finding in unsafe_payload["findings"]
        if finding["signal"] == "national_id"
    )
    national_id["observed"] = raw_id
    national_id["evidence"][0]["excerpt"] = raw_id
    before = deepcopy(unsafe_payload)

    store.persist_report(
        result.document_identity,
        result.report,
        report_payload=unsafe_payload,
    )

    assert unsafe_payload == before
    output_json = store.get_audit_entries()[0]["output_json"]
    persisted = json.loads(output_json)
    persisted_national_id = next(
        finding
        for finding in persisted["findings"]
        if finding["signal"] == "national_id"
    )
    assert persisted_national_id["observed"] == "present:REDACTED"
    assert persisted_national_id["evidence"][0]["excerpt"] == "█" * len(raw_id)
    assert raw_id not in output_json
    assert raw_id.encode() not in store.config.db_path.read_bytes()


def test_previous_schema_rows_remain_readable_when_new_report_is_persisted(
    tmp_path,
) -> None:
    db_path = tmp_path / "existing.db"
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
            INSERT INTO reports VALUES (
                1, 'old-hash', '1.0.0', 50, 'gray', '[]',
                '2026-08-21T00:00:00+00:00'
            );
            INSERT INTO audit_log VALUES (
                1, 'old-hash', '1.0.0', '{"band":"gray"}',
                '2026-08-21T00:00:00+00:00'
            );
            """
        )
    store = PersistenceStore(PersistenceConfig(db_path, retention_days=36500))
    result = analyze_cv_text_result(
        "Jane Example\nCurrent location: Munich\nSoftware engineer profile",
        location_resolver=_resolver(),
    )
    before = result.report.to_dict()

    store.persist_report(result.document_identity, result.report)

    assert result.report.to_dict() == before
    audit_rows = store.get_audit_entries()
    assert json.loads(audit_rows[0]["output_json"]) == {"band": "gray"}
    assert "deterministic" in json.loads(audit_rows[1]["output_json"])
    assert audit_rows[1]["ruleset_version"] == (
        "weights:1.0.0;policy:deterministic-phone-postal-comparison-v2"
    )
    with sqlite3.connect(db_path) as connection:
        old_report = connection.execute(
            "SELECT input_hash, findings_json FROM reports WHERE id = 1"
        ).fetchone()
    assert old_report == ("old-hash", "[]")


def test_deterministic_analysis_stays_offline(monkeypatch) -> None:
    def reject_network(*args, **kwargs):
        raise AssertionError("deterministic analysis attempted network access")

    monkeypatch.setattr(socket, "socket", reject_network)

    result = analyze_cv_text_result(
        "Jane Example\nCurrent location: Munich\n+49 30 123456\nEngineer",
        location_resolver=_resolver(),
    )

    assert result.report.claimed_location.country_code == "DE"
    assert result.report.deterministic is result.deterministic
