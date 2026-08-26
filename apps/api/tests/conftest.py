import pytest

from cv_validator.domain import ComponentVersion
from cv_validator.location import (
    InMemoryLocationResolver,
    LocationMatch,
    MatchKind,
    ResolutionLevel,
)


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
