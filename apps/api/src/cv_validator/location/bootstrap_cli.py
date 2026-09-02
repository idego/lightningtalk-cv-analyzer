from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from cv_validator.location.bootstrap import (
    DEFAULT_SOURCE_URLS,
    ReferenceDataBootstrapError,
    bootstrap_reference_data,
)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    urls = {
        role: getattr(arguments, role)
        for role in DEFAULT_SOURCE_URLS
    }
    if not arguments.allow_insecure_urls:
        invalid = [url for url in urls.values() if urlparse(url).scheme != "https"]
        if invalid:
            parser.error("GeoNames source URLs must use HTTPS")
    try:
        release = bootstrap_reference_data(
            arguments.target,
            snapshot_version=arguments.snapshot_version,
            source_urls=urls,
        )
    except ReferenceDataBootstrapError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"GeoNames reference data ready: {release}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cv-geonames-bootstrap",
        description="Prepare versioned GeoNames indexes in a persistent volume.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path(os.getenv("GEONAMES_TARGET", "/reference-data")),
    )
    parser.add_argument(
        "--snapshot-version",
        default=os.getenv("GEONAMES_SNAPSHOT_VERSION"),
        required=os.getenv("GEONAMES_SNAPSHOT_VERSION") is None,
    )
    for role, default_url in DEFAULT_SOURCE_URLS.items():
        parser.add_argument(
            f"--{role.replace('_', '-')}-url",
            dest=role,
            default=os.getenv(f"GEONAMES_{role.upper()}_URL", default_url),
        )
    parser.add_argument("--allow-insecure-urls", action="store_true", help=argparse.SUPPRESS)
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
