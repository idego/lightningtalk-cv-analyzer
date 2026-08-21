import os
import subprocess
import sys
from pathlib import Path


API_ROOT = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "geonames"


def test_cli_builds_and_validates_index(tmp_path: Path) -> None:
    index_path = tmp_path / "locations.sqlite3"
    manifest_path = tmp_path / "locations.manifest.json"
    environment = dict(os.environ, PYTHONPATH=str(API_ROOT / "src"))
    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "cv_validator.location.index_cli",
            "build",
            "--cities500",
            str(FIXTURES / "cities500.txt"),
            "--cities500-url",
            "https://example.test/cities500.zip",
            "--country-info",
            str(FIXTURES / "countryInfo.txt"),
            "--country-info-url",
            "https://example.test/countryInfo.txt",
            "--alternate-names",
            str(FIXTURES / "alternateNamesV2.txt"),
            "--alternate-names-url",
            "https://example.test/alternateNamesV2.zip",
            "--snapshot-date",
            "2026-08-21",
            "--output-index",
            str(index_path),
            "--output-manifest",
            str(manifest_path),
        ],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    validate = subprocess.run(
        [
            sys.executable,
            "-m",
            "cv_validator.location.index_cli",
            "validate",
            "--index",
            str(index_path),
            "--manifest",
            str(manifest_path),
            "--cities500",
            str(FIXTURES / "cities500.txt"),
            "--country-info",
            str(FIXTURES / "countryInfo.txt"),
            "--alternate-names",
            str(FIXTURES / "alternateNamesV2.txt"),
        ],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert build.returncode == 0, build.stderr
    assert "geonames-2026-08-21-" in build.stdout
    assert validate.returncode == 0, validate.stderr
    assert "valid" in validate.stdout.casefold()


def test_cli_returns_nonzero_for_invalid_index(tmp_path: Path) -> None:
    environment = dict(os.environ, PYTHONPATH=str(API_ROOT / "src"))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cv_validator.location.index_cli",
            "validate",
            "--index",
            str(tmp_path / "missing.sqlite3"),
            "--manifest",
            str(tmp_path / "missing.json"),
        ],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stderr.startswith("error:")


def test_build_cli_does_not_expose_overwrite() -> None:
    environment = dict(os.environ, PYTHONPATH=str(API_ROOT / "src"))
    result = subprocess.run(
        [sys.executable, "-m", "cv_validator.location.index_cli", "build", "--help"],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "--overwrite" not in result.stdout
