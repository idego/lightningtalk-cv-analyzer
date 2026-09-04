from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from cv_validator.location.index import (
    LocationIndexBuildError,
    SourceSpec,
    build_location_index,
)
from cv_validator.location.validation import (
    LocationIndexValidationError,
    validate_location_index,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _create_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "build":
            manifest = build_location_index(
                cities500=SourceSpec(arguments.cities500, arguments.cities500_url),
                country_info=SourceSpec(
                    arguments.country_info,
                    arguments.country_info_url,
                ),
                alternate_names=SourceSpec(
                    arguments.alternate_names,
                    arguments.alternate_names_url,
                ),
                snapshot_date=arguments.snapshot_date,
                output_index=arguments.output_index,
                output_manifest=arguments.output_manifest,
            )
            print(
                f"built {arguments.output_index} "
                f"({manifest['reference_data_version']})"
            )
            return 0

        source_values = (
            arguments.cities500,
            arguments.country_info,
            arguments.alternate_names,
        )
        if any(source_values) and not all(source_values):
            raise LocationIndexValidationError(
                "validation source paths must be supplied together"
            )
        source_paths = None
        if all(source_values):
            source_paths = {
                "cities500": arguments.cities500,
                "country_info": arguments.country_info,
                "alternate_names_v2": arguments.alternate_names,
            }
        manifest = validate_location_index(
            arguments.index,
            arguments.manifest,
            source_paths=source_paths,
        )
        print(
            f"valid {arguments.index} "
            f"({manifest['reference_data_version']})"
        )
        return 0
    except (
        LocationIndexBuildError,
        LocationIndexValidationError,
        OSError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cv-location-index",
        description="Build and validate the offline GeoNames SQLite index.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--cities500", type=Path, required=True)
    build.add_argument("--cities500-url", required=True)
    build.add_argument("--country-info", type=Path, required=True)
    build.add_argument("--country-info-url", required=True)
    build.add_argument("--alternate-names", type=Path, required=True)
    build.add_argument("--alternate-names-url", required=True)
    build.add_argument("--snapshot-date", required=True)
    build.add_argument("--output-index", type=Path, required=True)
    build.add_argument("--output-manifest", type=Path, required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--index", type=Path, required=True)
    validate.add_argument("--manifest", type=Path, required=True)
    validate.add_argument("--cities500", type=Path)
    validate.add_argument("--country-info", type=Path)
    validate.add_argument("--alternate-names", type=Path)
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
