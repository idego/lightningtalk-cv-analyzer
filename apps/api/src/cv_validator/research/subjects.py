from __future__ import annotations

import unicodedata
from typing import Any


def subject_key(category: str, subject: str) -> tuple[str, str]:
    normalized = unicodedata.normalize("NFKC", subject).casefold()
    return category, " ".join(normalized.split())


def supported_field(record: Any, name: str) -> str | None:
    if not isinstance(record, dict):
        return None
    field = record.get(name)
    if not isinstance(field, dict) or field.get("status") != "supported":
        return None
    value = field.get("value")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def accepted_records(
    stored_report: dict[str, Any],
    category: str,
) -> tuple[dict[str, Any], ...]:
    base_analysis = stored_report.get("base_analysis")
    if not isinstance(base_analysis, dict):
        return ()
    records = base_analysis.get(category)
    if not isinstance(records, list):
        return ()
    return tuple(
        record
        for record in records
        if isinstance(record, dict)
        and record.get("status") == "accepted"
        and record.get("relation_status") == "supported"
    )


def supported_profile_field(
    stored_report: dict[str, Any],
    name: str,
) -> str | None:
    base_analysis = stored_report.get("base_analysis")
    if not isinstance(base_analysis, dict):
        return None
    return supported_field(base_analysis.get("profile"), name)


def safe_public_subject(value: str, *, limit: int = 200) -> bool:
    """Return whether a literal field is safe to send as a public-search subject."""
    import re

    stripped = value.strip()
    if (
        not stripped
        or len(stripped) > limit
        or any(ord(char) < 0x20 or ord(char) == 0x7F for char in stripped)
    ):
        return False
    if "@" in stripped or re.search(
        r"(?:https?://|www\.)|\+?\d[\d\s().-]{6,}\d",
        stripped,
        re.IGNORECASE,
    ):
        return False
    return len(re.findall(r"[^\W\d_]", stripped, re.UNICODE)) >= 2
