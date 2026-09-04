from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Mapping
from urllib.parse import quote

from jsonschema import Draft202012Validator, FormatChecker

from cv_validator.location.checksum import sha256_fd, sha256_file
from cv_validator.location.index import INDEX_APPLICATION_ID, INDEX_SCHEMA_VERSION


EXPECTED_SCHEMA_OBJECTS = frozenset(
    {
        ("index", "location_name_alternate_id", "location_name"),
        ("index", "location_name_record_id", "location_name"),
        ("table", "build_stat", "build_stat"),
        ("table", "index_metadata", "index_metadata"),
        ("table", "location_name", "location_name"),
        ("table", "location_record", "location_record"),
        ("table", "source_input", "source_input"),
    }
)

EXPECTED_TABLE_COLUMNS = {
    "index_metadata": (
        "singleton",
        "schema_version",
        "reference_data_version",
        "builder_version",
        "normalization_version",
        "filter_policy_version",
        "snapshot_date",
        "sqlite_version",
        "record_count",
        "name_count",
    ),
    "source_input": (
        "role",
        "filename",
        "source_url",
        "size_bytes",
        "sha256",
        "archive_member",
        "member_sha256",
    ),
    "build_stat": ("metric", "value"),
    "location_record": (
        "record_id",
        "geoname_id",
        "level",
        "canonical_name",
        "normalized_canonical_name",
        "country_code",
        "country_name",
        "region_code",
        "region_name",
        "source_kind",
        "feature_class",
        "feature_code",
        "population",
        "source_modified_date",
    ),
    "location_name": (
        "normalized_name",
        "record_id",
        "display_name",
        "match_kind",
        "alias_kind",
        "language_code",
        "alternate_name_id",
        "is_preferred",
        "is_short",
    ),
}


class LocationIndexValidationError(ValueError):
    pass


def validate_location_index(
    index_path: Path,
    manifest_path: Path,
    *,
    source_paths: Mapping[str, Path] | None = None,
    _connection: sqlite3.Connection | None = None,
    _artifact_fd: int | None = None,
) -> dict[str, object]:
    try:
        index_path = index_path.resolve()
        manifest = _load_manifest(manifest_path)
        artifact = manifest["artifact"]
        if artifact["filename"] != index_path.name:
            raise LocationIndexValidationError("artifact filename does not match index")
        artifact_stat = (
            os.fstat(_artifact_fd) if _artifact_fd is not None else index_path.stat()
        )
        if artifact_stat.st_size != artifact["size_bytes"]:
            raise LocationIndexValidationError("index size does not match manifest")
        artifact_hash = (
            sha256_fd(_artifact_fd)
            if _artifact_fd is not None
            else sha256_file(index_path)
        )
        if artifact_hash != artifact["sha256"]:
            raise LocationIndexValidationError("index SHA-256 does not match manifest")
        if index_path.with_name(f"{index_path.name}-wal").exists() or index_path.with_name(
            f"{index_path.name}-shm"
        ).exists():
            raise LocationIndexValidationError("index must not have WAL or SHM sidecars")

        if _connection is None:
            with open_read_only_connection(index_path) as connection:
                _validate_database(connection, manifest)
        else:
            _validate_database(_connection, manifest)

        if source_paths is not None:
            expected_sources = {source["role"]: source for source in manifest["sources"]}
            if set(source_paths) != set(expected_sources):
                raise LocationIndexValidationError("source path roles do not match manifest")
            for role, source_path in source_paths.items():
                if sha256_file(source_path) != expected_sources[role]["sha256"]:
                    raise LocationIndexValidationError(
                        f"source SHA-256 does not match manifest: {role}"
                    )
        return manifest
    except LocationIndexValidationError:
        raise
    except sqlite3.DatabaseError as exc:
        raise LocationIndexValidationError(f"invalid SQLite index: {exc}") from exc
    except (KeyError, OSError, TypeError, ValueError) as exc:
        raise LocationIndexValidationError(f"invalid location index: {exc}") from exc


def open_read_only_connection(index_path: Path) -> sqlite3.Connection:
    encoded_path = quote(index_path.resolve().as_posix(), safe="/")
    connection = sqlite3.connect(
        f"file:{encoded_path}?mode=ro&immutable=1",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA trusted_schema = OFF")
    return connection


def open_pinned_read_only_connection(artifact_fd: int) -> sqlite3.Connection:
    pinned_path = Path("/proc/self/fd") / str(artifact_fd)
    if not pinned_path.exists():
        raise LocationIndexValidationError(
            "pinned SQLite artifacts require /proc/self/fd"
        )
    encoded_path = quote(pinned_path.as_posix(), safe="/")
    connection = sqlite3.connect(
        f"file:{encoded_path}?mode=ro&immutable=1",
        uri=True,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA trusted_schema = OFF")
    return connection


def _load_manifest(path: Path) -> dict[str, object]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LocationIndexValidationError(f"invalid manifest JSON: {exc}") from exc
    schema_path = Path(__file__).with_name("manifest.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(manifest),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        raise LocationIndexValidationError(
            f"manifest schema violation at {location}: {error.message}"
        )
    return manifest


def _validate_database(
    connection: sqlite3.Connection,
    manifest: dict[str, object],
) -> None:
    artifact = manifest["artifact"]
    if connection.execute("PRAGMA application_id").fetchone()[0] != INDEX_APPLICATION_ID:
        raise LocationIndexValidationError("unexpected SQLite application_id")
    if connection.execute("PRAGMA user_version").fetchone()[0] != INDEX_SCHEMA_VERSION:
        raise LocationIndexValidationError("unexpected SQLite user_version")
    if artifact["sqlite_application_id"] != INDEX_APPLICATION_ID:
        raise LocationIndexValidationError("manifest application_id is unsupported")
    if artifact["sqlite_user_version"] != INDEX_SCHEMA_VERSION:
        raise LocationIndexValidationError("manifest user_version is unsupported")

    objects = {
        (row["type"], row["name"], row["tbl_name"])
        for row in connection.execute(
            """SELECT type, name, tbl_name FROM sqlite_schema
            WHERE name NOT LIKE 'sqlite_%'"""
        )
    }
    if objects != EXPECTED_SCHEMA_OBJECTS:
        raise LocationIndexValidationError("SQLite schema does not match allowlist")
    for table_name, expected_columns in EXPECTED_TABLE_COLUMNS.items():
        actual_columns = tuple(
            row["name"]
            for row in connection.execute(
                f"PRAGMA table_info({table_name})"
            )
        )
        if actual_columns != expected_columns:
            raise LocationIndexValidationError(
                f"SQLite table definition differs: {table_name}"
            )
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise LocationIndexValidationError("SQLite integrity_check failed")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise LocationIndexValidationError("SQLite foreign key check failed")

    metadata = connection.execute(
        "SELECT * FROM index_metadata WHERE singleton = 1"
    ).fetchone()
    if metadata is None:
        raise LocationIndexValidationError("index metadata is missing")
    expected_metadata = {
        "schema_version": artifact["sqlite_schema_version"],
        "reference_data_version": manifest["reference_data_version"],
        "builder_version": manifest["builder"]["version"],
        "normalization_version": manifest["builder"]["normalization_version"],
        "filter_policy_version": manifest["builder"]["filter_policy_version"],
        "snapshot_date": manifest["snapshot_date"],
        "sqlite_version": manifest["builder"]["sqlite_version"],
        "record_count": manifest["counts"]["records_total"],
        "name_count": manifest["counts"]["names_total"],
    }
    for key, expected in expected_metadata.items():
        if metadata[key] != expected:
            raise LocationIndexValidationError(f"index metadata mismatch: {key}")

    database_sources = {
        row["role"]: dict(row)
        for row in connection.execute("SELECT * FROM source_input")
    }
    manifest_sources = {source["role"]: source for source in manifest["sources"]}
    if database_sources != manifest_sources:
        raise LocationIndexValidationError("source metadata differs from manifest")
    database_stats = {
        row["metric"]: row["value"]
        for row in connection.execute("SELECT metric, value FROM build_stat")
    }
    if database_stats != manifest["counts"]:
        raise LocationIndexValidationError("build counts differ from manifest")
    if connection.execute("SELECT count(*) FROM location_record").fetchone()[0] != manifest[
        "counts"
    ]["records_total"]:
        raise LocationIndexValidationError("record count differs from manifest")
    if connection.execute("SELECT count(*) FROM location_name").fetchone()[0] != manifest[
        "counts"
    ]["names_total"]:
        raise LocationIndexValidationError("name count differs from manifest")
