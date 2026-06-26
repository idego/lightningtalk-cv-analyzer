# location-analysis-api Specification

## Purpose
TBD - created by archiving change cv-location-consistency. Update Purpose after archive.
## Requirements
### Requirement: Single-CV analysis endpoint
The system SHALL expose an HTTP endpoint that accepts a single CV upload and returns the consistency report as JSON.

#### Scenario: Successful single analysis
- **WHEN** a supported CV is uploaded to the single-analysis endpoint
- **THEN** the system returns the JSON report (score, band, findings, summary)

#### Scenario: Rejected upload
- **WHEN** an unsupported or non-extractable file is uploaded
- **THEN** the system returns an error response without producing a report

### Requirement: Batch analysis endpoint
The system SHALL expose an endpoint that accepts multiple CVs and returns a report per CV, isolating per-file failures.

#### Scenario: Mixed batch
- **WHEN** a batch contains both valid and invalid files
- **THEN** the system returns reports for the valid files and per-file errors for the invalid ones without failing the whole batch

### Requirement: Minimal-retention persistence with ruleset versioning
The system SHALL persist the report findings, score, and the ruleset/weights version that produced them, and MUST store national IDs as presence/type only, never the raw value. Retention SHALL be governed by a configurable window.

#### Scenario: Report persisted with version
- **WHEN** a report is produced
- **THEN** the system stores the findings, score, and ruleset/weights version

#### Scenario: National ID not retained
- **WHEN** a report involving a detected national ID is persisted
- **THEN** only presence/type is stored, never the raw value

### Requirement: Immutable audit trail
The system SHALL record an immutable audit entry for every analysis containing the input hash, ruleset/weights version, and the output, sufficient to reproduce and defend the result.

#### Scenario: Audit entry written
- **WHEN** an analysis completes
- **THEN** the system writes an audit entry with input hash, ruleset version, and output that cannot be altered after the fact

