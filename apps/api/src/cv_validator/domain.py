from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComponentVersion:
    name: str
    version: str
    source_url: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("component version name must not be empty")
        if not self.version.strip():
            raise ValueError("component version value must not be empty")
