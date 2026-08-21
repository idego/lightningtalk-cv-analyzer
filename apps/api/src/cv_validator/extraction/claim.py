from __future__ import annotations

import re

from cv_validator.domain import ClaimedLocation
from cv_validator.gazetteer.resolver import resolve_location
from cv_validator.ingestion import RawDocument, RedactedDocument

_LOCATION_LINE = re.compile(
    r"^[A-Za-zÀ-ÿ\s\-'.]+,\s*[A-Za-zÀ-ÿ\s\-'.]+$|"
    r"^(Berlin|Munich|München|Warsaw|Warszawa|London|Paris|New York|San Francisco)\b.*",
    re.IGNORECASE,
)


def identify_claim(parsed: RawDocument | RedactedDocument) -> ClaimedLocation:
    candidates: list[tuple[str, str]] = []

    for line in parsed.contact_region:
        if _LOCATION_LINE.match(line.strip()):
            candidates.append((line.strip(), "high"))
            continue
        resolution = resolve_location(line)
        if resolution.is_unambiguous and resolution.primary:
            candidates.append((line.strip(), "high"))

    if not candidates:
        for line in parsed.contact_region[-3:]:
            resolution = resolve_location(line)
            if resolution.is_unambiguous and resolution.primary:
                candidates.append((line.strip(), "low"))

    if not candidates:
        return ClaimedLocation(raw=None, country_code=None, region=None, confidence="undetermined")

    raw, confidence = candidates[0]
    resolution = resolve_location(raw)
    if not resolution.is_unambiguous or not resolution.primary:
        if len(resolution.matches) > 1:
            return ClaimedLocation(raw=raw, country_code=None, region=None, confidence="undetermined")
        return ClaimedLocation(raw=raw, country_code=None, region=None, confidence="undetermined")

    match = resolution.primary
    return ClaimedLocation(
        raw=raw,
        country_code=match.country_code,
        region=match.region,
        confidence=confidence,
    )
