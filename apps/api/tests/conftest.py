import pytest

from cv_validator.domain import ComponentVersion
from cv_validator.location import (
    InMemoryLocationResolver,
    LocationMatch,
    MatchKind,
    ResolutionLevel,
)


def supported(value: str, source_id: str = "segment-1") -> dict:
    return {
        "value": value,
        "status": "supported",
        "evidence": [{"source_id": source_id, "excerpt": value}],
    }


def valid_report(
    sha256: str = "0" * 64,
    *,
    source_format: str = "pdf",
    strategy_name: str = "luna-only",
) -> dict:
    return {
        "contract_version": "base-analysis-v2",
        "strategy": {
            "name": strategy_name,
            "version": f"{strategy_name}-test-v1",
        },
        "source": {
            "format": source_format,
            "sha256": sha256,
            "conversion_status": "completed",
        },
        "base_analysis": {
            "status": "completed",
            "profile": {
                "candidate_name": supported("Jane Example"),
                "declared_location": supported("Warsaw, Poland"),
                "headline": supported("Software Engineer"),
                "summary": None,
                "skills": [supported("Python")],
                "languages": [supported("Polish")],
            },
            "employment": [{
                "id": "employment-1",
                "status": "accepted",
                "relation_status": "supported",
                "added_by_reviewer": False,
                "organization": supported("Example Systems"),
                "role": supported("Software Engineer"),
                "start_date": supported("2020"),
                "end_date": supported("2024"),
                "location": supported("Warsaw"),
                "relationship_type": supported("employer"),
            }],
            "education": [{
                "id": "education-1",
                "status": "accepted",
                "relation_status": "supported",
                "added_by_reviewer": True,
                "institution": supported("Example University"),
                "program": supported("Computer Science"),
                "degree": None,
                "certificate": None,
                "start_date": None,
                "end_date": None,
                "location": supported("Warsaw"),
            }],
            "pass_statuses": {
                "analysis": {
                    "status": "completed",
                    "attempt_count": 1,
                    "latency_ms": 10,
                    "failure_reason": None,
                }
            },
            "review": {
                "status": "completed",
                "accepted_ids": ["employment-1", "education-1"],
                "rejected": [],
                "merged_ids": [],
                "relation_corrections": [],
                "added_profile_fields": [],
                "added_candidate_ids": ["education-1"],
                "conflicts": [],
                "coverage_gaps": [],
            },
        },
        "mechanical": {
            "phones": [],
            "emails": [],
            "literal_links": [],
            "postal_candidates": [],
            "accepted_postal_addresses": [],
            "email_findings": [],
            "location_resolution": [],
            "eu_status": None,
        },
        "research": {},
        "limitations": [],
        "versions": {"contract": "base-analysis-v2"},
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


@pytest.fixture
def location_resolver() -> InMemoryLocationResolver:
    return InMemoryLocationResolver(
        records=(
            LocationMatch(
                record_id="place:berlin-de",
                level=ResolutionLevel.LOCALITY,
                canonical_name="Berlin",
                matched_name="Berlin",
                match_kind=MatchKind.CANONICAL,
                country_code="DE",
                country_name="Germany",
            ),
            LocationMatch(
                record_id="country:germany",
                level=ResolutionLevel.COUNTRY,
                canonical_name="Germany",
                matched_name="Germany",
                match_kind=MatchKind.CANONICAL,
                country_code="DE",
                country_name="Germany",
            ),
            LocationMatch(
                record_id="place:opole-pl",
                level=ResolutionLevel.LOCALITY,
                canonical_name="Opole",
                matched_name="Opole",
                match_kind=MatchKind.CANONICAL,
                country_code="PL",
                country_name="Poland",
            ),
            LocationMatch(
                record_id="country:poland",
                level=ResolutionLevel.COUNTRY,
                canonical_name="Poland",
                matched_name="Poland",
                match_kind=MatchKind.CANONICAL,
                country_code="PL",
                country_name="Poland",
            ),
        ),
        reference_data_version=ComponentVersion("test-locations", "v1"),
    )
