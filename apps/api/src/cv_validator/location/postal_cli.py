from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from cv_validator.location.postal import build_postal_index


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cv-postal-index",
        description="Build the offline GeoNames postal-code SQLite index.",
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument("--output-index", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        manifest = build_postal_index(
            source_path=arguments.source,
            source_url=arguments.source_url,
            snapshot_date=arguments.snapshot_date,
            output_index=arguments.output_index,
            output_manifest=arguments.output_manifest,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(
        f"built {arguments.output_index} "
        f"({manifest['reference_data_version']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
