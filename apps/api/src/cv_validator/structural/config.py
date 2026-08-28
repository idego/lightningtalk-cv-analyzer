from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StructuralAuditConfig:
    threshold_version: str = "structural-thresholds-v1"
    near_zero_font_points: float = 1.0
    near_zero_opacity: float = 0.05
    near_white_luminance: float = 0.95
    known_light_background_luminance: float = 0.95
    max_low_contrast_luminance_delta: float = 0.05
    minimum_meaningful_alphanumeric: int = 3
    max_pdf_atoms: int = 100_000
    max_docx_runs: int = 20_000
    max_timeline_entries: int = 100
    max_timeline_observations: int = 100
    max_visibility_observations: int = 50
    max_evidence_excerpt_chars: int = 256

    def __post_init__(self) -> None:
        if not self.threshold_version.strip():
            raise ValueError("threshold_version must not be empty")
        if self.near_zero_font_points < 0:
            raise ValueError("near_zero_font_points must not be negative")
        for name in (
            "near_zero_opacity",
            "near_white_luminance", "known_light_background_luminance",
            "max_low_contrast_luminance_delta",
        ):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        for name in (
            "minimum_meaningful_alphanumeric", "max_pdf_atoms", "max_docx_runs",
            "max_timeline_entries", "max_timeline_observations",
            "max_visibility_observations", "max_evidence_excerpt_chars",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
