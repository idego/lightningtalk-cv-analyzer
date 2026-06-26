from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LocationMatch:
    name: str
    country_code: str
    region: str | None
    kind: str  # country, city, region


@dataclass(frozen=True)
class ResolutionResult:
    query: str
    matches: tuple[LocationMatch, ...]

    @property
    def is_unambiguous(self) -> bool:
        if len(self.matches) != 1:
            return False
        return len({m.country_code for m in self.matches}) == 1

    @property
    def primary(self) -> LocationMatch | None:
        return self.matches[0] if self.is_unambiguous else None
