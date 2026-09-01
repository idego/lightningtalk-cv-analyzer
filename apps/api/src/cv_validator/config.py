from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from cv_validator.location import LocationIndexValidationError, SQLiteLocationResolver


class LocationConfigurationError(ValueError):
    pass


def load_location_resolver(*, required: bool = False) -> SQLiteLocationResolver | None:
    index_path = os.environ.get("CV_VALIDATOR_LOCATION_INDEX_PATH")
    manifest_path = os.environ.get("CV_VALIDATOR_LOCATION_MANIFEST_PATH")
    if index_path is None and manifest_path is None:
        if required:
            raise LocationConfigurationError(
                "GeoNames reference data is required: set "
                "CV_VALIDATOR_LOCATION_INDEX_PATH and "
                "CV_VALIDATOR_LOCATION_MANIFEST_PATH"
            )
        return None
    if index_path is None or manifest_path is None:
        raise LocationConfigurationError(
            "CV_VALIDATOR_LOCATION_INDEX_PATH and "
            "CV_VALIDATOR_LOCATION_MANIFEST_PATH must be set together"
        )
    if not index_path.strip() or not manifest_path.strip():
        raise LocationConfigurationError(
            "configured location reference-data paths must not be empty"
        )
    try:
        return SQLiteLocationResolver(Path(index_path), Path(manifest_path))
    except (OSError, LocationIndexValidationError, sqlite3.Error) as exc:
        raise LocationConfigurationError(
            "configured location reference-data pair is invalid"
        ) from exc
