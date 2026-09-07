"""Compare public lifecycle evidence with accepted, owner-scoped CV records."""
from __future__ import annotations

import calendar
import re
from copy import deepcopy
from datetime import date
from typing import Any

from cv_validator.research.subjects import accepted_records, subject_key, supported_field

_MONTHS = {name.casefold(): index for index, name in enumerate(calendar.month_name) if name}
_MONTHS.update({name.casefold(): index for index, name in enumerate(calendar.month_abbr) if name})


def date_bounds(value: str) -> tuple[date, date] | None:
    """Keep imprecise dates as intervals; never invent a day for comparisons."""
    value = value.strip()
    match = re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{4})", value)
    if match:
        month = _MONTHS.get(match[1].casefold())
        if month is None:
            return None
        value = f"{match[2]}-{month:02}"
    if not re.fullmatch(r"\d{4}(?:-\d{2})?(?:-\d{2})?", value):
        return None
    try:
        parts = [int(part) for part in value.split("-")]
        year = parts[0]
        month = parts[1] if len(parts) > 1 else 1
        first = date(year, month, parts[2] if len(parts) > 2 else 1)
        last = first if len(parts) == 3 else date(year, month, calendar.monthrange(year, month)[1]) if len(parts) == 2 else date(year, 12, 31)
        return first, last
    except ValueError:
        return None


def apply_company_timeline(public_result: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(public_result)
    result["timeline_findings"] = []
    organizations = {subject_key("company", item["query_subject"]): item for item in result.get("organizations", [])}
    for record in accepted_records(report, "employment"):
        subject = supported_field(record, "organization")
        start = supported_field(record, "start_date")
        organization = organizations.get(subject_key("company", subject)) if subject else None
        if not organization or not start:
            continue
        if organization.get("entity_match") != "unique" or organization.get("continuity_unclear") is not False or organization.get("existence") != "supported":
            continue
        interval = date_bounds(start)
        if interval is None:
            continue
        for event in organization.get("lifecycle_events", []):
            bound = date_bounds(event["date"])
            if bound is None or event.get("confidence") != "high" or not event.get("source_urls"):
                continue
            kind = None
            if event["kind"] == "founded" and interval[1] < bound[0]:
                kind = "employment_before_founding"
            elif event["kind"] == "closed" and interval[0] > bound[1]:
                kind = "employment_after_closure"
            if kind:
                result["timeline_findings"].append({
                    "kind": kind, "record_id": record["id"], "organization": subject,
                    "cv_date": start, "event_date": event["date"],
                    "source_urls": list(dict.fromkeys(event["source_urls"])),
                })
    return result
