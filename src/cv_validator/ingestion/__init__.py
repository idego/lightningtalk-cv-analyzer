from __future__ import annotations

from dataclasses import dataclass


class IngestionError(Exception):
    """Raised when a CV cannot be ingested."""


@dataclass(frozen=True)
class ParsedCV:
    lines: tuple[str, ...]
    contact_region: tuple[str, ...]
    body_region: tuple[str, ...]
    source_format: str

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def contact_text(self) -> str:
        return "\n".join(self.contact_region)

    @property
    def body_text(self) -> str:
        return "\n".join(self.body_region)
