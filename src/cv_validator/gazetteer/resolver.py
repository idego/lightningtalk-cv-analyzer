from __future__ import annotations

import re

from cv_validator.gazetteer import LocationMatch, ResolutionResult
from cv_validator.gazetteer.data import CITIES, COUNTRIES


def resolve_location(text: str) -> ResolutionResult:
    normalized = _normalize(text)
    if not normalized:
        return ResolutionResult(query=text, matches=())

    # Try "City, Country" pattern first.
    if "," in normalized:
        city_part, country_part = [p.strip() for p in normalized.split(",", 1)]
        country_hint = _lookup_country(country_part)
        city_matches = _lookup_city(city_part)
        if country_hint and city_matches:
            filtered = tuple(m for m in city_matches if m.country_code == country_hint.country_code)
            if len(filtered) == 1:
                return ResolutionResult(query=text, matches=filtered)
            if len(filtered) > 1:
                return ResolutionResult(query=text, matches=filtered)
        if country_hint and not city_matches:
            return ResolutionResult(query=text, matches=(country_hint,))
        if city_matches:
            return ResolutionResult(query=text, matches=city_matches)

    country = _lookup_country(normalized)
    if country:
        return ResolutionResult(query=text, matches=(country,))

    city_matches = _lookup_city(normalized)
    if city_matches:
        return ResolutionResult(query=text, matches=city_matches)

    return ResolutionResult(query=text, matches=())


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _lookup_country(token: str) -> LocationMatch | None:
    return COUNTRIES.get(_normalize(token))


def _lookup_city(token: str) -> tuple[LocationMatch, ...]:
    return CITIES.get(_normalize(token), ())
