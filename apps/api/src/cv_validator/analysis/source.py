from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextSegment:
    id: str
    text: str
    page_number: int | None = None

    def evidence(self, start: int, end: int) -> dict[str, object]:
        if start < 0 or end < start or end > len(self.text):
            raise ValueError("evidence offsets are outside the source segment")
        return {
            "source_id": self.id,
            "excerpt": self.text[start:end],
            "page_number": self.page_number,
            "start_offset": start,
            "end_offset": end,
        }
