from __future__ import annotations

from dataclasses import dataclass

from cv_validator.ingestion import RedactedDocument
from cv_validator.structural.config import StructuralAuditConfig

QUARANTINE_VERSION = "visibility-quarantine-v1"


@dataclass(frozen=True)
class VisibilityExclusionIndex:
    intervals: tuple[tuple[str, int, int], ...]
    partial_coverage: bool

    def intersects(self, page_id: str, start: int, end: int) -> bool:
        return any(pid == page_id and start < right and end > left for pid, left, right in self.intervals)


def build_visibility_exclusion_index(document: RedactedDocument, config: StructuralAuditConfig | None = None) -> VisibilityExclusionIndex:
    cfg = config or StructuralAuditConfig()
    intervals: list[tuple[str, int, int]] = []
    partial = document.presentation_truncated
    redactions = tuple((r.page_id, r.start_offset, r.end_offset) for r in document.redactions)
    for span in document.presentation_spans:
        trigger = (
            span.explicit_hidden
            or (span.font_size_points is not None and span.font_size_points <= cfg.near_zero_font_points)
            or (span.opacity is not None and span.opacity <= cfg.near_zero_opacity)
            or (span.foreground_luminance is not None and span.background_luminance is not None
                and span.foreground_luminance >= cfg.near_white_luminance
                and span.background_luminance >= cfg.known_light_background_luminance
                and abs(span.foreground_luminance - span.background_luminance) <= cfg.max_low_contrast_luminance_delta)
        )
        if not trigger:
            continue
        if span.association != "exact" or span.start_offset is None or span.end_offset is None:
            partial = True
            continue
        parts = [(span.start_offset, span.end_offset)]
        for page_id, left, right in redactions:
            if page_id != span.page_id:
                continue
            remaining = []
            for start, end in parts:
                if right <= start or left >= end:
                    remaining.append((start, end))
                else:
                    if start < left: remaining.append((start, left))
                    if right < end: remaining.append((right, end))
            parts = remaining
        intervals.extend((span.page_id, start, end) for start, end in parts if start < end)
    merged: list[tuple[str, int, int]] = []
    for page_id, start, end in sorted(intervals):
        if merged and merged[-1][0] == page_id and start <= merged[-1][2]:
            merged[-1] = (page_id, merged[-1][1], max(end, merged[-1][2]))
        else:
            merged.append((page_id, start, end))
    return VisibilityExclusionIndex(tuple(merged), partial)
