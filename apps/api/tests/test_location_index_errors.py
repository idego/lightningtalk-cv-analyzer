from pathlib import Path

import pytest

from cv_validator.location.index import (
    LocationIndexBuildError,
    SourceSpec,
    build_location_index,
)


FIXTURES = Path(__file__).parent / "fixtures" / "geonames"


def test_builder_rejects_non_populated_place_record(tmp_path: Path) -> None:
    cities = (FIXTURES / "cities500.txt").read_text(encoding="utf-8")
    cities = cities.replace("\tP\tPPLC\t", "\tA\tPPLC\t", 1)

    with pytest.raises(LocationIndexBuildError, match="feature class P"):
        _build_with_sources(tmp_path, cities=cities)


def test_builder_rejects_duplicate_geoname_id(tmp_path: Path) -> None:
    cities = (FIXTURES / "cities500.txt").read_text(encoding="utf-8")
    cities += cities.splitlines()[0] + "\n"

    with pytest.raises(LocationIndexBuildError, match="duplicate geoname id"):
        _build_with_sources(tmp_path, cities=cities)


def test_builder_rejects_unknown_country(tmp_path: Path) -> None:
    cities = (FIXTURES / "cities500.txt").read_text(encoding="utf-8")
    cities = cities.replace("\tDE\t\t16\t", "\tZZ\t\t16\t", 1)

    with pytest.raises(LocationIndexBuildError, match="unknown country code: ZZ"):
        _build_with_sources(tmp_path, cities=cities)


def test_builder_rejects_duplicate_alternate_name_id(tmp_path: Path) -> None:
    aliases = (FIXTURES / "alternateNamesV2.txt").read_text(encoding="utf-8")
    duplicate = aliases.splitlines()[0].replace("Berlin", "Berlin duplicate")
    aliases += duplicate + "\n"

    with pytest.raises(LocationIndexBuildError, match="duplicate alternate-name id"):
        _build_with_sources(tmp_path, aliases=aliases)


def test_builder_rejects_invalid_alternate_name_flag(tmp_path: Path) -> None:
    aliases = (FIXTURES / "alternateNamesV2.txt").read_text(encoding="utf-8")
    aliases = aliases.replace("\t1\t0\t0\t0\t", "\t2\t0\t0\t0\t", 1)

    with pytest.raises(LocationIndexBuildError, match="flags"):
        _build_with_sources(tmp_path, aliases=aliases)


def test_builder_wraps_invalid_alternate_name_id(tmp_path: Path) -> None:
    aliases = (FIXTURES / "alternateNamesV2.txt").read_text(encoding="utf-8")
    aliases = aliases.replace("1001\t", "not-an-id\t", 1)

    with pytest.raises(LocationIndexBuildError, match="alternateNameId"):
        _build_with_sources(tmp_path, aliases=aliases)


def test_builder_rejects_invalid_snapshot_date(tmp_path: Path) -> None:
    with pytest.raises(LocationIndexBuildError, match="snapshot_date"):
        _build_with_sources(tmp_path, snapshot_date="21-08-2026")


def test_builder_maps_country_info_by_header_name(tmp_path: Path) -> None:
    lines = (FIXTURES / "countryInfo.txt").read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    order = [4, 0, 16, 1, *[index for index in range(19) if index not in {0, 1, 4, 16}]]
    reordered = ["\t".join(header[index] for index in order)]
    reordered.extend(
        "\t".join(line.split("\t")[index] for index in order)
        for line in lines[1:]
    )

    _build_with_sources(tmp_path, countries="\n".join(reordered) + "\n")


def test_builder_wraps_invalid_numeric_field(tmp_path: Path) -> None:
    cities = (FIXTURES / "cities500.txt").read_text(encoding="utf-8")
    cities = cities.replace("2950159\t", "not-an-id\t", 1)

    with pytest.raises(LocationIndexBuildError, match="cities500.*geonameid"):
        _build_with_sources(tmp_path, cities=cities)


def test_builder_rejects_id_shared_by_country_and_locality(tmp_path: Path) -> None:
    cities = (FIXTURES / "cities500.txt").read_text(encoding="utf-8")
    cities = cities.replace("2950159\t", "2921044\t", 1)

    with pytest.raises(LocationIndexBuildError, match="country and locality"):
        _build_with_sources(tmp_path, cities=cities)


def _build_with_sources(
    tmp_path: Path,
    *,
    cities: str | None = None,
    countries: str | None = None,
    aliases: str | None = None,
    snapshot_date: str = "2026-08-21",
) -> None:
    cities_path = tmp_path / "cities500.txt"
    countries_path = tmp_path / "countryInfo.txt"
    aliases_path = tmp_path / "alternateNamesV2.txt"
    cities_path.write_text(
        cities
        if cities is not None
        else (FIXTURES / "cities500.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    countries_path.write_text(
        countries
        if countries is not None
        else (FIXTURES / "countryInfo.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    aliases_path.write_text(
        aliases
        if aliases is not None
        else (FIXTURES / "alternateNamesV2.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    build_location_index(
        cities500=SourceSpec(cities_path, "https://example.test/cities500.zip"),
        country_info=SourceSpec(
            countries_path,
            "https://example.test/countryInfo.txt",
        ),
        alternate_names=SourceSpec(
            aliases_path,
            "https://example.test/alternateNamesV2.zip",
        ),
        snapshot_date=snapshot_date,
        output_index=tmp_path / "locations.sqlite3",
        output_manifest=tmp_path / "locations.manifest.json",
    )
