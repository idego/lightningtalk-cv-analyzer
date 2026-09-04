from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from cv_validator.location.bootstrap import (
    ReferenceDataBootstrapError,
    bootstrap_reference_data,
)
from cv_validator.location.bootstrap_cli import main
from cv_validator.location.postal import SQLitePostalCodeResolver
from cv_validator.location.validation import validate_location_index


FIXTURES = Path(__file__).parent / "fixtures"
URLS = {
    "cities500": "https://example.test/cities500.zip",
    "country_info": "https://example.test/countryInfo.txt",
    "alternate_names": "https://example.test/alternateNamesV2.zip",
    "postal_codes": "https://example.test/allCountries.zip",
}


def _sources(tmp_path: Path) -> dict[str, Path]:
    sources = tmp_path / "sources"
    sources.mkdir()
    result = {"country_info": FIXTURES / "geonames" / "countryInfo.txt"}
    for role, fixture, member in (
        ("cities500", FIXTURES / "geonames" / "cities500.txt", "cities500.txt"),
        (
            "alternate_names",
            FIXTURES / "geonames" / "alternateNamesV2.txt",
            "alternateNamesV2.txt",
        ),
        ("postal_codes", FIXTURES / "postal" / "allCountries.txt", "allCountries.txt"),
    ):
        archive = sources / f"{role}.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
            output.write(fixture, member)
        result[role] = archive
    return result


def _downloader(sources: dict[str, Path], calls: list[str]):
    def download(url: str, destination: Path) -> None:
        calls.append(url)
        role = next(role for role, configured in URLS.items() if configured == url)
        shutil.copyfile(sources[role], destination)

    return download


def test_bootstrap_builds_and_reuses_a_complete_release(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    calls: list[str] = []
    target = tmp_path / "volume"

    release = bootstrap_reference_data(
        target,
        snapshot_version="2026-09-02",
        source_urls=URLS,
        downloader=_downloader(sources, calls),
    )

    assert len(calls) == 4
    assert (target / "current").resolve() == release
    validate_location_index(release / "locations.sqlite3", release / "locations.manifest.json")
    postal = SQLitePostalCodeResolver(
        release / "postal-codes.sqlite3", release / "postal-codes.manifest.json"
    )
    postal.close()
    assert json.loads((release / "release.json").read_text())["snapshot_version"] == "2026-09-02"

    bootstrap_reference_data(
        target,
        snapshot_version="2026-09-02",
        source_urls=URLS,
        downloader=lambda *_: pytest.fail("valid release must not download"),
    )


def test_failed_refresh_preserves_current_release_and_recovers_staging(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    target = tmp_path / "volume"
    first = bootstrap_reference_data(
        target,
        snapshot_version="2026-09-01",
        source_urls=URLS,
        downloader=_downloader(sources, []),
    )
    stale = target / ".staging-abandoned"
    stale.mkdir()

    def fail_download(_url: str, _destination: Path) -> None:
        raise OSError("network unavailable")

    with pytest.raises(ReferenceDataBootstrapError, match="network unavailable"):
        bootstrap_reference_data(
            target,
            snapshot_version="2026-09-02",
            source_urls=URLS,
            downloader=fail_download,
        )

    assert not stale.exists()
    assert (target / "current").resolve() == first
    assert not (target / "releases" / "2026-09-02").exists()

    second = bootstrap_reference_data(
        target,
        snapshot_version="2026-09-02",
        source_urls=URLS,
        downloader=_downloader(sources, []),
    )
    assert (target / "current").resolve() == second
    assert first.exists()

    third = bootstrap_reference_data(
        target,
        snapshot_version="2026-09-03",
        source_urls=URLS,
        downloader=_downloader(sources, []),
    )
    assert (target / "current").resolve() == third
    assert second.exists()
    assert not first.exists()


def test_invalid_existing_release_is_rebuilt(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    target = tmp_path / "volume"
    broken = target / "releases" / "2026-09-02"
    broken.mkdir(parents=True)
    (broken / "release.json").write_text("{}", encoding="utf-8")

    release = bootstrap_reference_data(
        target,
        snapshot_version="2026-09-02",
        source_urls=URLS,
        downloader=_downloader(sources, []),
    )

    assert (release / "locations.sqlite3").is_file()


def test_snapshot_version_cannot_escape_the_volume(tmp_path: Path) -> None:
    with pytest.raises(ReferenceDataBootstrapError, match="snapshot version"):
        bootstrap_reference_data(
            tmp_path,
            snapshot_version="../outside",
            source_urls=URLS,
            downloader=lambda *_: None,
        )


def test_cli_rejects_non_https_source(monkeypatch, capsys) -> None:
    monkeypatch.setenv("GEONAMES_SNAPSHOT_VERSION", "2026-09-02")
    with pytest.raises(SystemExit) as raised:
        main(["--cities500-url", "http://example.test/cities500.zip"])
    assert raised.value.code == 2
    assert "must use HTTPS" in capsys.readouterr().err


def test_corrupt_sqlite_release_is_rebuilt_instead_of_crashing(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    target = tmp_path / "volume"
    release = bootstrap_reference_data(
        target,
        snapshot_version="2026-09-02",
        source_urls=URLS,
        downloader=_downloader(sources, []),
    )
    (release / "locations.sqlite3").write_bytes(b"not-a-sqlite-database")

    rebuilt = bootstrap_reference_data(
        target,
        snapshot_version="2026-09-02",
        source_urls=URLS,
        downloader=_downloader(sources, []),
    )

    validate_location_index(rebuilt / "locations.sqlite3", rebuilt / "locations.manifest.json")
    assert (target / "current").resolve() == rebuilt
