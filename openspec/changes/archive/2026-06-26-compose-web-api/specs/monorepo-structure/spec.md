## MODIFIED Requirements

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
