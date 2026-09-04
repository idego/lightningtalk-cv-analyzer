# GeoNames reference data

The analyzer uses two offline SQLite indexes: countries/localities from
`cities500`, and postal-code-to-city relationships. Runtime CV analysis never
calls GeoNames or sends CV fields to it.

GeoNames data is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Generated manifests record attribution, source URLs, hashes, build tools,
filtering rules, and record counts.

## Normal Compose startup

The base stack owns the complete lifecycle:

1. `geonames-init` downloads the four official HTTPS sources.
2. It builds and validates both index/manifest pairs in a temporary directory.
3. It atomically promotes the complete release behind `current`.
4. Only then may `api` start; the API mounts the named volume read-only.

The persistent volume is scoped by the Compose project name. A valid matching
release is verified and reused without any network request on later deploys.
An interrupted download or build never replaces `current`; the next start
removes stale staging data and retries. A filesystem lock prevents two jobs
from writing the same volume concurrently.

Configure the release identity in the deployment environment:

```dotenv
GEONAMES_SNAPSHOT_VERSION=2026-08-21
```

The source URLs default to:

- `https://download.geonames.org/export/dump/cities500.zip`
- `https://download.geonames.org/export/dump/countryInfo.txt`
- `https://download.geonames.org/export/dump/alternateNamesV2.zip`
- `https://download.geonames.org/export/zip/allCountries.zip`

Override the corresponding `GEONAMES_*_URL` variables only for an approved
HTTPS mirror. GeoNames URLs are mutable, so a successful release is immutable
inside the volume and records the exact downloaded source hashes. Refreshing is
always explicit: choose a new `GEONAMES_SNAPSHOT_VERSION` and deploy again.

Allow at least 3 GiB free before the first build or a refresh. This covers
compressed sources, extracted inputs, temporary SQLite files, and completed
indexes. After promotion, temporary inputs are removed and only the current and
immediately previous releases are retained.

Useful checks:

```bash
docker compose ps
docker compose logs geonames-init
docker compose exec -T api python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
```

The health request runs inside the API container because the normal deployment
does not publish the API port on the host.

## Offline or operator-provided snapshot

For a host without outbound access, build both pairs separately using
`cv-location-index build` and `cv-postal-index`, then place these four files in
one approved directory:

```text
locations.sqlite3
locations.manifest.json
postal-codes.sqlite3
postal-codes.manifest.json
```

Set `CV_VALIDATOR_REFERENCE_DATA_DIR` in the environment file and run:

```bash
REFERENCE_DATA_MODE=operator make dev
REFERENCE_DATA_MODE=operator make deploy
```

This applies `docker-compose.reference-data.yml`: the initialization command is
bypassed and the approved directory replaces the named reference-data mount.
The API receives it read-only. Preflight verifies the locality pair against
`config/geonames.lock` and requires the postal pair; runtime validates both.

## Recovery and rollback

- If initialization fails, inspect `docker compose logs geonames-init`, fix
  network, disk, or source configuration, and run the same deploy again.
- Do not create or edit files inside the named volume manually. The initializer
  ignores incomplete staging directories and preserves the last current release
  until a replacement validates.
- To retry a corrupt release with the same configured version, restart the
  stack; validation removes and rebuilds that release without promoting partial
  files.
- To roll back the application, use the previous reviewed Git revision. Keep
  the GeoNames volume intact. If the older application expects flat paths, use
  operator mode with a compatible approved directory.

Generated artifacts and downloaded source data remain outside Git. Never add
them to the repository.
