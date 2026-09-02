from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class CompanyResearchError(Exception):
    pass


class CompanyResearchTimeout(CompanyResearchError):
    pass


class CompanyResearchInvalidResponse(CompanyResearchError):
    def __init__(self, reason: str = "invalid_response") -> None:
        super().__init__(reason)
        self.reason = reason


class CompanyResearchClientError(CompanyResearchError):
    pass


@dataclass(frozen=True)
class CompanyResearchRequest:
    input_facts: tuple[dict[str, Any], ...]


class EducationResearchError(Exception):
    pass


class EducationResearchTimeout(EducationResearchError):
    pass


class EducationResearchInvalidResponse(EducationResearchError):
    pass


class EducationResearchClientError(EducationResearchError):
    pass


@dataclass(frozen=True)
class EducationResearchRequest:
    input_facts: tuple[dict[str, Any], ...]


class LinkedInResearchError(Exception):
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
