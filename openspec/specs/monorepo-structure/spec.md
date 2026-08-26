# monorepo-structure Specification

## Purpose
Defines the two-service monorepo layout and the build, runtime, test, and
documentation wiring that connects the web and API applications.
## Requirements
### Requirement: Two-service repository layout
The repository SHALL organize each deployable service under `apps/<service>`: the Python backend at `apps/api/` and the frontend at `apps/web/`. Shared root-level files (OpenSpec, agent docs, workflow skills) SHALL remain at the repository root.

#### Scenario: Backend located under apps/api
- **WHEN** the repository is inspected after the change
- **THEN** the backend package, tests, fixtures, `weights.yaml`, `pyproject.toml`, and `Dockerfile` reside under `apps/api/`
- **AND** no backend source remains at the repository root

#### Scenario: Frontend service present
- **WHEN** the repository is inspected after the change
- **THEN** the frontend service resides under `apps/web/`

### Requirement: Backend behavior preserved after relocation
Relocating the backend MUST NOT change its behavior, scoring, weights, or HTTP contract. The existing test suite SHALL pass from the new location.

#### Scenario: Test suite passes from new location
- **WHEN** the backend test suite is run from `apps/api` (`cd apps/api && PYTHONPATH=src pytest`)
- **THEN** all existing tests pass with no source changes other than path/build wiring

#### Scenario: API contract unchanged
- **WHEN** the relocated backend is started
- **THEN** `GET /health`, `POST /analyze`, and `POST /analyze/batch` behave identically to before the move

### Requirement: Build and run wiring resolves from new locations
Backend build, test, and container wiring SHALL reference the new `apps/api` paths so the service builds and runs without relying on the old root layout.

#### Scenario: Container builds from apps/api context
- **WHEN** the backend image is built with `apps/api/` as the build context
- **THEN** the image builds successfully and the API starts

#### Scenario: Compose test profile works from new layout
- **WHEN** `docker compose --profile test run --rm test` is executed
- **THEN** the backend tests run and pass from the relocated layout

#### Scenario: Web service runs from apps/web in compose
- **WHEN** root compose is started
- **THEN** `apps/web` builds and runs as the public entrypoint
- **AND** backend traffic from browser flows through `web` proxy routes rather than direct host-to-api access

### Requirement: Documentation and tooling reference the new paths
Project docs and tooling SHALL be updated so no instructions point at the old root paths.

#### Scenario: No stale root-path references remain
- **WHEN** `AGENTS.md`, `CLAUDE.md`, `README.md`, the workflow skills, and `openspec/` references are inspected
- **THEN** commands and file maps reference `apps/api` (and `apps/web`) locations, not the former root paths
