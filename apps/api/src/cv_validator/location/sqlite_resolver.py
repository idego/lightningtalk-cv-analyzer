from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

from cv_validator.domain import ComponentVersion
from cv_validator.errors import LocationAnalysisError
from cv_validator.location.resolver import (
    LocationMatch,
    LocationResolution,
    MatchKind,
    ResolutionLevel,
    _match_sort_key,
    _resolution_from_matches,
    normalize_location,
)
from cv_validator.location.validation import (
    LocationIndexValidationError,
    open_pinned_read_only_connection,
    validate_location_index,
)


class SQLiteLocationResolver:
    def __init__(self, index_path: Path, manifest_path: Path) -> None:
        self._index_path = index_path.resolve()
        self._lock = threading.RLock()
        self._connection: sqlite3.Connection | None = None
        self._artifact_fd: int | None = None
        artifact_fd: int | None = None
        connection: sqlite3.Connection | None = None
        try:
            artifact_fd = os.open(self._index_path, os.O_RDONLY | os.O_CLOEXEC)
            pinned_before = _file_identity(os.fstat(artifact_fd))
            if _file_identity(self._index_path.stat()) != pinned_before:
                raise LocationIndexValidationError(
                    "index path changed while opening the artifact"
                )
            connection = open_pinned_read_only_connection(artifact_fd)
            manifest = validate_location_index(
                self._index_path,
                manifest_path,
                _connection=connection,
                _artifact_fd=artifact_fd,
            )
            if _file_identity(self._index_path.stat()) != pinned_before:
                raise LocationIndexValidationError(
                    "index path changed during artifact validation"
                )
            self._reference_data_version = ComponentVersion(
                "geonames-sqlite",
                manifest["reference_data_version"],
            )
            self._connection = connection
            self._artifact_fd = artifact_fd
        except BaseException:
            if connection is not None:
                connection.close()
            if artifact_fd is not None:
                os.close(artifact_fd)
            raise

    @property
    def reference_data_version(self) -> ComponentVersion:
        return self._reference_data_version

    def resolve(
        self,
        value: str,
        *,
        level: ResolutionLevel,
    ) -> LocationResolution:
        with self._lock:
            if self._connection is None:
                raise LocationAnalysisError("location resolver is closed")
            normalized_value = normalize_location(value)
            try:
                if not normalized_value or level is ResolutionLevel.REGION:
                    rows = ()
                else:
                    rows = self._connection.execute(
                        """SELECT
                            r.record_id, r.level, r.canonical_name, n.display_name,
                            n.match_kind, r.country_code, r.country_name,
                            r.region_code, r.region_name
                        FROM location_name AS n
                        JOIN location_record AS r ON r.record_id = n.record_id
                        WHERE n.normalized_name = ? AND r.level = ?""",
                        (normalized_value, level.value),
                    ).fetchall()
            except sqlite3.Error as exc:
                raise LocationAnalysisError(
                    "location reference-data query failed"
                ) from exc
        matches = tuple(
            sorted(
                (
                    LocationMatch(
                        record_id=row[0],
                        level=ResolutionLevel(row[1]),
                        canonical_name=row[2],
                        matched_name=row[3],
                        match_kind=MatchKind(row[4]),
                        country_code=row[5],
                        country_name=row[6],
                        region_code=row[7],
                        region_name=row[8],
                    )
                    for row in rows
                ),
                key=_match_sort_key,
            )
        )
        return _resolution_from_matches(
            input_value=value,
            normalized_value=normalized_value,
            matches=matches,
            reference_data_version=self._reference_data_version,
            level=level,
        )

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
            if self._artifact_fd is not None:
                os.close(self._artifact_fd)
                self._artifact_fd = None

    def __enter__(self) -> SQLiteLocationResolver:
        with self._lock:
            if self._connection is None:
                raise LocationAnalysisError("location resolver is closed")
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _file_identity(file_stat: os.stat_result) -> tuple[int, int, int, int]:
    return (
        file_stat.st_dev,
        file_stat.st_ino,
        file_stat.st_size,
        file_stat.st_mtime_ns,
    )
