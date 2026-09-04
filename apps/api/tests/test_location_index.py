import hashlib
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import zipfile
from pathlib import Path

import pytest

from cv_validator.location import (
    Ambiguous,
    ResolutionLevel,
    Resolved,
    SQLiteLocationResolver,
    Unresolved,
)
from cv_validator.location.index import SourceSpec, build_location_index
from cv_validator.location.validation import (
    LocationIndexValidationError,
    validate_location_index,
)


FIXTURES = Path(__file__).parent / "fixtures" / "geonames"


@pytest.fixture
def sqlite_resolver(tmp_path: Path) -> SQLiteLocationResolver:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    _build_fixture_index(index_path, manifest_path)
    return SQLiteLocationResolver(index_path, manifest_path)


def test_builder_creates_index_resolved_by_sqlite_runtime(tmp_path: Path) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"

    _build_fixture_index(index_path, manifest_path)

    resolver = SQLiteLocationResolver(index_path, manifest_path)
    result = resolver.resolve("  BERLIN ", level=ResolutionLevel.LOCALITY)

    assert isinstance(result, Resolved)
    assert result.selected_record_id == "geonames:2950159"
    assert result.resolution.country_code == "DE"
    assert result.reference_data_version.name == "geonames-sqlite"
    assert result.reference_data_version.version.startswith("geonames-2026-08-21-")


def test_sqlite_resolver_preserves_ambiguity_semantics(
    sqlite_resolver: SQLiteLocationResolver,
) -> None:
    cross_country = sqlite_resolver.resolve(
        "Paris",
        level=ResolutionLevel.LOCALITY,
    )
    same_country = sqlite_resolver.resolve(
        "Springfield",
        level=ResolutionLevel.LOCALITY,
    )

    assert isinstance(cross_country, Ambiguous)
    assert cross_country.common_resolution is None
    assert isinstance(same_country, Ambiguous)
    assert same_country.common_resolution is not None
    assert same_country.common_resolution.country_code == "US"


@pytest.mark.parametrize(
    ("value", "alias_kind"),
    [
        ("Berlyn", "alternate"),
        ("Berlin Preferred", "preferred"),
        ("Berlin Short", "short"),
    ],
)
def test_current_supported_aliases_resolve(
    sqlite_resolver: SQLiteLocationResolver,
    value: str,
    alias_kind: str,
) -> None:
    result = sqlite_resolver.resolve(value, level=ResolutionLevel.LOCALITY)

    assert isinstance(result, Resolved), alias_kind
    assert result.selected_record_id == "geonames:2950159"


@pytest.mark.parametrize(
    "value",
    [
        "Old Berlin",
        "Big Berlin",
        "Past Berlin",
        "BER",
        "10115",
        "EDDB",
        "BML",
        "https://example.test/berlin",
        "Q64",
        "Berlín révolutionnaire",
        "Orphan Alias",
    ],
)
def test_excluded_aliases_are_unresolved(
    sqlite_resolver: SQLiteLocationResolver,
    value: str,
) -> None:
    result = sqlite_resolver.resolve(value, level=ResolutionLevel.LOCALITY)

    assert isinstance(result, Unresolved)


def test_country_codes_resolve_only_at_country_level(
    sqlite_resolver: SQLiteLocationResolver,
) -> None:
    country = sqlite_resolver.resolve("DEU", level=ResolutionLevel.COUNTRY)
    locality = sqlite_resolver.resolve("DEU", level=ResolutionLevel.LOCALITY)

    assert isinstance(country, Resolved)
    assert country.resolution.country_code == "DE"
    assert isinstance(locality, Unresolved)


def test_region_level_is_explicitly_unsupported(
    sqlite_resolver: SQLiteLocationResolver,
) -> None:
    result = sqlite_resolver.resolve("Berlin", level=ResolutionLevel.REGION)

    assert isinstance(result, Unresolved)


def test_repeated_build_is_bit_identical_with_same_toolchain(tmp_path: Path) -> None:
    first_index = tmp_path / "first.sqlite3"
    first_manifest = tmp_path / "first.manifest.json"
    second_index = tmp_path / "second.sqlite3"
    second_manifest = tmp_path / "second.manifest.json"

    first = _build_fixture_index(first_index, first_manifest)
    second = _build_fixture_index(second_index, second_manifest)

    assert first_index.read_bytes() == second_index.read_bytes()
    assert first["artifact"]["sha256"] == second["artifact"]["sha256"]


def test_validator_checks_manifest_against_index(tmp_path: Path) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    manifest = _build_fixture_index(index_path, manifest_path)

    validated = validate_location_index(index_path, manifest_path)

    assert validated["reference_data_version"] == manifest["reference_data_version"]
    assert validated["counts"]["records_locality"] == 5
    assert validated["counts"]["alternate_filtered_historic"] == 1
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest


def test_validator_rejects_manifest_schema_violation(tmp_path: Path) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    manifest = _build_fixture_index(index_path, manifest_path)
    manifest["unexpected"] = True
    _write_manifest(manifest_path, manifest)

    with pytest.raises(LocationIndexValidationError, match="schema violation"):
        validate_location_index(index_path, manifest_path)


def test_validator_rejects_missing_required_count_as_controlled_error(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    manifest = _build_fixture_index(index_path, manifest_path)
    del manifest["counts"]["records_total"]
    _write_manifest(manifest_path, manifest)

    with pytest.raises(LocationIndexValidationError, match="schema violation"):
        validate_location_index(index_path, manifest_path)


def test_validator_rejects_manifest_counts_different_from_index(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    manifest = _build_fixture_index(index_path, manifest_path)
    manifest["counts"]["names_total"] += 1
    _write_manifest(manifest_path, manifest)

    with pytest.raises(LocationIndexValidationError, match="metadata mismatch"):
        validate_location_index(index_path, manifest_path)


def test_validator_rejects_extra_sqlite_schema_object(tmp_path: Path) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    manifest = _build_fixture_index(index_path, manifest_path)
    with sqlite3.connect(index_path) as connection:
        connection.execute("CREATE VIEW unexpected_view AS SELECT 1 AS value")
    _refresh_artifact_metadata(manifest, index_path)
    _write_manifest(manifest_path, manifest)

    with pytest.raises(LocationIndexValidationError, match="schema.*allowlist"):
        validate_location_index(index_path, manifest_path)


def test_validator_rejects_table_with_unexpected_column(tmp_path: Path) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    manifest = _build_fixture_index(index_path, manifest_path)
    with sqlite3.connect(index_path) as connection:
        connection.execute("ALTER TABLE build_stat ADD COLUMN unexpected TEXT")
    _refresh_artifact_metadata(manifest, index_path)
    _write_manifest(manifest_path, manifest)

    with pytest.raises(LocationIndexValidationError, match="table definition"):
        validate_location_index(index_path, manifest_path)


def test_manifest_has_auditable_source_and_result_counts(tmp_path: Path) -> None:
    manifest = _build_fixture_index(
        tmp_path / "locations.sqlite3",
        tmp_path / "locations.manifest.json",
    )

    assert manifest["counts"]["country_rows_total"] == 3
    assert manifest["counts"]["city_rows_total"] == 5
    assert manifest["counts"]["normalized_keys_distinct"] > 0
    assert manifest["counts"]["normalized_keys_ambiguous"] == 2
    assert manifest["builder"]["python_version"]
    assert manifest["license"]["warranty_notice"]


def test_sqlite_resolver_reads_file_without_write_permission(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    _build_fixture_index(index_path, manifest_path)
    index_path.chmod(0o444)

    result = SQLiteLocationResolver(index_path, manifest_path).resolve(
        "Berlin",
        level=ResolutionLevel.LOCALITY,
    )

    assert isinstance(result, Resolved)


def test_validator_rejects_corrupt_sqlite_with_matching_artifact_hash(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    manifest = _build_fixture_index(index_path, manifest_path)
    index_path.write_bytes(index_path.read_bytes()[:128])
    _refresh_artifact_metadata(manifest, index_path)
    _write_manifest(manifest_path, manifest)

    with pytest.raises(LocationIndexValidationError, match="invalid SQLite"):
        validate_location_index(index_path, manifest_path)


def test_validator_rejects_foreign_key_violation(tmp_path: Path) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    manifest = _build_fixture_index(index_path, manifest_path)
    with sqlite3.connect(index_path) as connection:
        connection.execute(
            """INSERT INTO location_name VALUES (
                'missing', 'geonames:missing', 'Missing', 'alias',
                'alternate', 'en', 999999, 0, 0
            )"""
        )
    _refresh_artifact_metadata(manifest, index_path)
    _write_manifest(manifest_path, manifest)

    with pytest.raises(LocationIndexValidationError, match="foreign key"):
        validate_location_index(index_path, manifest_path)


def test_validator_rejects_unsupported_sqlite_version(tmp_path: Path) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    manifest = _build_fixture_index(index_path, manifest_path)
    with sqlite3.connect(index_path) as connection:
        connection.execute("PRAGMA user_version = 999")
    _refresh_artifact_metadata(manifest, index_path)
    _write_manifest(manifest_path, manifest)

    with pytest.raises(LocationIndexValidationError, match="user_version"):
        validate_location_index(index_path, manifest_path)


def test_validator_rejects_source_different_from_manifest(tmp_path: Path) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    _build_fixture_index(index_path, manifest_path)
    modified_cities = tmp_path / "cities500.txt"
    modified_cities.write_text("changed\n", encoding="utf-8")

    with pytest.raises(LocationIndexValidationError, match="cities500"):
        validate_location_index(
            index_path,
            manifest_path,
            source_paths={
                "cities500": modified_cities,
                "country_info": FIXTURES / "countryInfo.txt",
                "alternate_names_v2": FIXTURES / "alternateNamesV2.txt",
            },
        )


def test_sqlite_resolver_does_not_create_wal_or_shm(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    _build_fixture_index(index_path, manifest_path)

    resolver = SQLiteLocationResolver(index_path, manifest_path)
    resolver.resolve("Berlin", level=ResolutionLevel.LOCALITY)

    assert not index_path.with_name(f"{index_path.name}-wal").exists()
    assert not index_path.with_name(f"{index_path.name}-shm").exists()


def test_sqlite_resolver_keeps_validated_snapshot_after_path_replacement(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    _build_fixture_index(index_path, manifest_path)
    resolver = SQLiteLocationResolver(index_path, manifest_path)
    replacement_index = tmp_path / "replacement.sqlite3"
    replacement_manifest = tmp_path / "replacement.manifest.json"
    _build_fixture_index(replacement_index, replacement_manifest)
    with sqlite3.connect(replacement_index) as connection:
        connection.execute(
            "DELETE FROM location_name WHERE normalized_name = 'berlin'"
        )
    replacement_index.replace(index_path)

    try:
        result = resolver.resolve("Berlin", level=ResolutionLevel.LOCALITY)
    finally:
        resolver.close()

    assert isinstance(result, Resolved)


def test_sqlite_resolver_close_is_controlled(tmp_path: Path) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    _build_fixture_index(index_path, manifest_path)
    resolver = SQLiteLocationResolver(index_path, manifest_path)

    resolver.close()

    with pytest.raises(RuntimeError, match="closed"):
        resolver.resolve("Berlin", level=ResolutionLevel.LOCALITY)
    with pytest.raises(RuntimeError, match="closed"):
        resolver.resolve("", level=ResolutionLevel.LOCALITY)
    with pytest.raises(RuntimeError, match="closed"):
        resolver.resolve("Berlin", level=ResolutionLevel.REGION)


def test_sqlite_resolver_supports_concurrent_resolve_calls(tmp_path: Path) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    _build_fixture_index(index_path, manifest_path)

    with SQLiteLocationResolver(index_path, manifest_path) as resolver:
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = tuple(
                executor.map(
                    lambda _: resolver.resolve(
                        "Berlin",
                        level=ResolutionLevel.LOCALITY,
                    ),
                    range(64),
                )
            )

    assert all(isinstance(result, Resolved) for result in results)


def test_sqlite_resolver_resolve_close_race_is_controlled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    _build_fixture_index(index_path, manifest_path)
    resolver = SQLiteLocationResolver(index_path, manifest_path)
    entered_resolve = Event()
    allow_resolve = Event()
    from cv_validator.location import sqlite_resolver as resolver_module

    real_normalize = resolver_module.normalize_location

    def blocking_normalize(value: str) -> str:
        entered_resolve.set()
        assert allow_resolve.wait(timeout=5)
        return real_normalize(value)

    monkeypatch.setattr(resolver_module, "normalize_location", blocking_normalize)

    with ThreadPoolExecutor(max_workers=2) as executor:
        resolve_future = executor.submit(
            resolver.resolve,
            "Berlin",
            level=ResolutionLevel.LOCALITY,
        )
        assert entered_resolve.wait(timeout=5)
        close_future = executor.submit(resolver.close)
        assert not close_future.done()
        allow_resolve.set()
        resolved = resolve_future.result(timeout=5)
        close_future.result(timeout=5)

    assert isinstance(resolved, Resolved)
    with pytest.raises(RuntimeError, match="closed"):
        resolver.resolve("Berlin", level=ResolutionLevel.LOCALITY)


def test_sqlite_resolver_fails_closed_when_path_changes_during_init(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    _build_fixture_index(index_path, manifest_path)
    replacement_index = tmp_path / "replacement.sqlite3"
    replacement_manifest = tmp_path / "replacement.manifest.json"
    _build_fixture_index(replacement_index, replacement_manifest)
    from cv_validator.location import sqlite_resolver as resolver_module

    real_validate = resolver_module.validate_location_index

    def replacing_validate(*args: object, **kwargs: object) -> dict[str, object]:
        manifest = real_validate(*args, **kwargs)
        replacement_index.replace(index_path)
        return manifest

    monkeypatch.setattr(resolver_module, "validate_location_index", replacing_validate)

    with pytest.raises(LocationIndexValidationError, match="changed during"):
        SQLiteLocationResolver(index_path, manifest_path)


def test_builder_accepts_official_zip_layout_and_hashes_members(
    tmp_path: Path,
) -> None:
    cities_zip = tmp_path / "cities500.zip"
    aliases_zip = tmp_path / "alternateNamesV2.zip"
    _zip_fixture(cities_zip, "cities500.txt", FIXTURES / "cities500.txt")
    with zipfile.ZipFile(
        aliases_zip,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            "alternateNamesV2.txt",
            (FIXTURES / "alternateNamesV2.txt").read_bytes(),
        )
        archive.writestr(
            "iso-languagecodes.txt",
            b"ISO 639-3\tISO 639-2\tISO 639-1\tlanguage name\n",
        )
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"

    manifest = build_location_index(
        cities500=SourceSpec(cities_zip, "https://example.test/cities500.zip"),
        country_info=SourceSpec(
            FIXTURES / "countryInfo.txt",
            "https://example.test/countryInfo.txt",
        ),
        alternate_names=SourceSpec(
            aliases_zip,
            "https://example.test/alternateNamesV2.zip",
        ),
        snapshot_date="2026-08-21",
        output_index=index_path,
        output_manifest=manifest_path,
    )

    sources = {source["role"]: source for source in manifest["sources"]}
    assert sources["cities500"]["archive_member"] == "cities500.txt"
    assert len(sources["cities500"]["member_sha256"]) == 64
    assert sources["alternate_names_v2"]["archive_member"] == "alternateNamesV2.txt"
    with SQLiteLocationResolver(index_path, manifest_path) as resolver:
        assert isinstance(
            resolver.resolve("Berlin", level=ResolutionLevel.LOCALITY),
            Resolved,
        )


def test_builder_streams_source_files_and_zip_members(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cities_zip = tmp_path / "cities500.zip"
    aliases_zip = tmp_path / "alternateNamesV2.zip"
    _zip_fixture(cities_zip, "cities500.txt", FIXTURES / "cities500.txt")
    with zipfile.ZipFile(aliases_zip, "w") as archive:
        archive.writestr(
            "alternateNamesV2.txt",
            (FIXTURES / "alternateNamesV2.txt").read_bytes(),
        )
        archive.writestr("iso-languagecodes.txt", b"codes\n")

    def forbidden_read_bytes(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("builder must stream Path content")

    def forbidden_zip_read(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("builder must stream ZIP members")

    monkeypatch.setattr(Path, "read_bytes", forbidden_read_bytes)
    monkeypatch.setattr(zipfile.ZipFile, "read", forbidden_zip_read)

    manifest = build_location_index(
        cities500=SourceSpec(cities_zip, "https://example.test/cities500.zip"),
        country_info=SourceSpec(
            FIXTURES / "countryInfo.txt",
            "https://example.test/countryInfo.txt",
        ),
        alternate_names=SourceSpec(
            aliases_zip,
            "https://example.test/alternateNamesV2.zip",
        ),
        snapshot_date="2026-08-21",
        output_index=tmp_path / "locations.sqlite3",
        output_manifest=tmp_path / "locations.manifest.json",
    )

    assert manifest["counts"]["records_locality"] == 5


@pytest.mark.parametrize(
    "unexpected_member",
    ["unexpected.txt", "../alternateNamesV2.txt", "nested/alternateNamesV2.txt"],
)
def test_builder_rejects_unapproved_zip_members(
    tmp_path: Path,
    unexpected_member: str,
) -> None:
    aliases_zip = tmp_path / "alternateNamesV2.zip"
    with zipfile.ZipFile(aliases_zip, "w") as archive:
        archive.writestr(
            "alternateNamesV2.txt",
            (FIXTURES / "alternateNamesV2.txt").read_bytes(),
        )
        archive.writestr(unexpected_member, b"unexpected")

    with pytest.raises(ValueError, match="approved members"):
        build_location_index(
            cities500=SourceSpec(
                FIXTURES / "cities500.txt",
                "https://example.test/cities500.zip",
            ),
            country_info=SourceSpec(
                FIXTURES / "countryInfo.txt",
                "https://example.test/countryInfo.txt",
            ),
            alternate_names=SourceSpec(
                aliases_zip,
                "https://example.test/alternateNamesV2.zip",
            ),
            snapshot_date="2026-08-21",
            output_index=tmp_path / "locations.sqlite3",
            output_manifest=tmp_path / "locations.manifest.json",
        )


def test_builder_rejects_aliasing_output_paths(tmp_path: Path) -> None:
    output = tmp_path / "artifact"

    with pytest.raises(ValueError, match="distinct"):
        _build_fixture_index(output, output)


def test_builder_rejects_hardlink_aliasing_output_paths(tmp_path: Path) -> None:
    index_path = tmp_path / "index"
    manifest_path = tmp_path / "manifest"
    index_path.touch()
    os.link(index_path, manifest_path)

    with pytest.raises(ValueError, match="distinct"):
        _build_fixture_index(index_path, manifest_path)


def test_builder_removes_partial_pair_when_manifest_publish_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    real_link = os.link

    def failing_link(source: Path | str, destination: Path | str) -> None:
        if Path(destination) == manifest_path:
            raise OSError("injected manifest publish failure")
        real_link(source, destination)

    monkeypatch.setattr("cv_validator.location.index.os.link", failing_link)

    with pytest.raises(OSError, match="injected manifest"):
        _build_fixture_index(index_path, manifest_path)

    assert not index_path.exists()
    assert not manifest_path.exists()
    assert not tuple(tmp_path.glob(".*.tmp"))
    assert not tuple(tmp_path.glob("*-wal"))
    assert not tuple(tmp_path.glob("*-shm"))
    assert not tuple(tmp_path.glob("*-journal"))


def test_builder_never_removes_or_overwrites_racing_foreign_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    real_link = os.link

    def racing_link(source: Path | str, destination: Path | str) -> None:
        destination_path = Path(destination)
        if destination_path == index_path:
            destination_path.write_bytes(b"foreign artifact")
            raise FileExistsError(destination_path)
        real_link(source, destination)

    monkeypatch.setattr("cv_validator.location.index.os.link", racing_link)

    with pytest.raises(FileExistsError):
        _build_fixture_index(index_path, manifest_path)

    assert index_path.read_bytes() == b"foreign artifact"
    assert not manifest_path.exists()


def test_builder_leaves_no_sqlite_sidecars(tmp_path: Path) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"

    _build_fixture_index(index_path, manifest_path)

    with sqlite3.connect(index_path) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    for suffix in ("-wal", "-shm", "-journal"):
        assert not index_path.with_name(f"{index_path.name}{suffix}").exists()


def test_builder_rejects_zip_without_exact_expected_member(tmp_path: Path) -> None:
    cities_zip = tmp_path / "cities500.zip"
    _zip_fixture(cities_zip, "nested/cities500.txt", FIXTURES / "cities500.txt")

    with pytest.raises(ValueError, match="approved members"):
        build_location_index(
            cities500=SourceSpec(cities_zip, "https://example.test/cities500.zip"),
            country_info=SourceSpec(
                FIXTURES / "countryInfo.txt",
                "https://example.test/countryInfo.txt",
            ),
            alternate_names=SourceSpec(
                FIXTURES / "alternateNamesV2.txt",
                "https://example.test/alternateNamesV2.zip",
            ),
            snapshot_date="2026-08-21",
            output_index=tmp_path / "locations.sqlite3",
            output_manifest=tmp_path / "locations.manifest.json",
        )


def _build_fixture_index(
    index_path: Path,
    manifest_path: Path,
) -> dict[str, object]:
    return build_location_index(
        cities500=SourceSpec(
            path=FIXTURES / "cities500.txt",
            url="https://download.geonames.org/export/dump/cities500.zip",
        ),
        country_info=SourceSpec(
            path=FIXTURES / "countryInfo.txt",
            url="https://download.geonames.org/export/dump/countryInfo.txt",
        ),
        alternate_names=SourceSpec(
            path=FIXTURES / "alternateNamesV2.txt",
            url="https://download.geonames.org/export/dump/alternateNamesV2.zip",
        ),
        snapshot_date="2026-08-21",
        output_index=index_path,
        output_manifest=manifest_path,
    )


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _refresh_artifact_metadata(
    manifest: dict[str, object],
    index_path: Path,
) -> None:
    data = index_path.read_bytes()
    manifest["artifact"]["size_bytes"] = len(data)
    manifest["artifact"]["sha256"] = hashlib.sha256(data).hexdigest()


def _zip_fixture(zip_path: Path, member_name: str, source_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member_name, source_path.read_bytes())
