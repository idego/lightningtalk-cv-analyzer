## RENAMED Requirements

- FROM: `### Requirement: Two-service compose runtime`
- TO: `### Requirement: Multi-service compose runtime`

## MODIFIED Requirements

### Requirement: Multi-service compose runtime
The root Compose file SHALL run `web`, `api`, queue services, and scalable workers. Only `web` SHALL publish a host port.

#### Scenario: Full stack startup
- **WHEN** the operator runs the documented Compose command
- **THEN** web, API, queue, and configured workers start
- **AND** only `web` publishes a host port

#### Scenario: API remains internal
- **WHEN** Compose services are running
- **THEN** API, queue, and workers use the internal network
- **AND** they do not publish host ports

## ADDED Requirements

### Requirement: Configurable worker scaling
Deployment settings SHALL change worker capacity without changes to application code or job contracts.

#### Scenario: Worker capacity configured
- **WHEN** the operator starts the stack with a worker replica count
- **THEN** that number of workers can claim jobs from the shared queue
