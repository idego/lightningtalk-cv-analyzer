from cv_validator.domain import ComponentVersion


POSTAL_PATTERNS: dict[str, str] = {
    "DE": r"\b\d{5}\b",
    "US": r"\b\d{5}(?:-\d{4})?\b",
    "GB": r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b",
    "PL": r"\b\d{2}-\d{3}\b",
    "FR": r"\b\d{5}\b",
}
POSTAL_REFERENCE_VERSION = ComponentVersion("postal-patterns", "v1")
