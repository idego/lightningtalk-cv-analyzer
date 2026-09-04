from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator


class AnalysisReportValidationError(ValueError):
    pass


def _validator() -> Draft202012Validator:
    schema_path = files("cv_validator.analysis.contracts").joinpath(
        "base-analysis.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


_REPORT_VALIDATOR = _validator()


def validate_analysis_report(payload: dict[str, Any]) -> dict[str, Any]:
    candidate = deepcopy(payload)
    errors = sorted(_REPORT_VALIDATOR.iter_errors(candidate), key=lambda item: list(item.path))
    if errors:
        path = ".".join(str(part) for part in errors[0].path) or "$"
        raise AnalysisReportValidationError(f"invalid_base_analysis:{path}")
    _validate_internal_integrity(candidate)
    return candidate


def _validate_internal_integrity(payload: dict[str, Any]) -> None:
    base = payload["base_analysis"]
    records = [*base["employment"], *base["education"]]
    record_ids = [record["id"] for record in records]
    if len(record_ids) != len(set(record_ids)):
        raise AnalysisReportValidationError(
            "invalid_base_analysis:base_analysis.record_ids"
        )

    by_id = {record["id"]: record for record in records}
    accepted_ids = base["review"]["accepted_ids"]
    expected_accepted = {
        record["id"]
        for record in records
        if record["status"] == "accepted"
    }
    if len(accepted_ids) != len(set(accepted_ids)):
        raise AnalysisReportValidationError(
            "invalid_base_analysis:base_analysis.review.accepted_ids"
        )
    if set(accepted_ids) != expected_accepted:
        raise AnalysisReportValidationError(
            "invalid_base_analysis:base_analysis.review.accepted_ids"
        )

    added_ids = base["review"]["added_candidate_ids"]
    expected_added = {
        record["id"]
        for record in records
        if record["added_by_reviewer"]
    }
    if (
        len(added_ids) != len(set(added_ids))
        or set(added_ids) != expected_added
        or any(by_id[record_id]["status"] != "accepted" for record_id in added_ids)
    ):
        raise AnalysisReportValidationError(
            "invalid_base_analysis:base_analysis.review.added_candidate_ids"
        )

    profile = base["profile"]
    for field_name in base["review"]["added_profile_fields"]:
        value = profile[field_name]
        if isinstance(value, list):
            valid = any(field["status"] == "supported" for field in value)
        else:
            valid = value is not None and value["status"] == "supported"
        if not valid:
            raise AnalysisReportValidationError(
                "invalid_base_analysis:base_analysis.review.added_profile_fields"
            )
    fields = [
        profile["candidate_name"],
        profile["declared_location"],
        profile["headline"],
        profile["summary"],
        *profile["skills"],
        *profile["languages"],
    ]
    for record in base["employment"]:
        fields.extend(record[name] for name in (
            "organization",
            "role",
            "start_date",
            "end_date",
            "location",
            "relationship_type",
        ))
    for record in base["education"]:
        fields.extend(record[name] for name in (
            "institution",
            "program",
            "degree",
            "certificate",
            "start_date",
            "end_date",
            "location",
        ))
    for field in fields:
        if field is None:
            continue
        for evidence in field["evidence"]:
            start = evidence.get("start_offset")
            end = evidence.get("end_offset")
            if (start is None) != (end is None):
                raise AnalysisReportValidationError(
                    "invalid_base_analysis:evidence.offsets"
                )
            if start is not None and end <= start:
                raise AnalysisReportValidationError(
                    "invalid_base_analysis:evidence.offsets"
                )
