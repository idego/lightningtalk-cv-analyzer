from __future__ import annotations

import re

_SECTION_MARKERS = re.compile(
    r"^(experience|work experience|employment|professional experience|"
    r"education|skills|summary|profile|objective|certifications)\b",
    re.IGNORECASE,
)


def split_contact_and_body(lines: list[str]) -> tuple[list[str], list[str]]:
    """Split CV into contact/header region and body based on first section heading."""
    if not lines:
        return [], []

    split_index = len(lines)
    for idx, line in enumerate(lines):
        if idx == 0:
            continue
        if _SECTION_MARKERS.match(line):
            split_index = idx
            break

    # If no section marker, treat first ~25% or first 8 lines as contact block.
    if split_index == len(lines):
        split_index = min(max(8, len(lines) // 4), len(lines))

    contact = lines[:split_index]
    body = lines[split_index:]
    return contact, body
