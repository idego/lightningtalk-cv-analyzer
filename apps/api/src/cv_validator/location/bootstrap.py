from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import sqlite3
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator

from cv_validator.location.index import SourceSpec, build_location_index
from cv_validator.location.postal import SQLitePostalCodeResolver, build_postal_index
from cv_validator.location.validation import validate_location_index


DEFAULT_SOURCE_URLS = {
    "cities500": "https://download.geonames.org/export/dump/cities500.zip",
    "country_info": "https://download.geonames.org/export/dump/countryInfo.txt",
    "alternate_names": "https://download.geonames.org/export/dump/alternateNamesV2.zip",
    "postal_codes": "https://download.geonames.org/export/zip/allCountries.zip",
}
_SOURCE_FILES = {
    "cities500": ("cities500.zip", "cities500.txt"),
    "country_info": ("countryInfo.txt", None),
    "alternate_names": ("alternateNamesV2.zip", "alternateNamesV2.txt"),
    "postal_codes": ("allCountries.zip", "allCountries.txt"),
}
_RELEASE_FILES = (
    "locations.sqlite3",
    "locations.manifest.json",
    "postal-codes.sqlite3",
    "postal-codes.manifest.json",
    "release.json",
)
_VERSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")

Downloader = Callable[[str, Path], None]


class ReferenceDataBootstrapError(RuntimeError):
    pass


def bootstrap_reference_data(
    target: Path,
    *,
    snapshot_version: str,
    source_urls: Mapping[str, str] = DEFAULT_SOURCE_URLS,
    downloader: Downloader | None = None,
) -> Path:
    """Build and atomically publish one complete GeoNames release."""
    if not _VERSION_PATTERN.fullmatch(snapshot_version):
        raise ReferenceDataBootstrapError("invalid GeoNames snapshot version")
    if set(source_urls) != set(DEFAULT_SOURCE_URLS):
        raise ReferenceDataBootstrapError("all GeoNames source URLs are required")

    target = target.resolve()
    target.mkdir(parents=True, exist_ok=True)
    releases = target / "releases"
    releases.mkdir(exist_ok=True)
    download = downloader or _download

    with _exclusive_lock(target / ".bootstrap.lock"):
        _remove_stale_staging(target)
        release = releases / snapshot_version
        if _valid_release(release, snapshot_version, source_urls):
            _promote(target, release)
            return release
        previous = _current_release(target)
        if release.exists():
            shutil.rmtree(release)
        staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=target))
        try:
            inputs = staging / "inputs"
            output = staging / "release"
            inputs.mkdir()
            output.mkdir()
            source_paths = _fetch_sources(inputs, source_urls, download)
            build_location_index(
                cities500=SourceSpec(source_paths["cities500"], source_urls["cities500"]),
                country_info=SourceSpec(
                    source_paths["country_info"], source_urls["country_info"]
                ),
                alternate_names=SourceSpec(
                    source_paths["alternate_names"], source_urls["alternate_names"]
                ),
                snapshot_date=snapshot_version,
                output_index=output / "locations.sqlite3",
                output_manifest=output / "locations.manifest.json",
            )
            build_postal_index(
                source_path=source_paths["postal_codes"],
                source_url=source_urls["postal_codes"],
                snapshot_date=snapshot_version,
                output_index=output / "postal-codes.sqlite3",
                output_manifest=output / "postal-codes.manifest.json",
            )
            (output / "release.json").write_text(
                json.dumps(
                    {"snapshot_version": snapshot_version, "source_urls": dict(source_urls)},
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            if not _valid_release(output, snapshot_version, source_urls):
                raise ReferenceDataBootstrapError("built GeoNames release is invalid")
            os.replace(output, release)
            _promote(target, release)
            _prune_releases(releases, keep={path for path in (release, previous) if path})
            return release
        except Exception as exc:
            if isinstance(exc, ReferenceDataBootstrapError):
                raise
            raise ReferenceDataBootstrapError(f"GeoNames bootstrap failed: {exc}") from exc
        finally:
            shutil.rmtree(staging, ignore_errors=True)


def _fetch_sources(
    destination: Path,
    source_urls: Mapping[str, str],
    downloader: Downloader,
) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for role, (download_name, archive_member) in _SOURCE_FILES.items():
        downloaded = destination / download_name
        downloader(source_urls[role], downloaded)
        if archive_member is None:
            paths[role] = downloaded
            continue
        extracted = destination / archive_member
        try:
            with zipfile.ZipFile(downloaded) as archive:
                members = [item for item in archive.infolist() if item.filename == archive_member]
                if len(members) != 1 or members[0].is_dir():
                    raise ReferenceDataBootstrapError(
                        f"GeoNames archive does not contain exactly one {archive_member}"
                    )
                with archive.open(members[0]) as source, extracted.open("xb") as output:
                    shutil.copyfileobj(source, output)
        except zipfile.BadZipFile as exc:
            raise ReferenceDataBootstrapError(
                f"invalid GeoNames archive for {role}"
            ) from exc
        downloaded.unlink()
        paths[role] = extracted
    return paths


def _download(url: str, destination: Path) -> None:
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open("xb") as output:
            shutil.copyfileobj(response, output)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _valid_release(
    release: Path,
    snapshot_version: str,
    source_urls: Mapping[str, str],
) -> bool:
    try:
        if not release.is_dir() or any(not (release / name).is_file() for name in _RELEASE_FILES):
            return False
        metadata = json.loads((release / "release.json").read_text(encoding="utf-8"))
        if metadata != {
            "snapshot_version": snapshot_version,
            "source_urls": dict(source_urls),
        }:
            return False
        validate_location_index(
            release / "locations.sqlite3", release / "locations.manifest.json"
        )
        postal = SQLitePostalCodeResolver(
            release / "postal-codes.sqlite3", release / "postal-codes.manifest.json"
        )
        postal.close()
        return True
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.DatabaseError):
        return False


def _promote(target: Path, release: Path) -> None:
    link = target / ".current.tmp"
    link.unlink(missing_ok=True)
    link.symlink_to(Path("releases") / release.name)
    os.replace(link, target / "current")


def _current_release(target: Path) -> Path | None:
    current = target / "current"
    try:
        return current.resolve(strict=True)
    except OSError:
        return None


def _prune_releases(releases: Path, *, keep: set[Path]) -> None:
    for obsolete in releases.iterdir():
        if obsolete.is_dir() and obsolete not in keep:
            shutil.rmtree(obsolete)


def _remove_stale_staging(target: Path) -> None:
    for path in target.glob(".staging-*"):
        if path.is_dir():
            shutil.rmtree(path)


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    with path.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ReferenceDataBootstrapError(
                "another GeoNames bootstrap is already running"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
