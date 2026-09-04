from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ResearchError(Exception):
    def __init__(self, *args: Any, usage: Any = None, model: str | None = None) -> None:
        super().__init__(*args)
        self.usage = usage or {}
        self.model = model


class CompanyResearchError(ResearchError):
    pass


class CompanyResearchTimeout(CompanyResearchError):
    pass


class CompanyResearchInvalidResponse(CompanyResearchError):
    def __init__(
        self,
        reason: str = "invalid_response",
        *,
        usage: Any = None,
        model: str | None = None,
    ) -> None:
        super().__init__(reason, usage=usage, model=model)
        self.reason = reason


class CompanyResearchClientError(CompanyResearchError):
    pass


@dataclass(frozen=True)
class CompanyResearchRequest:
    input_facts: tuple[dict[str, Any], ...]


class EducationResearchError(ResearchError):
    pass


class EducationResearchTimeout(EducationResearchError):
    pass


class EducationResearchInvalidResponse(EducationResearchError):
    def __init__(
        self,
        reason: str = "invalid_response",
        *,
        usage: Any = None,
        model: str | None = None,
    ) -> None:
        super().__init__(reason, usage=usage, model=model)
        self.reason = reason


class EducationResearchClientError(EducationResearchError):
    pass


@dataclass(frozen=True)
class EducationResearchRequest:
    input_facts: tuple[dict[str, Any], ...]


class LinkedInResearchError(ResearchError):
    pass


class LinkedInResearchTimeout(LinkedInResearchError):
    pass


class LinkedInResearchInvalidResponse(LinkedInResearchError):
    pass


class LinkedInResearchClientError(LinkedInResearchError):
    pass


@dataclass(frozen=True)
class LinkedInDiscoveryRequest:
    candidate: dict[str, Any]
