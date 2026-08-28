from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
SKOS = "{http://www.w3.org/2004/02/skos/core#}"
SKOSXL = "{http://www.w3.org/2008/05/skos-xl#}"
ISOTHES = "{http://purl.org/iso25964/skos-thes#}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def build(source: Path, output: Path, *, expected_checksum: str, source_version: str, source_url: str) -> None:
    raw = source.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_checksum:
        raise SystemExit(f"input checksum mismatch: expected {expected_checksum}, got {actual}")
    aliases = _read_rdf_zip(source) if zipfile.is_zipfile(source) else _read_csv(source)
    aliases.sort(key=lambda item: (item["language"], item["canonical_id"], item["alias"].casefold()))
    encoded = json.dumps(aliases, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    manifest = {
        "build_version": "esco-index-v2", "source_version": source_version,
        "source_url": source_url, "license_url": "https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/european-union-public-licence",
        "input_checksum": actual, "output_checksum": hashlib.sha256(encoded).hexdigest(),
        "languages": ["en", "pl"], "alias_count": len(aliases),
        "language_alias_counts": {language: sum(item["language"] == language for item in aliases) for language in ("en", "pl")},
        "filtering_rules": ["skill-concepts-only", "exclude-obsolete", "languages=en,pl", "pref-and-alternative-labels", "non-empty-aliases", "exact-normalized-token-boundaries"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"manifest": manifest, "aliases": aliases}, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def _read_csv(source: Path) -> list[dict[str, str]]:
    aliases = []
    with source.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["language"] in {"en", "pl"} and row["alias"].strip():
                aliases.append({key: row[key].strip() for key in ("alias", "canonical_id", "display_label", "language")})
    return aliases


def _read_rdf_zip(source: Path) -> list[dict[str, str]]:
    aliases: list[dict[str, str]] = []
    with zipfile.ZipFile(source) as archive:
        names = [name for name in archive.namelist() if name.endswith(".rdf")]
        if len(names) != 1:
            raise SystemExit("official ESCO archive must contain exactly one RDF export")
        with archive.open(names[0]) as handle:
            for _, concept in ET.iterparse(handle, events=("end",)):
                if concept.tag != f"{SKOS}Concept":
                    continue
                uri = concept.attrib.get(f"{RDF}about", "")
                if "/skill/" not in uri or concept.findtext(f"{ISOTHES}status") == "obsolete":
                    concept.clear(); continue
                preferred = {node.attrib.get(XML_LANG): (node.text or "").strip() for node in concept.findall(f"{SKOS}prefLabel") if node.attrib.get(XML_LANG) in {"en", "pl"}}
                display = preferred.get("en") or preferred.get("pl")
                if not display:
                    concept.clear(); continue
                labels = [(node.attrib.get(XML_LANG), (node.text or "").strip()) for node in concept.findall(f"{SKOS}prefLabel") + concept.findall(f"{SKOS}altLabel")]
                labels += [(node.attrib.get(XML_LANG), (node.text or "").strip()) for node in concept.findall(f".//{SKOSXL}literalForm")]
                seen: set[tuple[str, str]] = set()
                for language, alias in labels:
                    key = (language or "", alias.casefold())
                    if language not in {"en", "pl"} or not alias or key in seen:
                        continue
                    seen.add(key); aliases.append({"alias": alias, "canonical_id": uri, "display_label": display, "language": language})
                concept.clear()
    return aliases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path); parser.add_argument("output", type=Path)
    parser.add_argument("--expected-checksum", required=True); parser.add_argument("--source-version", required=True)
    parser.add_argument("--source-url", required=True)
    args = parser.parse_args(); build(args.source, args.output, expected_checksum=args.expected_checksum, source_version=args.source_version, source_url=args.source_url)


if __name__ == "__main__":
    main()
