import json
import os
from pathlib import Path

import pytest
from cv_validator.config import (
    LocationConfigurationError,
    load_location_resolver,
    load_postal_code_resolver,
)
from cv_validator.location import (
    ResolutionLevel,
    SQLiteLocationResolver,
    SQLitePostalCodeResolver,
    build_postal_index,
)
from cv_validator.location.index import SourceSpec, build_location_index


FIXTURES = Path(__file__).parent / "fixtures" / "geonames"
INDEX_ENV = "CV_VALIDATOR_LOCATION_INDEX_PATH"
MANIFEST_ENV = "CV_VALIDATOR_LOCATION_MANIFEST_PATH"
POSTAL_INDEX_ENV = "CV_VALIDATOR_POSTAL_INDEX_PATH"
POSTAL_MANIFEST_ENV = "CV_VALIDATOR_POSTAL_MANIFEST_PATH"


def _build_pair(directory: Path) -> tuple[Path, Path]:
    index_path = directory / "locations.sqlite3"
    manifest_path = directory / "locations.manifest.json"
    build_location_index(
        cities500=SourceSpec(FIXTURES / "cities500.txt", "https://example.test/cities500"),
        country_info=SourceSpec(FIXTURES / "countryInfo.txt", "https://example.test/countryInfo"),
        alternate_names=SourceSpec(
            FIXTURES / "alternateNamesV2.txt",
            "https://example.test/alternateNamesV2",
        ),
        snapshot_date="2026-08-21",
        output_index=index_path,
        output_manifest=manifest_path,
    )
    return index_path, manifest_path


def _clear_location_env(monkeypatch) -> None:
    monkeypatch.delenv(INDEX_ENV, raising=False)
    monkeypatch.delenv(MANIFEST_ENV, raising=False)


def test_no_location_paths_disables_the_runtime_resolver(monkeypatch) -> None:
    _clear_location_env(monkeypatch)

    assert load_location_resolver() is None


def test_required_location_resolver_fails_loudly_without_paths(monkeypatch) -> None:
    _clear_location_env(monkeypatch)

    with pytest.raises(LocationConfigurationError, match="required"):
        load_location_resolver(required=True)


@pytest.mark.parametrize("configured", [INDEX_ENV, MANIFEST_ENV])
def test_exactly_one_location_path_is_a_configuration_error(
    monkeypatch,
    configured: str,
) -> None:
    _clear_location_env(monkeypatch)
    monkeypatch.setenv(configured, "/operator/reference-data/file")

    with pytest.raises(LocationConfigurationError, match="must be set together"):
        load_location_resolver()


def test_valid_pair_creates_one_sqlite_resolver(monkeypatch, tmp_path) -> None:
    index_path, manifest_path = _build_pair(tmp_path)
    monkeypatch.setenv(INDEX_ENV, str(index_path))
    monkeypatch.setenv(MANIFEST_ENV, str(manifest_path))

    resolver = load_location_resolver()

    assert isinstance(resolver, SQLiteLocationResolver)
    assert resolver.resolve("Berlin", level=ResolutionLevel.LOCALITY).matches
    resolver.close()


def test_invalid_pair_fails_during_configuration(monkeypatch, tmp_path) -> None:
    index_path, manifest_path = _build_pair(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv(INDEX_ENV, str(index_path))
    monkeypatch.setenv(MANIFEST_ENV, str(manifest_path))

    with pytest.raises(
        LocationConfigurationError,
        match="configured location reference-data pair is invalid",
    ):
        load_location_resolver()


def test_optional_postal_pair_is_loaded_together(monkeypatch, tmp_path) -> None:
    source = Path(__file__).parent / "fixtures" / "postal" / "allCountries.txt"
    index = tmp_path / "postal-codes.sqlite3"
    manifest = tmp_path / "postal-codes.manifest.json"
    build_postal_index(
        source_path=source,
        source_url="https://example.test/postal",
        snapshot_date="2026-09-02",
        output_index=index,
        output_manifest=manifest,
    )
    monkeypatch.setenv(POSTAL_INDEX_ENV, str(index))
    monkeypatch.setenv(POSTAL_MANIFEST_ENV, str(manifest))

    resolver = load_postal_code_resolver()

    assert isinstance(resolver, SQLitePostalCodeResolver)
    assert resolver.validate("00-001", city="Warsaw", country_code="PL").status == "resolved"
    resolver.close()


def test_missing_or_empty_postal_configuration_is_unavailable(monkeypatch) -> None:
    monkeypatch.delenv(POSTAL_INDEX_ENV, raising=False)
    monkeypatch.delenv(POSTAL_MANIFEST_ENV, raising=False)
    assert load_postal_code_resolver() is None
    monkeypatch.setenv(POSTAL_INDEX_ENV, "")
    monkeypatch.setenv(POSTAL_MANIFEST_ENV, "")
    assert load_postal_code_resolver() is None


def test_partial_postal_configuration_fails_loudly(monkeypatch) -> None:
    monkeypatch.setenv(POSTAL_INDEX_ENV, "/reference/postal.sqlite3")
    monkeypatch.delenv(POSTAL_MANIFEST_ENV, raising=False)

    with pytest.raises(LocationConfigurationError, match="must be set together"):
        load_postal_code_resolver()


def test_base_compose_bootstraps_persistent_read_only_reference_data() -> None:
    root = (
        Path(os.environ["CV_VALIDATOR_REPO_ROOT"])
        if "CV_VALIDATOR_REPO_ROOT" in os.environ
        else Path(__file__).resolve().parents[3]
    )
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (root / "apps/api/Dockerfile").read_text(encoding="utf-8")
    dockerignore = (root / "apps/api/.dockerignore").read_text(encoding="utf-8")
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")

    assert "CV_VALIDATOR_REQUIRE_LOCATION_RESOLVER: \"true\"" in compose
    assert "CV_VALIDATOR_AI_ENABLED: ${CV_VALIDATOR_AI_ENABLED:-true}" in compose
    assert "CV_VALIDATOR_LOCATION_INDEX_PATH: /app/reference-data/current/locations.sqlite3" in compose
    assert "CV_VALIDATOR_LOCATION_MANIFEST_PATH: /app/reference-data/current/locations.manifest.json" in compose
    assert "CV_VALIDATOR_POSTAL_INDEX_PATH: /app/reference-data/current/postal-codes.sqlite3" in compose
    assert "CV_VALIDATOR_POSTAL_MANIFEST_PATH: /app/reference-data/current/postal-codes.manifest.json" in compose
    assert "geonames-init:" in compose
    assert "condition: service_completed_successfully" in compose
    assert "geonames_data:/reference-data" in compose
    assert "source: geonames_data" in compose
    assert "read_only: true" in compose
    assert "reference-data" not in dockerfile
    assert "data" in dockerignore.splitlines()
    assert "data/" in gitignore.splitlines()


def test_optional_compose_overlay_bypasses_initializer_with_read_only_directory() -> None:
    root = (
        Path(os.environ["CV_VALIDATOR_REPO_ROOT"])
        if "CV_VALIDATOR_REPO_ROOT" in os.environ
        else Path(__file__).resolve().parents[3]
    )
    overlay = (root / "docker-compose.reference-data.yml").read_text(
        encoding="utf-8"
    )

    assert "CV_VALIDATOR_REFERENCE_DATA_DIR:?" in overlay
    assert 'command: ["true"]' in overlay
    assert "volumes: !override" in overlay
    assert "read_only: true" in overlay
    assert "create_host_path: false" in overlay
