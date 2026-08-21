import pytest

from cv_validator.domain import ComponentVersion
from cv_validator.location import (
    Ambiguous,
    InMemoryLocationResolver,
    LocationMatch,
    MatchKind,
    ResolutionLevel,
    Resolved,
    ScopeResolution,
    Unresolved,
    normalize_location,
)


REFERENCE_DATA_VERSION = ComponentVersion("test-locations", "2026-08-21")


def _locality(
    record_id: str,
    canonical_name: str,
    country_code: str,
    country_name: str,
    *,
    region_code: str,
    region_name: str,
) -> LocationMatch:
    return LocationMatch(
        record_id=record_id,
        level=ResolutionLevel.LOCALITY,
        canonical_name=canonical_name,
        matched_name=canonical_name,
        match_kind=MatchKind.CANONICAL,
        country_code=country_code,
        country_name=country_name,
        region_code=region_code,
        region_name=region_name,
    )


BERLIN = _locality(
    "de-berlin",
    "Berlin",
    "DE",
    "Germany",
    region_code="BE",
    region_name="Berlin",
)
PARIS_FR = _locality(
    "fr-paris",
    "Paris",
    "FR",
    "France",
    region_code="IDF",
    region_name="Île-de-France",
)
PARIS_US = _locality(
    "us-paris-tx",
    "Paris",
    "US",
    "United States",
    region_code="TX",
    region_name="Texas",
)
SPRINGFIELD_IL = _locality(
    "us-springfield-il",
    "Springfield",
    "US",
    "United States",
    region_code="IL",
    region_name="Illinois",
)
SPRINGFIELD_MA = _locality(
    "us-springfield-ma",
    "Springfield",
    "US",
    "United States",
    region_code="MA",
    region_name="Massachusetts",
)


def test_resolves_one_unambiguous_locality() -> None:
    resolver = InMemoryLocationResolver(
        records=(BERLIN,),
        reference_data_version=REFERENCE_DATA_VERSION,
    )

    result = resolver.resolve("  BERLIN\t", level=ResolutionLevel.LOCALITY)

    assert isinstance(result, Resolved)
    assert result.normalized_value == "berlin"
    assert result.selected_record_id == "de-berlin"
    assert result.resolution.level is ResolutionLevel.LOCALITY
    assert result.resolution.canonical_name == "Berlin"
    assert result.matches[0].record_id == "de-berlin"
    assert result.reference_data_version == REFERENCE_DATA_VERSION


def test_same_name_in_several_countries_is_ambiguous_without_common_resolution() -> None:
    resolver = InMemoryLocationResolver(
        records=(PARIS_US, PARIS_FR),
        reference_data_version=REFERENCE_DATA_VERSION,
    )

    result = resolver.resolve("Paris", level=ResolutionLevel.LOCALITY)

    assert isinstance(result, Ambiguous)
    assert result.ambiguous_at is ResolutionLevel.LOCALITY
    assert result.common_resolution is None
    assert tuple(match.record_id for match in result.matches) == (
        "fr-paris",
        "us-paris-tx",
    )


def test_several_places_in_one_country_are_ambiguous_with_country_resolution() -> None:
    resolver = InMemoryLocationResolver(
        records=(SPRINGFIELD_MA, SPRINGFIELD_IL),
        reference_data_version=REFERENCE_DATA_VERSION,
    )

    result = resolver.resolve("Springfield", level=ResolutionLevel.LOCALITY)

    assert isinstance(result, Ambiguous)
    assert result.ambiguous_at is ResolutionLevel.LOCALITY
    assert result.common_resolution == ScopeResolution(
        level=ResolutionLevel.COUNTRY,
        canonical_name="United States",
        country_code="US",
        supporting_record_ids=(
            "us-springfield-il",
            "us-springfield-ma",
        ),
    )
    assert all(match.level is ResolutionLevel.LOCALITY for match in result.matches)


@pytest.mark.parametrize("value", ["Atlantis", "", " \t\n "])
def test_no_match_and_blank_input_are_unresolved(value: str) -> None:
    resolver = InMemoryLocationResolver(
        records=(BERLIN,),
        reference_data_version=REFERENCE_DATA_VERSION,
    )

    result = resolver.resolve(value, level=ResolutionLevel.LOCALITY)

    assert isinstance(result, Unresolved)
    assert result.input_value == value
    assert result.normalized_value == normalize_location(value)
    assert result.matches == ()
    assert result.attempted_at is ResolutionLevel.LOCALITY


def test_alias_leading_to_several_records_is_ambiguous() -> None:
    saint_mary_ca = _locality(
        "ca-saint-mary",
        "Saint Mary",
        "CA",
        "Canada",
        region_code="ON",
        region_name="Ontario",
    )
    saint_mary_gb = _locality(
        "gb-saint-mary",
        "Saint Mary",
        "GB",
        "United Kingdom",
        region_code="ENG",
        region_name="England",
    )
    resolver = InMemoryLocationResolver(
        records=(saint_mary_gb, saint_mary_ca),
        aliases={"St. Mary": ("gb-saint-mary", "ca-saint-mary")},
        reference_data_version=REFERENCE_DATA_VERSION,
    )

    result = resolver.resolve("ST. MARY", level=ResolutionLevel.LOCALITY)

    assert isinstance(result, Ambiguous)
    assert result.common_resolution is None
    assert tuple(match.match_kind for match in result.matches) == (
        MatchKind.ALIAS,
        MatchKind.ALIAS,
    )
    assert {match.matched_name for match in result.matches} == {"St. Mary"}


def test_aliases_are_deduplicated_by_record_id_before_outcome() -> None:
    resolver = InMemoryLocationResolver(
        records=(BERLIN,),
        aliases={
            " BERLIN ": ("de-berlin", "de-berlin"),
            "ＢＥＲＬＩＮ": ("de-berlin",),
        },
        reference_data_version=REFERENCE_DATA_VERSION,
    )

    result = resolver.resolve("ＢＥＲＬＩＮ", level=ResolutionLevel.LOCALITY)

    assert isinstance(result, Resolved)
    assert tuple(match.record_id for match in result.matches) == ("de-berlin",)
    assert result.matches[0].match_kind is MatchKind.CANONICAL


def test_normalization_is_nfkc_casefold_whitespace_only() -> None:
    assert normalize_location("  ＭÜNCHEN\tStraße\n") == "münchen strasse"
    assert normalize_location("München") != normalize_location("Munchen")


def test_resolution_rejects_duplicate_matches() -> None:
    with pytest.raises(ValueError, match="unique record_id"):
        Ambiguous(
            input_value="Berlin",
            normalized_value="berlin",
            matches=(BERLIN, BERLIN),
            reference_data_version=REFERENCE_DATA_VERSION,
            ambiguous_at=ResolutionLevel.LOCALITY,
            common_resolution=None,
        )


def test_resolution_rejects_unsorted_matches() -> None:
    with pytest.raises(ValueError, match="stably sorted"):
        Ambiguous(
            input_value="Paris",
            normalized_value="paris",
            matches=(PARIS_US, PARIS_FR),
            reference_data_version=REFERENCE_DATA_VERSION,
            ambiguous_at=ResolutionLevel.LOCALITY,
            common_resolution=None,
        )


@pytest.mark.parametrize(
    "supporting_record_ids",
    [(), ("b", "a"), ("a", "a")],
)
def test_scope_resolution_rejects_invalid_supporting_record_ids(
    supporting_record_ids: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError, match="supporting_record_ids"):
        ScopeResolution(
            level=ResolutionLevel.COUNTRY,
            canonical_name="France",
            country_code="FR",
            supporting_record_ids=supporting_record_ids,
        )


def test_common_resolution_rejects_matches_from_different_countries() -> None:
    with pytest.raises(ValueError, match="one non-empty country_code"):
        Ambiguous(
            input_value="Paris",
            normalized_value="paris",
            matches=(PARIS_FR, PARIS_US),
            reference_data_version=REFERENCE_DATA_VERSION,
            ambiguous_at=ResolutionLevel.LOCALITY,
            common_resolution=ScopeResolution(
                level=ResolutionLevel.COUNTRY,
                canonical_name="France",
                country_code="FR",
                supporting_record_ids=("fr-paris", "us-paris-tx"),
            ),
        )


def test_resolved_rejects_selected_record_outside_matches() -> None:
    with pytest.raises(ValueError, match="selected_record_id"):
        Resolved(
            input_value="Berlin",
            normalized_value="berlin",
            matches=(BERLIN,),
            reference_data_version=REFERENCE_DATA_VERSION,
            resolution=ScopeResolution(
                level=ResolutionLevel.LOCALITY,
                canonical_name="Berlin",
                country_code="DE",
                region_code="BE",
                supporting_record_ids=("not-berlin",),
            ),
            selected_record_id="not-berlin",
        )


def test_resolved_rejects_selected_record_at_another_level() -> None:
    with pytest.raises(ValueError, match="resolved level"):
        Resolved(
            input_value="Berlin",
            normalized_value="berlin",
            matches=(BERLIN,),
            reference_data_version=REFERENCE_DATA_VERSION,
            resolution=ScopeResolution(
                level=ResolutionLevel.COUNTRY,
                canonical_name="Berlin",
                country_code="DE",
                supporting_record_ids=("de-berlin",),
            ),
            selected_record_id="de-berlin",
        )


def test_resolved_rejects_region_inconsistent_with_selected_record() -> None:
    with pytest.raises(ValueError, match="resolved region code"):
        Resolved(
            input_value="Berlin",
            normalized_value="berlin",
            matches=(BERLIN,),
            reference_data_version=REFERENCE_DATA_VERSION,
            resolution=ScopeResolution(
                level=ResolutionLevel.LOCALITY,
                canonical_name="Berlin",
                country_code="DE",
                region_code="XX",
                supporting_record_ids=("de-berlin",),
            ),
            selected_record_id="de-berlin",
        )


def test_unresolved_rejects_matches() -> None:
    with pytest.raises(ValueError, match="cannot contain matches"):
        Unresolved(
            input_value="Berlin",
            normalized_value="berlin",
            matches=(BERLIN,),
            reference_data_version=REFERENCE_DATA_VERSION,
            attempted_at=ResolutionLevel.LOCALITY,
        )


def test_in_memory_resolver_rejects_unknown_alias_record() -> None:
    with pytest.raises(ValueError, match="unknown record_id"):
        InMemoryLocationResolver(
            records=(BERLIN,),
            aliases={"Berlyn": ("missing",)},
            reference_data_version=REFERENCE_DATA_VERSION,
        )
