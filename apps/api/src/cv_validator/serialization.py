from __future__ import annotations

import json
from typing import Any

from cv_validator.domain import Report
from cv_validator.errors import ReportSerializationError


def serialize_report_payload(report: Report) -> dict[str, Any]:
    payload = report.to_dict()
    try:
        json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ReportSerializationError(
            "report contains a value that is not JSON-safe"
        ) from exc
    return payload
