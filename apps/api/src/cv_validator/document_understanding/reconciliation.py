from __future__ import annotations

from copy import deepcopy
from typing import Any

from cv_validator.document_understanding.normalization import normalize_text


def reconcile_records(understanding: dict[str, Any] | None, ai_analysis: dict[str, Any] | None) -> tuple[dict[str, Any], ...]:
    """Create a display/research projection without mutating either authority source."""
    if not isinstance(understanding, dict):
        return tuple(_ai_records(ai_analysis))
    result = []
    matched_ai: set[tuple[str, int]] = set()
    ai_groups = (ai_analysis or {}).get("facts", {}) if isinstance(ai_analysis, dict) else {}
    for record in understanding.get("records", []):
        if not isinstance(record, dict):
            continue
        projected = deepcopy(record); projected["authority"] = "code"; projected["conflicts"] = []
        identity_name = "institution" if record.get("kind") == "education" else "organization"
        identity = next((field.get("value") for field in record.get("fields", []) if field.get("name") == identity_name and field.get("status") == "supported"), None)
        group = "education" if record.get("kind") == "education" else "employment"
        match = next(((index, item) for index, item in enumerate(ai_groups.get(group, [])) if isinstance(item, dict) and normalize_text(str(item.get(identity_name) or "")) == normalize_text(str(identity or ""))), None)
        if match:
            index, ai_record = match; matched_ai.add((group, index)); _enrich(projected, ai_record)
        result.append(projected)
    for group, records in (("education", ai_groups.get("education", [])), ("employment", ai_groups.get("employment", []))):
        for index, record in enumerate(records):
            if (group, index) not in matched_ai and isinstance(record, dict): result.append(_ai_record(group, index, record))
    return tuple(result)


def _enrich(record: dict[str, Any], ai_record: dict[str, Any]) -> None:
    mapping = {"education": {"program": "program", "study_dates": "study_dates"}, "employment": {"role": "role", "employment_dates": "employment_dates", "employment_location": "location", "relationship_type": "relationship_type"}}
    fields = {field["name"]: field for field in record.get("fields", []) if isinstance(field, dict) and isinstance(field.get("name"), str)}
    for name, ai_name in mapping.get(record.get("kind"), {}).items():
        value = ai_record.get(ai_name)
        if not isinstance(value, str) or not value.strip(): continue
        field = fields.get(name)
        if field is None or field.get("status") == "unknown":
            record.setdefault("ai_enrichments", []).append({"name": name, "value": value, "authority": "ai"})
        elif normalize_text(str(field.get("value"))) != normalize_text(value):
            record["conflicts"].append({"name": name, "code_value": field.get("value"), "ai_value": value})


def _ai_records(ai_analysis):
    facts = (ai_analysis or {}).get("facts", {}) if isinstance(ai_analysis, dict) else {}
    return [_ai_record(group, index, record) for group in ("education", "employment") for index, record in enumerate(facts.get(group, [])) if isinstance(record, dict)]


def _ai_record(group: str, index: int, record: dict[str, Any]) -> dict[str, Any]:
    return {"id": f"ai-{group}-{index}", "kind": group, "authority": "ai", "fields": deepcopy(record), "conflicts": []}
