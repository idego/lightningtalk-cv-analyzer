from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _root() -> Path:
    if configured := os.environ.get("CV_VALIDATOR_REPO_ROOT"):
        return Path(configured)
    return Path(__file__).resolve().parents[3]


def _run_preflight(env_file: Path, reference_mode: str) -> subprocess.CompletedProcess[str]:
    root = _root()
    return subprocess.run(
        [str(root / "scripts/runtime-preflight.sh"), "dev", str(env_file), reference_mode],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )


def test_automatic_preflight_accepts_versioned_offline_build(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CV_VALIDATOR_AI_ENABLED=false\nGEONAMES_SNAPSHOT_VERSION=2026-08-21\n",
        encoding="utf-8",
    )

    result = _run_preflight(env_file, "automatic")

    assert result.returncode == 0, result.stderr
    assert "configuration is valid" in result.stdout


def test_automatic_preflight_rejects_insecure_mirror(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CV_VALIDATOR_AI_ENABLED=false\n"
        "GEONAMES_SNAPSHOT_VERSION=2026-08-21\n"
        "GEONAMES_CITIES500_URL=http://example.test/cities500.zip\n",
        encoding="utf-8",
    )

    result = _run_preflight(env_file, "automatic")

    assert result.returncode == 1
    assert "must use HTTPS" in result.stderr


def test_operator_preflight_requires_an_existing_directory(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"CV_VALIDATOR_REFERENCE_DATA_DIR={tmp_path / 'missing'}\n",
        encoding="utf-8",
    )

    result = _run_preflight(env_file, "operator")

    assert result.returncode == 1
    assert "directory does not exist" in result.stderr


def test_automatic_disk_check_runs_inside_docker_filesystem() -> None:
    script = (_root() / "scripts/runtime-preflight.sh").read_text(encoding="utf-8")

    assert 'docker --context "${DOCKER_CONTEXT:-default}" run' in script
    assert "--network none python:3.12-slim" in script
    assert 'available_kb=$(df -Pk "$space_path"' in script
    assert "space_path=." not in script
