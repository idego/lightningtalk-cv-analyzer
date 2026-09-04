# reference-data Specification

## Purpose
Defines how offline GeoNames locality and postal-code indexes are built,
versioned, and mounted so runtime CV analysis never downloads reference data.

## Requirements

### Requirement: One-shot index build
The checked-in `config/geonames.lock` SHALL pin the accepted snapshot version, and preflight SHALL reject a configured `GEONAMES_SNAPSHOT_VERSION` that disagrees with it. The `geonames-init` Compose service SHALL download the official GeoNames dumps (overridable with `GEONAMES_*_URL`), build locality and postal index/manifest pairs under `GEONAMES_SNAPSHOT_VERSION` in the `geonames_data` volume, validate them, and promote the release to `current`. `api` mounts the volume read-only and requires the resolver via `CV_VALIDATOR_REQUIRE_LOCATION_RESOLVER=true`, reporting readiness in `GET /health`.

#### Scenario: Snapshot already built
- **WHEN** the volume already holds the configured snapshot version
- **THEN** `geonames-init` skips download and exits successfully

#### Scenario: Resolver missing
- **WHEN** the indexes are absent or invalid
- **THEN** `/health` reports `ready: false` and the compose healthcheck fails

### Requirement: Operator-provided snapshot
With `REFERENCE_DATA_MODE=operator`, the `docker-compose.reference-data.yml` overlay SHALL disable the download and bind-mount `CV_VALIDATOR_REFERENCE_DATA_DIR` read-only; the directory MUST contain both index/manifest pairs.

#### Scenario: Directory unset
- **WHEN** operator mode is used without `CV_VALIDATOR_REFERENCE_DATA_DIR`
- **THEN** compose refuses to start with an explicit error
