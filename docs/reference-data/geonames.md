# GeoNames reference data

The analyzer resolves countries and localities with an offline SQLite index
built from GeoNames `cities500`. An unresolved place is unknown, not invalid.
Analysis never downloads reference data.

## Sources and license

- `https://download.geonames.org/export/dump/cities500.zip`
- `https://download.geonames.org/export/dump/countryInfo.txt`
- `https://download.geonames.org/export/dump/alternateNamesV2.zip`

GeoNames is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The generated manifest records attribution, source URLs, hashes, build tools,
filtering rules, and record counts.

## Build and validate

Keep inputs and generated artifacts under ignored `data/`. Build with
`cv-location-index build` and validate the result with
`cv-location-index validate`; run `--help` for the required paths and snapshot
date. The runtime pair is:

```text
locations.sqlite3
locations.manifest.json
```

Set `CV_VALIDATOR_REFERENCE_DATA_DIR` to the directory containing that pair.
Compose mounts it read-only at `/app/reference-data`. Outside Compose, point
`CV_VALIDATOR_LOCATION_INDEX_PATH` and
`CV_VALIDATOR_LOCATION_MANIFEST_PATH` directly at the two files.

The repository does not currently distribute the large generated index. For a
fresh clone to work for every developer, publish the compressed pair as a
versioned repository release asset, track its URL and SHA-256 in a small lock
file, and add a setup command that downloads and verifies it into ignored
`data/`. Keep this download in setup only, never in CV analysis.

Refresh the snapshot manually in a new dated directory. Validate all hashes,
SQLite integrity, resolver behavior, and tests before changing the promoted
version. Never overwrite an approved snapshot in place.
