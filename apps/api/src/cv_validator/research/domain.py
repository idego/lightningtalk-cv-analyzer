from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class CompanyResearchError(Exception):
    pass


class CompanyResearchTimeout(CompanyResearchError):
    pass


class CompanyResearchInvalidResponse(CompanyResearchError):
    pass


class CompanyResearchClientError(CompanyResearchError):
    pass


@dataclass(frozen=True)
class CompanyResearchRequest:
    input_facts: tuple[dict[str, Any], ...]
