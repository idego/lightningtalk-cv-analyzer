from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
import zipfile
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator, TextIO

from cv_validator.location.resolver import normalize_location


INDEX_SCHEMA_VERSION = 1
INDEX_APPLICATION_ID = 0x43564C49
BUILDER_VERSION = "1"
NORMALIZATION_VERSION = "nfkc-casefold-whitespace-v1"
FILTER_POLICY_VERSION = "geonames-v1"
TECHNICAL_NAMESPACES = frozenset(
    {"abbr", "faac", "iata", "icao", "link", "post", "wkdt"}
)
LANGUAGE_CODE_PATTERN = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


class LocationIndexBuildError(ValueError):
    pass


@dataclass(frozen=True)
class SourceSpec:
    path: Path
    url: str


@dataclass(frozen=True)
class PreparedSource:
    role: str
    spec: SourceSpec
    archive_member: str | None
    metadata: dict[str, object]


def build_location_index(
    *,
    cities500: SourceSpec,
    country_info: SourceSpec,
    alternate_names: SourceSpec,
    snapshot_date: str,
    output_index: Path,
    output_manifest: Path,
) -> dict[str, object]:
    try:
        parsed_snapshot_date = date.fromisoformat(snapshot_date)
    except ValueError as exc:
        raise LocationIndexBuildError(
            "snapshot_date must use YYYY-MM-DD"
        ) from exc
    if parsed_snapshot_date.isoformat() != snapshot_date:
        raise LocationIndexBuildError("snapshot_date must use YYYY-MM-DD")
    if _paths_alias(output_index, output_manifest):
        raise LocationIndexBuildError("output index and manifest must be distinct")
    if output_index.exists() or output_manifest.exists():
        raise LocationIndexBuildError("output already exists")

    sources = {
        "cities500": cities500,
        "country_info": country_info,
        "alternate_names_v2": alternate_names,
    }
    expected_members = {
        "cities500": "cities500.txt",
        "country_info": None,
        "alternate_names_v2": "alternateNamesV2.txt",
    }
    prepared_sources: dict[str, PreparedSource] = {}
    source_metadata: dict[str, dict[str, object]] = {}
    for role, source in sources.items():
        prepared = _prepare_source(
            role,
            source,
            expected_member=expected_members[role],
        )
        prepared_sources[role] = prepared
        source_metadata[role] = prepared.metadata
    digest_input = "\n".join(
        f"{role}:{source_metadata[role]['sha256']}" for role in sorted(sources)
    ).encode()
    source_digest = hashlib.sha256(digest_input).hexdigest()[:12]
    reference_data_version = f"geonames-{snapshot_date}-{source_digest}"

    output_index.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output_index.name}.",
        suffix=".tmp",
        dir=output_index.parent,
    )
    os.close(fd)
    temporary_index = Path(temporary_name)
    manifest_fd, manifest_name = tempfile.mkstemp(
        prefix=f".{output_manifest.name}.",
        suffix=".tmp",
        dir=output_manifest.parent,
    )
    os.close(manifest_fd)
    temporary_manifest = Path(manifest_name)
    try:
        build_stats = _write_streaming_database(
            temporary_index,
            prepared_sources=prepared_sources,
            sources=source_metadata,
            snapshot_date=snapshot_date,
            reference_data_version=reference_data_version,
        )
        artifact_sha256 = _sha256(temporary_index)
        manifest: dict[str, object] = {
            "manifest_schema_version": 1,
            "reference_data_version": reference_data_version,
            "snapshot_date": snapshot_date,
            "artifact": {
                "filename": output_index.name,
                "size_bytes": temporary_index.stat().st_size,
                "sha256": artifact_sha256,
                "sqlite_schema_version": INDEX_SCHEMA_VERSION,
                "sqlite_application_id": INDEX_APPLICATION_ID,
                "sqlite_user_version": INDEX_SCHEMA_VERSION,
            },
            "builder": {
                "name": "cv-validator-geonames-index",
                "version": BUILDER_VERSION,
                "python_version": sys.version.split()[0],
                "sqlite_version": sqlite3.sqlite_version,
                "normalization_version": NORMALIZATION_VERSION,
                "filter_policy_version": FILTER_POLICY_VERSION,
            },
            "sources": [source_metadata[role] for role in sorted(sources)],
            "filters": {
                "locality_source": "cities500",
                "normalization": "NFKC, casefold, collapse whitespace, trim",
                "included_aliases": ["alternate", "preferred", "short"],
                "excluded_aliases": [
                    "historic",
                    "colloquial",
                    "temporal",
                    "abbr",
                    "faac",
                    "iata",
                    "icao",
                    "link",
                    "post",
                    "wkdt",
                    "unsupported_namespace",
                ],
                "country_code_aliases": ["ISO2", "ISO3"],
                "ignored_geoname_fields": ["asciiname", "alternatenames"],
            },
            "counts": build_stats,
            "license": {
                "dataset": "GeoNames",
                "license_name": "CC BY 4.0",
                "license_url": "https://creativecommons.org/licenses/by/4.0/",
                "source_url": "https://www.geonames.org/",
                "attribution": "Contains data from GeoNames, licensed under CC BY 4.0.",
                "modifications": "Filtered, normalized for exact lookup, and transformed into SQLite.",
                "warranty_notice": "GeoNames data is provided without warranty of accuracy, timeliness, or completeness.",
            },
        }
        temporary_manifest.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        published_index = False
        published_manifest = False
        try:
            _fsync_file(temporary_index)
            _fsync_file(temporary_manifest)
            os.link(temporary_index, output_index)
            published_index = True
            temporary_index.unlink()
            os.link(temporary_manifest, output_manifest)
            published_manifest = True
            temporary_manifest.unlink()
            _fsync_directory(output_index.parent)
            if output_manifest.parent != output_index.parent:
                _fsync_directory(output_manifest.parent)
        except BaseException:
            if published_index:
                output_index.unlink(missing_ok=True)
            if published_manifest:
                output_manifest.unlink(missing_ok=True)
            raise
        return manifest
    finally:
        temporary_index.unlink(missing_ok=True)
        temporary_manifest.unlink(missing_ok=True)
        for suffix in ("-wal", "-shm", "-journal"):
            temporary_index.with_name(f"{temporary_index.name}{suffix}").unlink(
                missing_ok=True
            )


def _prepare_source(
    role: str,
    source: SourceSpec,
    *,
    expected_member: str | None,
) -> PreparedSource:
    if not source.url.strip():
        raise LocationIndexBuildError(f"source URL must not be empty: {role}")
    try:
        size_bytes = source.path.stat().st_size
        source_sha256 = _sha256(source.path)
    except OSError as exc:
        raise LocationIndexBuildError(f"cannot read source {role}: {exc}") from exc
    archive_member = None
    member_sha256 = None
    if source.path.suffix.casefold() == ".zip":
        if expected_member is None:
            raise LocationIndexBuildError(f"ZIP input is not supported for {role}")
        try:
            with zipfile.ZipFile(source.path) as archive:
                members = [name for name in archive.namelist() if not name.endswith("/")]
                approved_members = {expected_member}
                if role == "alternate_names_v2":
                    approved_members.add("iso-languagecodes.txt")
                if len(members) != len(set(members)) or set(members) != approved_members:
                    raise LocationIndexBuildError(
                        f"{role} ZIP must contain exactly the approved members"
                    )
                for member in sorted(members):
                    with archive.open(member) as stream:
                        digest = _sha256_stream(stream)
                    if member == expected_member:
                        member_sha256 = digest
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            raise LocationIndexBuildError(f"invalid ZIP source {role}: {exc}") from exc
        archive_member = expected_member
    return PreparedSource(
        role=role,
        spec=source,
        archive_member=archive_member,
        metadata={
            "role": role,
            "filename": source.path.name,
            "source_url": source.url,
            "size_bytes": size_bytes,
            "sha256": source_sha256,
            "archive_member": archive_member,
            "member_sha256": member_sha256,
        },
    )


@contextmanager
def _open_source_text(source: PreparedSource) -> Iterator[TextIO]:
    try:
        if source.archive_member is None:
            with source.spec.path.open("r", encoding="utf-8", newline="") as stream:
                yield stream
            return
        with zipfile.ZipFile(source.spec.path) as archive:
            with archive.open(source.archive_member) as raw_stream:
                with io.TextIOWrapper(raw_stream, encoding="utf-8", newline="") as stream:
                    yield stream
    except UnicodeDecodeError as exc:
        raise LocationIndexBuildError(
            f"source is not UTF-8: {source.role}"
        ) from exc
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise LocationIndexBuildError(
            f"cannot stream source {source.role}: {exc}"
        ) from exc


def _write_streaming_database(
    path: Path,
    *,
    prepared_sources: dict[str, PreparedSource],
    sources: dict[str, dict[str, object]],
    snapshot_date: str,
    reference_data_version: str,
) -> dict[str, int]:
    connection = sqlite3.connect(path)
    stats: Counter[str] = Counter()
    try:
        connection.execute("PRAGMA page_size = 4096")
        journal_mode = connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0]
        if str(journal_mode).casefold() != "delete":
            raise LocationIndexBuildError("SQLite DELETE journal mode is unavailable")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA temp_store = FILE")
        connection.execute(f"PRAGMA application_id = {INDEX_APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version = {INDEX_SCHEMA_VERSION}")
        connection.executescript(_STREAMING_SCHEMA_SQL)

        with _open_source_text(prepared_sources["country_info"]) as stream:
            countries = _read_countries(stream)
        stats["country_rows_total"] = len(countries)
        retained_ids = {int(country["geoname_id"]) for country in countries.values()}
        for country in countries.values():
            record = {
                "record_id": f"geonames:{country['geoname_id']}",
                "geoname_id": country["geoname_id"],
                "level": "country",
                "canonical_name": country["country_name"],
                "normalized_canonical_name": normalize_location(
                    str(country["country_name"])
                ),
                "country_code": country["country_code"],
                "country_name": country["country_name"],
                "region_code": None,
                "region_name": None,
                "source_kind": "country_info",
                "feature_class": None,
                "feature_code": None,
                "population": None,
                "source_modified_date": None,
            }
            _insert_record_and_canonical_name(connection, record)
            for alias_kind, display_name in (
                ("country_iso2", country["country_code"]),
                ("country_iso3", country["iso3"]),
            ):
                _insert_staged_name(
                    connection,
                    normalized_name=normalize_location(str(display_name)),
                    record_id=str(record["record_id"]),
                    display_name=str(display_name),
                    match_kind="alias",
                    alias_kind=alias_kind,
                    language_code=None,
                    alternate_name_id=None,
                    is_preferred=0,
                    is_short=0,
                    precedence=4,
                )

        with _open_source_text(prepared_sources["cities500"]) as stream:
            for line_number, raw_line in enumerate(stream, start=1):
                line = raw_line.rstrip("\r\n")
                if not line:
                    continue
                record = _parse_locality_line(line, line_number, countries)
                geoname_id = int(record["geoname_id"])
                if geoname_id in retained_ids:
                    existing = connection.execute(
                        "SELECT level FROM location_record WHERE geoname_id = ?",
                        (geoname_id,),
                    ).fetchone()
                    if existing is not None and existing[0] == "country":
                        raise LocationIndexBuildError(
                            "geoname id is shared by a country and locality: "
                            f"{geoname_id}"
                        )
                    raise LocationIndexBuildError(
                        f"duplicate geoname id: {geoname_id}"
                    )
                try:
                    _insert_record_and_canonical_name(connection, record)
                except sqlite3.IntegrityError as exc:
                    raise LocationIndexBuildError(
                        f"duplicate geoname id: {geoname_id}"
                    ) from exc
                retained_ids.add(geoname_id)
                stats["city_rows_total"] += 1

        with _open_source_text(prepared_sources["alternate_names_v2"]) as stream:
            for line_number, raw_line in enumerate(stream, start=1):
                line = raw_line.rstrip("\r\n")
                if not line:
                    continue
                _stage_alternate_line(
                    connection,
                    line,
                    line_number=line_number,
                    retained_ids=retained_ids,
                    stats=stats,
                )

        staged_count = connection.execute(
            "SELECT count(*) FROM name_stage"
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO location_name
            SELECT normalized_name, record_id, display_name, match_kind,
                   alias_kind, language_code, alternate_name_id,
                   is_preferred, is_short
            FROM (
                SELECT *, row_number() OVER (
                    PARTITION BY normalized_name, record_id
                    ORDER BY precedence,
                             coalesce(alternate_name_id, -1),
                             display_name
                ) AS chosen
                FROM name_stage
            )
            WHERE chosen = 1
            ORDER BY normalized_name, record_id"""
        )
        names_total = connection.execute(
            "SELECT count(*) FROM location_name"
        ).fetchone()[0]
        stats["records_country"] = len(countries)
        stats["records_locality"] = stats["city_rows_total"]
        stats["records_total"] = stats["records_country"] + stats["records_locality"]
        stats["names_total"] = names_total
        stats["names_canonical"] = connection.execute(
            "SELECT count(*) FROM location_name WHERE match_kind = 'canonical'"
        ).fetchone()[0]
        stats["names_alias"] = names_total - stats["names_canonical"]
        stats["names_duplicate_normalized_record"] = staged_count - names_total
        ambiguity_rows = connection.execute(
            """SELECT count(*) AS records, count(DISTINCT r.country_code) AS countries
            FROM location_name AS n
            JOIN location_record AS r ON r.record_id = n.record_id
            GROUP BY r.level, n.normalized_name"""
        ).fetchall()
        stats["normalized_keys_distinct"] = len(ambiguity_rows)
        stats["normalized_keys_ambiguous"] = sum(
            row[0] > 1 for row in ambiguity_rows
        )
        stats["normalized_keys_ambiguous_same_country"] = sum(
            row[0] > 1 and row[1] == 1 for row in ambiguity_rows
        )
        stats["normalized_keys_ambiguous_cross_country"] = sum(
            row[0] > 1 and row[1] > 1 for row in ambiguity_rows
        )
        for metric in _ALTERNATE_METRICS:
            stats[metric] += 0
        build_stats = dict(stats)

        connection.execute(
            "INSERT INTO index_metadata VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                INDEX_SCHEMA_VERSION,
                reference_data_version,
                BUILDER_VERSION,
                NORMALIZATION_VERSION,
                FILTER_POLICY_VERSION,
                snapshot_date,
                sqlite3.sqlite_version,
                build_stats["records_total"],
                build_stats["names_total"],
            ),
        )
        connection.executemany(
            "INSERT INTO source_input VALUES (:role, :filename, :source_url, :size_bytes, :sha256, :archive_member, :member_sha256)",
            [sources[role] for role in sorted(sources)],
        )
        connection.executemany(
            "INSERT INTO build_stat VALUES (?, ?)",
            sorted(build_stats.items()),
        )
        connection.executescript(
            "DROP TABLE name_stage; DROP TABLE alternate_seen;"
        )
        connection.commit()
        connection.execute("VACUUM")
        return build_stats
    finally:
        connection.close()


def _parse_locality_line(
    line: str,
    line_number: int,
    countries: dict[str, dict[str, object]],
) -> dict[str, object]:
    fields = line.split("\t")
    if len(fields) != 19:
        raise LocationIndexBuildError(
            f"cities500 line {line_number} must have 19 fields"
        )
    try:
        geoname_id = int(fields[0])
    except ValueError as exc:
        raise LocationIndexBuildError(
            f"cities500 line {line_number} has invalid geonameid"
        ) from exc
    if geoname_id <= 0:
        raise LocationIndexBuildError(
            f"cities500 line {line_number} has invalid geonameid"
        )
    if not fields[1] or not normalize_location(fields[1]):
        raise LocationIndexBuildError(f"cities500 line {line_number} has an empty name")
    if fields[6] != "P":
        raise LocationIndexBuildError(
            f"cities500 record must have feature class P: {geoname_id}"
        )
    country_code = fields[8]
    if country_code not in countries:
        raise LocationIndexBuildError(f"unknown country code: {country_code}")
    try:
        population = int(fields[14]) if fields[14] else None
    except ValueError as exc:
        raise LocationIndexBuildError(
            f"cities500 line {line_number} has invalid population"
        ) from exc
    country = countries[country_code]
    return {
        "record_id": f"geonames:{geoname_id}",
        "geoname_id": geoname_id,
        "level": "locality",
        "canonical_name": fields[1],
        "normalized_canonical_name": normalize_location(fields[1]),
        "country_code": country_code,
        "country_name": country["country_name"],
        "region_code": None if fields[10] in ("", "00") else fields[10],
        "region_name": None,
        "source_kind": "cities500",
        "feature_class": fields[6],
        "feature_code": fields[7],
        "population": population,
        "source_modified_date": fields[18] or None,
    }


def _insert_record_and_canonical_name(
    connection: sqlite3.Connection,
    record: dict[str, object],
) -> None:
    connection.execute(
        """INSERT INTO location_record VALUES (
            :record_id, :geoname_id, :level, :canonical_name,
            :normalized_canonical_name, :country_code, :country_name,
            :region_code, :region_name, :source_kind, :feature_class,
            :feature_code, :population, :source_modified_date
        )""",
        record,
    )
    _insert_staged_name(
        connection,
        normalized_name=str(record["normalized_canonical_name"]),
        record_id=str(record["record_id"]),
        display_name=str(record["canonical_name"]),
        match_kind="canonical",
        alias_kind="canonical",
        language_code=None,
        alternate_name_id=None,
        is_preferred=0,
        is_short=0,
        precedence=0,
    )


def _stage_alternate_line(
    connection: sqlite3.Connection,
    line: str,
    *,
    line_number: int,
    retained_ids: set[int],
    stats: Counter[str],
) -> None:
    stats["alternate_rows_total"] += 1
    fields = line.split("\t")
    if len(fields) != 10:
        raise LocationIndexBuildError(
            f"alternateNamesV2 line {line_number} must have 10 fields"
        )
    try:
        alternate_id, geoname_id = int(fields[0]), int(fields[1])
    except ValueError as exc:
        raise LocationIndexBuildError(
            "alternateNamesV2 has an invalid alternateNameId or geonameid"
        ) from exc
    if alternate_id <= 0 or geoname_id <= 0:
        raise LocationIndexBuildError(
            "alternateNamesV2 has an invalid alternateNameId or geonameid"
        )
    try:
        connection.execute("INSERT INTO alternate_seen VALUES (?)", (alternate_id,))
    except sqlite3.IntegrityError as exc:
        raise LocationIndexBuildError(
            f"duplicate alternate-name id: {alternate_id}"
        ) from exc
    if geoname_id not in retained_ids:
        stats["alternate_filtered_unknown_record"] += 1
        return
    for field_index in (4, 5, 6, 7):
        if fields[field_index] not in ("", "0", "1"):
            raise LocationIndexBuildError("alternate-name flags must be 0, 1, or empty")
    language_code = fields[2]
    namespace = language_code.casefold()
    if fields[7] == "1":
        stats["alternate_filtered_historic"] += 1
        return
    if fields[6] == "1":
        stats["alternate_filtered_colloquial"] += 1
        return
    if fields[8] or fields[9]:
        stats["alternate_filtered_temporal"] += 1
        return
    if namespace in TECHNICAL_NAMESPACES:
        stats[f"alternate_filtered_namespace_{namespace}"] += 1
        return
    if language_code and not LANGUAGE_CODE_PATTERN.fullmatch(language_code):
        stats["alternate_filtered_unsupported_namespace"] += 1
        return
    display_name = fields[3]
    normalized_name = normalize_location(display_name)
    if not normalized_name:
        stats["alternate_filtered_empty_name"] += 1
        return
    _insert_staged_name(
        connection,
        normalized_name=normalized_name,
        record_id=f"geonames:{geoname_id}",
        display_name=display_name,
        match_kind="alias",
        alias_kind=(
            "preferred" if fields[4] == "1" else "short" if fields[5] == "1" else "alternate"
        ),
        language_code=language_code or None,
        alternate_name_id=alternate_id,
        is_preferred=int(fields[4] or 0),
        is_short=int(fields[5] or 0),
        precedence=1 if fields[4] == "1" else 2 if fields[5] == "1" else 3,
    )
    stats["alternate_retained"] += 1


def _insert_staged_name(
    connection: sqlite3.Connection,
    **values: object,
) -> None:
    connection.execute(
        """INSERT INTO name_stage VALUES (
            :normalized_name, :record_id, :display_name, :match_kind,
            :alias_kind, :language_code, :alternate_name_id,
            :is_preferred, :is_short, :precedence
        )""",
        values,
    )


def _sha256_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            return digest.hexdigest()
        digest.update(chunk)


_ALTERNATE_METRICS = (
    "alternate_rows_total",
    "alternate_retained",
    "alternate_filtered_unknown_record",
    "alternate_filtered_historic",
    "alternate_filtered_colloquial",
    "alternate_filtered_temporal",
    "alternate_filtered_empty_name",
    "alternate_filtered_unsupported_namespace",
    *(f"alternate_filtered_namespace_{name}" for name in sorted(TECHNICAL_NAMESPACES)),
)


_STREAMING_SCHEMA_SQL = """
CREATE TABLE index_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL,
    reference_data_version TEXT NOT NULL,
    builder_version TEXT NOT NULL,
    normalization_version TEXT NOT NULL,
    filter_policy_version TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    sqlite_version TEXT NOT NULL,
    record_count INTEGER NOT NULL,
    name_count INTEGER NOT NULL
);
CREATE TABLE source_input (
    role TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    source_url TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    archive_member TEXT,
    member_sha256 TEXT
) WITHOUT ROWID;
CREATE TABLE build_stat (
    metric TEXT PRIMARY KEY,
    value INTEGER NOT NULL CHECK (value >= 0)
) WITHOUT ROWID;
CREATE TABLE location_record (
    record_id TEXT PRIMARY KEY,
    geoname_id INTEGER NOT NULL UNIQUE,
    level TEXT NOT NULL CHECK (level IN ('country', 'locality')),
    canonical_name TEXT NOT NULL,
    normalized_canonical_name TEXT NOT NULL,
    country_code TEXT NOT NULL,
    country_name TEXT NOT NULL,
    region_code TEXT,
    region_name TEXT,
    source_kind TEXT NOT NULL,
    feature_class TEXT,
    feature_code TEXT,
    population INTEGER,
    source_modified_date TEXT
) WITHOUT ROWID;
CREATE TABLE location_name (
    normalized_name TEXT NOT NULL COLLATE BINARY,
    record_id TEXT NOT NULL REFERENCES location_record(record_id),
    display_name TEXT NOT NULL,
    match_kind TEXT NOT NULL CHECK (match_kind IN ('canonical', 'alias')),
    alias_kind TEXT NOT NULL,
    language_code TEXT,
    alternate_name_id INTEGER,
    is_preferred INTEGER NOT NULL CHECK (is_preferred IN (0, 1)),
    is_short INTEGER NOT NULL CHECK (is_short IN (0, 1)),
    PRIMARY KEY (normalized_name, record_id)
) WITHOUT ROWID;
CREATE INDEX location_name_record_id ON location_name(record_id);
CREATE UNIQUE INDEX location_name_alternate_id
    ON location_name(alternate_name_id)
    WHERE alternate_name_id IS NOT NULL;
CREATE TABLE alternate_seen (
    alternate_name_id INTEGER PRIMARY KEY
) WITHOUT ROWID;
CREATE TABLE name_stage (
    normalized_name TEXT NOT NULL COLLATE BINARY,
    record_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    match_kind TEXT NOT NULL,
    alias_kind TEXT NOT NULL,
    language_code TEXT,
    alternate_name_id INTEGER,
    is_preferred INTEGER NOT NULL,
    is_short INTEGER NOT NULL,
    precedence INTEGER NOT NULL
);
"""


def _read_countries(content: Iterable[str]) -> dict[str, dict[str, object]]:
    lines = [line.rstrip("\r\n") for line in content if line.rstrip("\r\n")]
    if not lines:
        raise LocationIndexBuildError("countryInfo is empty")
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "#ISO" in line.split("\t")
        ),
        None,
    )
    if header_index is None:
        raise LocationIndexBuildError("countryInfo header is missing")
    header = [field.removeprefix("#") for field in lines[header_index].split("\t")]
    required_columns = ("ISO", "ISO3", "Country", "geonameid")
    missing_columns = [column for column in required_columns if column not in header]
    if missing_columns:
        raise LocationIndexBuildError(
            "countryInfo header is missing required columns: "
            + ", ".join(missing_columns)
        )
    column = {name: header.index(name) for name in required_columns}
    countries: dict[str, dict[str, object]] = {}
    seen_geoname_ids: set[int] = set()
    for line_number, line in enumerate(lines[header_index + 1 :], start=header_index + 2):
        if line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != len(header):
            raise LocationIndexBuildError(
                f"countryInfo line {line_number} must have {len(header)} fields"
            )
        country_code, iso3, country_name, geoname_id = (
            fields[column["ISO"]],
            fields[column["ISO3"]],
            fields[column["Country"]],
            fields[column["geonameid"]],
        )
        if not country_code or not iso3 or not country_name or not geoname_id:
            raise LocationIndexBuildError(
                f"countryInfo line {line_number} has an empty required field"
            )
        if country_code in countries:
            raise LocationIndexBuildError(f"duplicate country code: {country_code}")
        try:
            parsed_geoname_id = int(geoname_id)
        except ValueError as exc:
            raise LocationIndexBuildError(
                f"countryInfo line {line_number} has invalid geonameid"
            ) from exc
        if parsed_geoname_id <= 0:
            raise LocationIndexBuildError(
                f"countryInfo line {line_number} has invalid geonameid"
            )
        if parsed_geoname_id in seen_geoname_ids:
            raise LocationIndexBuildError(
                f"duplicate country geoname id: {parsed_geoname_id}"
            )
        seen_geoname_ids.add(parsed_geoname_id)
        countries[country_code] = {
            "country_code": country_code,
            "iso3": iso3,
            "country_name": country_name,
            "geoname_id": parsed_geoname_id,
        }
    return countries


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _paths_alias(first: Path, second: Path) -> bool:
    if first.resolve() == second.resolve():
        return True
    try:
        return first.samefile(second)
    except FileNotFoundError:
        return False
