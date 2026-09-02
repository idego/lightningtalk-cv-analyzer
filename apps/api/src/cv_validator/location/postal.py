from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Literal, Protocol

from cv_validator.domain import ComponentVersion
from cv_validator.location.resolver import normalize_location


PostalValidationStatus = Literal["resolved", "mismatch", "unresolved"]


@dataclass(frozen=True)
class PostalCodeRecord:
    country_code: str
    postal_code: str
    place_name: str


@dataclass(frozen=True)
class PostalValidation:
    status: PostalValidationStatus
    postal_code: str
    city: str
    country_code: str
    matched_places: tuple[str, ...]
    reference_data_version: ComponentVersion


class PostalCodeResolver(Protocol):
    @property
    def reference_data_version(self) -> ComponentVersion: ...

    def validate(
        self,
        postal_code: str,
        *,
        city: str,
        country_code: str,
    ) -> PostalValidation: ...


def normalize_postal_code(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


class InMemoryPostalCodeResolver:
    def __init__(
        self,
        records: Iterable[PostalCodeRecord],
        *,
        reference_data_version: ComponentVersion,
    ) -> None:
        self._records = tuple(records)
        self._reference_data_version = reference_data_version

    @property
    def reference_data_version(self) -> ComponentVersion:
        return self._reference_data_version

    def validate(
        self,
        postal_code: str,
        *,
        city: str,
        country_code: str,
    ) -> PostalValidation:
        matches = tuple(
            record.place_name
            for record in self._records
            if record.country_code.upper() == country_code.upper()
            and normalize_postal_code(record.postal_code)
            == normalize_postal_code(postal_code)
        )
        return _postal_validation(
            postal_code,
            city=city,
            country_code=country_code,
            matched_places=matches,
            reference_data_version=self.reference_data_version,
        )


class SQLitePostalCodeResolver:
    def __init__(self, index_path: Path, manifest_path: Path) -> None:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifact = manifest["artifact"]
            reference_data_version = manifest["reference_data_version"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid postal reference-data manifest") from exc
        if not isinstance(artifact, dict) or (
            manifest.get("manifest_schema_version") != 1
            or artifact.get("filename") != index_path.name
            or artifact.get("sha256") != _sha256(index_path)
            or not isinstance(reference_data_version, str)
            or not reference_data_version.strip()
        ):
            raise ValueError("invalid postal reference-data pair")
        self._reference_data_version = ComponentVersion(
            "geonames-postal-sqlite",
            reference_data_version,
        )
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            f"file:{index_path.resolve()}?mode=ro",
            uri=True,
            check_same_thread=False,
        )
        integrity = self._connection.execute("PRAGMA quick_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            self._connection.close()
            raise ValueError("postal reference-data integrity check failed")
        self._connection.execute("PRAGMA query_only = ON")

    @property
    def reference_data_version(self) -> ComponentVersion:
        return self._reference_data_version

    def validate(
        self,
        postal_code: str,
        *,
        city: str,
        country_code: str,
    ) -> PostalValidation:
        with self._lock:
            rows = self._connection.execute(
                """SELECT place_name FROM postal_record
                   WHERE country_code = ? AND normalized_postal_code = ?
                   ORDER BY normalized_place_name, place_name""",
                (country_code.upper(), normalize_postal_code(postal_code)),
            ).fetchall()
        return _postal_validation(
            postal_code,
            city=city,
            country_code=country_code,
            matched_places=tuple(row[0] for row in rows),
            reference_data_version=self.reference_data_version,
        )

    def close(self) -> None:
        with self._lock:
            self._connection.close()


def _postal_validation(
    postal_code: str,
    *,
    city: str,
    country_code: str,
    matched_places: tuple[str, ...],
    reference_data_version: ComponentVersion,
) -> PostalValidation:
    normalized_city = normalize_location(city)
    status: PostalValidationStatus
    if not matched_places:
        status = "unresolved"
    elif any(normalize_location(place) == normalized_city for place in matched_places):
        status = "resolved"
    else:
        status = "mismatch"
    return PostalValidation(
        status=status,
        postal_code=postal_code,
        city=city,
        country_code=country_code.upper(),
        matched_places=tuple(dict.fromkeys(matched_places)),
        reference_data_version=reference_data_version,
    )


def build_postal_index(
    *,
    source_path: Path,
    source_url: str,
    snapshot_date: str,
    output_index: Path,
    output_manifest: Path,
) -> dict[str, object]:
    parsed_snapshot_date = date.fromisoformat(snapshot_date)
    if parsed_snapshot_date.isoformat() != snapshot_date:
        raise ValueError("snapshot_date must use YYYY-MM-DD")
    if output_index.exists() or output_manifest.exists():
        raise ValueError("postal output already exists")
    source_sha256 = _sha256(source_path)
    reference_data_version = f"geonames-postal-{snapshot_date}-{source_sha256[:12]}"
    output_index.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(output_index) as connection:
            connection.execute("PRAGMA temp_store = FILE")
            connection.execute(
                """CREATE TABLE postal_record (
                    country_code TEXT NOT NULL,
                    postal_code TEXT NOT NULL,
                    normalized_postal_code TEXT NOT NULL,
                    place_name TEXT NOT NULL,
                    normalized_place_name TEXT NOT NULL,
                    PRIMARY KEY (country_code, normalized_postal_code, normalized_place_name)
                ) WITHOUT ROWID"""
            )
            with source_path.open("r", encoding="utf-8", newline="") as source:
                for line_number, raw_line in enumerate(source, 1):
                    line = raw_line.rstrip("\r\n")
                    if not line or line.startswith("#"):
                        continue
                    columns = line.split("\t")
                    if len(columns) < 3:
                        raise ValueError(f"invalid postal source row: {line_number}")
                    country_code, postal_code, place_name = columns[:3]
                    if (
                        len(country_code) != 2
                        or not country_code.isalpha()
                        or not postal_code.strip()
                    ):
                        raise ValueError(f"invalid postal source row: {line_number}")
                    if not place_name.strip():
                        continue
                    record = (
                        country_code.upper(),
                        postal_code,
                        normalize_postal_code(postal_code),
                        place_name,
                        normalize_location(place_name),
                    )
                    connection.execute(
                        """INSERT INTO postal_record VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(country_code, normalized_postal_code, normalized_place_name)
                        DO UPDATE SET postal_code = excluded.postal_code,
                                      place_name = excluded.place_name
                        WHERE (excluded.postal_code, excluded.place_name)
                              < (postal_record.postal_code, postal_record.place_name)""",
                        record,
                    )
            records = connection.execute("SELECT count(*) FROM postal_record").fetchone()[0]
            if not records:
                raise ValueError("postal source contains no records")
            connection.execute(
                "CREATE INDEX postal_lookup ON postal_record(country_code, normalized_postal_code)"
            )
    except Exception:
        output_index.unlink(missing_ok=True)
        raise
    manifest: dict[str, object] = {
        "manifest_schema_version": 1,
        "reference_data_version": reference_data_version,
        "snapshot_date": snapshot_date,
        "artifact": {
            "filename": output_index.name,
            "sha256": _sha256(output_index),
            "size_bytes": output_index.stat().st_size,
        },
        "source": {
            "dataset": "GeoNames postal codes",
            "url": source_url,
            "sha256": source_sha256,
        },
        "license": {
            "name": "CC BY 4.0",
            "url": "https://creativecommons.org/licenses/by/4.0/",
        },
        "records": records,
    }
    output_manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
