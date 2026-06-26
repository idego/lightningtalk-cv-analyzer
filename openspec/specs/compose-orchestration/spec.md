# compose-orchestration Specification

## Purpose
TBD - created by archiving change compose-web-api. Update Purpose after archive.
## Requirements
### Requirement: Two-service compose runtime
The root compose configuration SHALL run `web` and `api` services together, with `web` as the only host-published service.

#### Scenario: Full stack startup
- **WHEN** `docker compose up --build` is executed
- **THEN** both `web` and `api` services start
- **AND** only `web` publishes a host port

#### Scenario: API remains internal
- **WHEN** compose services are running
- **THEN** `api` is reachable from `web` on the internal network
- **AND** `api` is not directly exposed on a host port

### Requirement: Persistent service storage
Compose SHALL persist backend audit SQLite and web auth SQLite in named volumes.

#### Scenario: Volumes mounted
- **WHEN** services are inspected
- **THEN** `api` uses a named volume for `CV_VALIDATOR_DB_PATH`
- **AND** `web` uses a named volume for Better Auth SQLite path

### Requirement: Compose test profile preserved
The backend `test` profile SHALL remain runnable from root compose.

#### Scenario: Profiled test run
- **WHEN** `docker compose --profile test run --rm test` is executed
- **THEN** backend tests run successfully from `apps/api`

### Requirement: Deployment and env documentation
Project docs SHALL describe env setup and reverse-proxy deployment pattern for a subdomain-hosted web entrypoint.

#### Scenario: Deployment notes available
- **WHEN** README and root `.env.example` are reviewed
- **THEN** they describe compose startup, required env vars, and TLS termination at external reverse proxy (not Vercel)

