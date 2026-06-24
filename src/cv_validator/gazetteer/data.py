from __future__ import annotations

from cv_validator.gazetteer import LocationMatch

# Curated subset for v1 — GeoNames-style identifiers without shipping full dataset.
COUNTRIES: dict[str, LocationMatch] = {
    "germany": LocationMatch("Germany", "DE", None, "country"),
    "deutschland": LocationMatch("Germany", "DE", None, "country"),
    "de": LocationMatch("Germany", "DE", None, "country"),
    "united states": LocationMatch("United States", "US", None, "country"),
    "usa": LocationMatch("United States", "US", None, "country"),
    "us": LocationMatch("United States", "US", None, "country"),
    "united kingdom": LocationMatch("United Kingdom", "GB", None, "country"),
    "uk": LocationMatch("United Kingdom", "GB", None, "country"),
    "england": LocationMatch("United Kingdom", "GB", "England", "region"),
    "poland": LocationMatch("Poland", "PL", None, "country"),
    "pl": LocationMatch("Poland", "PL", None, "country"),
    "france": LocationMatch("France", "FR", None, "country"),
    "fr": LocationMatch("France", "FR", None, "country"),
}

CITIES: dict[str, tuple[LocationMatch, ...]] = {
    "berlin": (LocationMatch("Berlin", "DE", "Berlin", "city"),),
    "munich": (LocationMatch("Munich", "DE", "Bavaria", "city"),),
    "münchen": (LocationMatch("Munich", "DE", "Bavaria", "city"),),
    "warsaw": (LocationMatch("Warsaw", "PL", "Mazovia", "city"),),
    "warszawa": (LocationMatch("Warsaw", "PL", "Mazovia", "city"),),
    "london": (LocationMatch("London", "GB", "England", "city"),),
    "new york": (LocationMatch("New York", "US", "NY", "city"),),
    "san francisco": (LocationMatch("San Francisco", "US", "CA", "city"),),
    "paris": (
        LocationMatch("Paris", "FR", "Île-de-France", "city"),
        LocationMatch("Paris", "US", "TX", "city"),
    ),
}

POSTAL_PATTERNS: dict[str, str] = {
    "DE": r"\b\d{5}\b",
    "US": r"\b\d{5}(?:-\d{4})?\b",
    "GB": r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b",
    "PL": r"\b\d{2}-\d{3}\b",
    "FR": r"\b\d{5}\b",
}

TLD_TO_COUNTRY: dict[str, str] = {
    "de": "DE",
    "pl": "PL",
    "fr": "FR",
    "uk": "GB",
    "co.uk": "GB",
    "us": "US",
}
