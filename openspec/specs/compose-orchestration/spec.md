# compose-orchestration Specification

## Purpose
Defines the containerized web/API runtime, internal service networking,
persistent storage, test profile, and deployment configuration.
## Requirements
### Requirement: Compose runtime services
The root compose configuration SHALL run the long-lived `web` and `api` services plus two one-shot init services: `geonames-init`, which builds the offline reference-data indexes `api` depends on, and `feedback-init`, which seeds feedback access in the web auth database before `web` starts. `web` SHALL be the only host-published service in `docker-compose.yml`, published as `${WEB_PORT:-3000}:3000`.

#### Scenario: Full stack startup
- **WHEN** `make dev` or `make deploy` runs the stack
- **THEN** `geonames-init` and `feedback-init` complete successfully before `api` and `web` are considered started
- **AND** only `web` publishes a host port from `docker-compose.yml`
- **AND** `feedback-init` reads its owner configuration from its image without mounting the source repository at runtime

#### Scenario: API remains internal in production
- **WHEN** compose services are running from `docker-compose.yml` alone
- **THEN** `api` is reachable from `web` on the internal network
- **AND** `api` is not directly exposed on a host port, because `/internal/feedback` relies on the web layer for authorization

#### Scenario: Local Swagger access
- **WHEN** `make dev` starts the stack
- **THEN** the `docker-compose.dev.yml` overlay additionally publishes `api` on `127.0.0.1:${API_DEV_PORT:-8001}` for `/docs`
- **AND** `make deploy` never includes that overlay

### Requirement: Shared configuration between services
Every environment variable that two services must agree on SHALL be read from the same `${VAR:-default}` expression in every service that uses it. In particular `feedback-init` and `web` SHALL resolve `BETTER_AUTH_DB_PATH` identically, and `.env.example` SHALL carry the same defaults as `docker-compose.yml` and the Makefile.

#### Scenario: Operator overrides the auth database path
- **WHEN** `BETTER_AUTH_DB_PATH` is set in the env file
- **THEN** `feedback-init` seeds owners into the same file `web` reads

#### Scenario: Example env file is used verbatim
- **WHEN** an operator copies `.env.example` without edits
- **THEN** the resulting ports and database paths match the compose and Makefile defaults

### Requirement: Persistent service storage
Compose SHALL persist backend audit SQLite and web auth SQLite in named volumes.

#### Scenario: Volumes mounted
- **WHEN** services are inspected
- **THEN** `api` uses a named volume for `CV_VALIDATOR_DB_PATH`
- **AND** `web` and `feedback-init` share the named volume for the Better Auth SQLite path
- **AND** `geonames-init` owns a named volume that `api` mounts read-only

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
- **AND** `.env.example` lists every variable an operator may set, including the optional dev-only `API_DEV_PORT`

### Requirement: Runtime containment
Long-lived `web` and `api` runtime containers and the feedback initializer SHALL execute as non-root users. Compose SHALL define bounded CPU, memory, and PID limits for the long-lived services and GeoNames initializer, with documented environment overrides. `make dev`, `make dev-down`, and `make deploy` SHALL consistently use `COMPOSE_PROJECT_NAME` so named-volume identity does not change between paths.

#### Scenario: Production compose is inspected
- **WHEN** an operator renders the production Compose config
- **THEN** web/API services have explicit resource bounds and the deployed project uses the configured project name


### Requirement: Existing-volume non-root upgrade
A bounded, one-shot permissions initializer SHALL prepare the existing API and
web-auth named volumes before API or feedback initialization starts, and SHALL
make existing GeoNames release artifacts readable by the non-root API user. Only this
initializer may run as root for application-volume ownership changes; long-lived
services remain non-root. An upgrade MUST NOT require deleting existing volumes
or making SQLite data world-writable.
