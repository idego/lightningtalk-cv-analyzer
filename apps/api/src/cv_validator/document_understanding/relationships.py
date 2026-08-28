from __future__ import annotations

from cv_validator.document_understanding.normalization import normalize_text

RELATIONSHIP_LABELS = frozenset({
    "freelance", "freelancer", "self employed", "self employment",
    "self-employed", "self-employment", "samozatrudnienie",
    "samozatrudniony", "wolny strzelec",
})


def is_self_employment_label(value: str | None) -> bool:
    return isinstance(value, str) and normalize_text(value) in {
        normalize_text(item) for item in RELATIONSHIP_LABELS
    }
