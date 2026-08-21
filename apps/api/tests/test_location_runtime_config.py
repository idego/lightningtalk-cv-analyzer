import json
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from docx import Document

from cv_validator.api.app import create_app
from cv_validator.config import LocationConfigurationError, load_location_resolver
from cv_validator.location import ResolutionLevel, SQLiteLocationResolver
from cv_validator.location.index import SourceSpec, build_location_index


FIXTURES = Path(__file__).parent / "fixtures" / "geonames"
INDEX_ENV = "CV_VALIDATOR_LOCATION_INDEX_PATH"
MANIFEST_ENV = "CV_VALIDATOR_LOCATION_MANIFEST_PATH"


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


def _docx_bytes(text: str) -> bytes:
    document = Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def test_no_location_paths_disables_the_runtime_resolver(monkeypatch) -> None:
    _clear_location_env(monkeypatch)

    assert load_location_resolver() is None


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


def test_app_reuses_one_resolver_and_closes_it_on_shutdown(monkeypatch, tmp_path) -> None:
    index_path, manifest_path = _build_pair(tmp_path)
    monkeypatch.setenv(INDEX_ENV, str(index_path))
    monkeypatch.setenv(MANIFEST_ENV, str(manifest_path))
    app = create_app(db_path=tmp_path / "audit.db")
    resolver = app.state.location_resolver

    with TestClient(app) as client:
        assert client.app.state.location_resolver is resolver
        assert client.get("/health").status_code == 200
        assert resolver.resolve("Berlin", level=ResolutionLevel.LOCALITY).matches

    with pytest.raises(RuntimeError, match="closed"):
        resolver.resolve("Berlin", level=ResolutionLevel.LOCALITY)


def test_api_and_audit_expose_version_but_not_host_paths(monkeypatch, tmp_path) -> None:
    index_path, manifest_path = _build_pair(tmp_path)
    monkeypatch.setenv(INDEX_ENV, str(index_path))
    monkeypatch.setenv(MANIFEST_ENV, str(manifest_path))
    app = create_app(db_path=tmp_path / "audit.db")

    with TestClient(app) as client:
        response = client.post(
            "/analyze",
            files={
                "file": (
                    "cv.docx",
                    _docx_bytes(
                        "Jane Example\nCurrent location: Berlin, Germany\n"
                        "Software engineer profile"
                    ),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        audit_json = client.app.state.store.get_audit_entries()[0]["output_json"]

    payload_text = response.text
    assert response.status_code == 200
    assert "geonames-sqlite" in payload_text
    assert "geonames-sqlite" in audit_json
    assert str(tmp_path) not in payload_text
    assert str(tmp_path) not in audit_json


def test_base_compose_and_image_do_not_require_or_copy_reference_data() -> None:
    root = Path(__file__).resolve().parents[3]
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (root / "apps/api/Dockerfile").read_text(encoding="utf-8")
    dockerignore = (root / "apps/api/.dockerignore").read_text(encoding="utf-8")
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")

    assert "CV_VALIDATOR_LOCATION_INDEX_PATH" not in compose
    assert "reference-data" not in dockerfile
    assert "data" in dockerignore.splitlines()
    assert "data/" in gitignore.splitlines()


def test_optional_compose_overlay_requires_read_only_operator_directory() -> None:
    root = Path(__file__).resolve().parents[3]
    overlay = (root / "docker-compose.reference-data.yml").read_text(
        encoding="utf-8"
    )

    assert "CV_VALIDATOR_REFERENCE_DATA_DIR:?" in overlay
    assert "CV_VALIDATOR_LOCATION_INDEX_PATH: /app/reference-data/locations.sqlite3" in overlay
    assert "CV_VALIDATOR_LOCATION_MANIFEST_PATH: /app/reference-data/locations.manifest.json" in overlay
    assert "read_only: true" in overlay
    assert "create_host_path: false" in overlay
