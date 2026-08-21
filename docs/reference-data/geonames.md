# GeoNames location index

The CV Analyzer resolves country and locality names against a versioned,
offline SQLite index. The application never downloads reference data while it
analyzes a CV.

The index is deliberately bounded. It uses GeoNames `cities500`, so a missing
place is **unresolved**, not nonexistent or invalid. V1 resolves countries and
localities only. It stores an `admin1` code for locality context but does not
resolve region names.

## Sources and license

Use these three official inputs:

- `https://download.geonames.org/export/dump/cities500.zip`
- `https://download.geonames.org/export/dump/countryInfo.txt`
- `https://download.geonames.org/export/dump/alternateNamesV2.zip`

GeoNames data is licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The generated
manifest records the attribution, source URLs, input hashes, transformations,
tool versions, record counts, and the built-index hash. GeoNames provides the
data without a warranty of accuracy, timeliness, or completeness.

The builder keeps canonical names, ordinary current alternate names, preferred
names, short names, and ISO2/ISO3 country codes. It removes historic,
colloquial, temporal, postal, aviation, link, Wikidata, and other unsupported
technical aliases. Alternate names are retained only when their GeoNames ID is
present in the selected country or `cities500` records.

## Controlled build

Download the inputs manually into an ignored directory. Do not commit source
archives, the full SQLite index, or its manifest until the team has chosen a
release and distribution process.

From `apps/api`, run:

```bash
cv-location-index build \
  --cities500 ../../data/geonames-build/2026-08-21/cities500.zip \
  --cities500-url https://download.geonames.org/export/dump/cities500.zip \
  --country-info ../../data/geonames-build/2026-08-21/countryInfo.txt \
  --country-info-url https://download.geonames.org/export/dump/countryInfo.txt \
  --alternate-names ../../data/geonames-build/2026-08-21/alternateNamesV2.zip \
  --alternate-names-url https://download.geonames.org/export/dump/alternateNamesV2.zip \
  --snapshot-date 2026-08-21 \
  --output-index ../../data/geonames-build/2026-08-21/locations.sqlite3 \
  --output-manifest ../../data/geonames-build/2026-08-21/locations.manifest.json
```

Use the date on which the source files were downloaded and reviewed. The
builder does not infer it from an HTTP header or archive metadata.

Validate both the generated artifact and the original inputs:

```bash
cv-location-index validate \
  --index ../../data/geonames-build/2026-08-21/locations.sqlite3 \
  --manifest ../../data/geonames-build/2026-08-21/locations.manifest.json \
  --cities500 ../../data/geonames-build/2026-08-21/cities500.zip \
  --country-info ../../data/geonames-build/2026-08-21/countryInfo.txt \
  --alternate-names ../../data/geonames-build/2026-08-21/alternateNamesV2.zip
```

The validator checks the JSON schema, every recorded SHA-256, SQLite identity
and integrity, the exact table and index allowlist, foreign keys, embedded
source metadata, and record counts. Runtime resolution opens the approved
SQLite file in immutable read-only mode.

## Runtime configuration

The base stack deliberately starts without GeoNames reference data. In that
mode location resolution is disabled: explicit location candidates remain
unresolved observations and cannot become a claimed-location fact or scoring
signal. The application does not fall back to the legacy gazetteer.

For an approved snapshot, prepare one versioned host directory containing
exactly the promoted pair under these runtime names:

```text
/absolute/operator/path/geonames-2026-08-21-f45689909bd1/
├── locations.sqlite3
└── locations.manifest.json
```

Start Compose with the optional overlay and an explicit absolute host path:

```bash
CV_VALIDATOR_REFERENCE_DATA_DIR=/absolute/operator/path/geonames-2026-08-21-f45689909bd1 \
  docker compose \
  -f docker-compose.yml \
  -f docker-compose.reference-data.yml \
  up --build
```

The overlay refuses an omitted host directory, does not create a missing host
path, mounts the directory read-only, and configures these container paths:

- `CV_VALIDATOR_LOCATION_INDEX_PATH=/app/reference-data/locations.sqlite3`
- `CV_VALIDATOR_LOCATION_MANIFEST_PATH=/app/reference-data/locations.manifest.json`

Outside Compose the same two variables may point directly to the approved
files. Both unset disables the resolver. Exactly one set, an empty value, or an
invalid/mismatched pair is a startup configuration error. A valid pair is
opened once as an app-scoped, immutable read-only resolver, shared across
single and batch requests, and closed during application shutdown. API and
audit payloads expose only the reference-data component name and version, never
the host filesystem paths.

## Quarterly refresh

Prepare a refresh once per quarter, or earlier only for a documented defect.
The update is not automatic.

1. Download all three official inputs into a new dated ignored directory.
2. Build into a new versioned directory. The builder has no overwrite mode and
   refuses an existing index or manifest; never modify an approved snapshot in
   place.
3. Validate the index against all three input files.
4. Compare the new manifest with the previously approved manifest. Review
   source hashes, builder and SQLite versions, filtering policy, total records,
   retained aliases, filtered aliases, and ambiguous normalized keys.
5. Run the location resolver tests and the full backend test suite.
6. Record the artifact size, build time, peak memory, and any material count
   changes in the review or pull request.
7. Have another developer approve the manifest and test results before the
   configured reference-data version changes.

The builder uses SQLite `DELETE` journal mode for its private scratch database,
fsyncs staged files, and publishes each output with atomic create-if-absent
semantics. It never overwrites a target created by another process. If normal
publication fails between the two outputs, it removes only files published by
that build. Two filesystem paths cannot be made crash-atomic as one operation,
so approval and promotion apply only to a complete pair that has passed
validation in its new versioned directory.

A rebuild from byte-identical inputs with the same Python and SQLite toolchain
must produce a byte-identical SQLite file. Across different SQLite versions,
compare the manifest and resolver behavior rather than requiring identical
database bytes.
