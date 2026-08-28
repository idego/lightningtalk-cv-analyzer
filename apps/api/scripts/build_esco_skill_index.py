from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def build(source: Path, output: Path, *, expected_checksum: str, source_version: str, source_url: str) -> None:
    raw = source.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_checksum:
        raise SystemExit(f"input checksum mismatch: expected {expected_checksum}, got {actual}")
    aliases = []
    with source.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["language"] not in {"en", "pl"} or not row["alias"].strip():
                continue
            aliases.append({key: row[key].strip() for key in ("alias", "canonical_id", "display_label", "language")})
    aliases.sort(key=lambda item: (item["language"], item["canonical_id"], item["alias"].casefold()))
    encoded = json.dumps(aliases, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    manifest = {
        "build_version": "esco-index-v1", "source_version": source_version,
        "source_url": source_url, "license_url": "https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/european-union-public-licence",
        "input_checksum": actual, "output_checksum": hashlib.sha256(encoded).hexdigest(),
        "languages": ["en", "pl"], "alias_count": len(aliases),
        "language_alias_counts": {language: sum(item["language"] == language for item in aliases) for language in ("en", "pl")},
        "filtering_rules": ["languages=en,pl", "non-empty-aliases", "exact-normalized-token-boundaries"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"manifest": manifest, "aliases": aliases}, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path); parser.add_argument("output", type=Path)
    parser.add_argument("--expected-checksum", required=True); parser.add_argument("--source-version", required=True)
    parser.add_argument("--source-url", required=True)
    args = parser.parse_args(); build(args.source, args.output, expected_checksum=args.expected_checksum, source_version=args.source_version, source_url=args.source_url)


if __name__ == "__main__":
    main()
