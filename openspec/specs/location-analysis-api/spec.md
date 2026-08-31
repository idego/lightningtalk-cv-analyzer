# location-analysis-api Specification

## Purpose
Defines the authenticated analysis and persistence API, including ownership,
retention, deterministic report serialization, and safe AI failure behavior.

## Requirements

### Requirement: Single-CV analysis endpoint
The system SHALL keep the existing synchronous single-CV upload endpoint. A successful response SHALL include the deterministic report, structured facts, AI document findings, authority/source labels, a complete flag checklist, and a stable analysis ID used by later research actions.

#### Scenario: Successful single analysis
- **WHEN** the API accepts one supported CV with enough text
- **THEN** it returns the completed base report and stable analysis ID in the same request

#### Scenario: Rejected upload
- **WHEN** an unsupported, non-extractable, or insufficient-text file is uploaded
- **THEN** the system returns an error response without producing a report

### Requirement: Batch analysis endpoint
The system SHALL keep the existing synchronous batch endpoint. It SHALL enforce a configured V1 file-count and request-size limit before analysis and SHALL isolate per-file failures within an accepted batch.

#### Scenario: Mixed batch
- **WHEN** an accepted batch contains successful and failed file analyses
- **THEN** the system returns one completed result or isolated error per file without failing the whole batch

#### Scenario: Batch exceeds the V1 limit
- **WHEN** a submitted batch exceeds the configured maximum file count or request size
- **THEN** the API rejects it with a clear limit message before starting analysis

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

### Requirement: Structured JSON candidate result
The API SHALL preserve the existing deterministic JSON fields and SHALL add one nested `deterministic` object. That object SHALL contain available candidates, facts, observations, scoring signals, authority, exact evidence, extractor versions, and applicable reference-data versions from `DeterministicAnalysisResult`. The API SHALL also return each candidate's structured contact, education, and employment facts, complete flag checklist, relevant model versions, and completed research results as JSON when those later sections are available. The HTML report SHALL use this same report model.

#### Scenario: Report returned as JSON
- **WHEN** an analysis or research action succeeds
- **THEN** the response contains every available fact, flag, reason, evidence item, authority/source label, configuration version, and research category result

#### Scenario: Slice 2 deterministic result returned
- **WHEN** Slice 2 returns a deterministic-only analysis
- **THEN** every pre-existing top-level JSON field keeps its name and meaning
- **AND** the response adds one nested `deterministic` object with the new typed deterministic results and versions

#### Scenario: Deterministic section absent from an older stored report
- **WHEN** the API reads a compatible report created before the additive deterministic section existed
- **THEN** it does not require a breaking rewrite of the legacy top-level fields

### Requirement: Redacted deterministic persistence identity
The API persistence boundary SHALL identify a deterministic analysis with a hash of redacted canonical text. It MUST NOT pass raw file bytes or raw national-ID values into deterministic report persistence for fingerprinting.

#### Scenario: Deterministic report persisted
- **WHEN** the API stores a completed deterministic report
- **THEN** it stores the redacted canonical-text hash with the report and audit data
- **AND** no raw national-ID value enters persistence

### Requirement: Synchronous research actions
The API SHALL let an authenticated user request company, education/certification, or LinkedIn research for a stored analysis. Each endpoint SHALL return the completed category result or a bounded error in the same request.

#### Scenario: Eligible category requested
- **WHEN** the user requests research for an existing analysis
- **THEN** the API validates the stored research candidates, performs that category, stores the completed result, and returns it

#### Scenario: Research request times out
- **WHEN** the category exceeds its configured request timeout
- **THEN** the API returns a retryable error and does not store a partial category result as complete

### Requirement: Capability health status
The API SHALL expose a non-sensitive health response that reports whether the
database, approved GeoNames resolver, AI document analysis, company research,
education research, and LinkedIn research are ready. Overall readiness SHALL be
false when any capability required by the full analyzer is unavailable. The
response MUST NOT expose secrets or host filesystem paths.

#### Scenario: Full analyzer is ready
- **WHEN** every required dependency is configured and initialized
- **THEN** health reports overall `ready` and identifies the active GeoNames reference version

#### Scenario: Required capability is missing
- **WHEN** a required capability is unavailable
- **THEN** health reports overall `degraded` with the affected capability and a safe recovery hint

### Requirement: Configurable report language
Each analysis request SHALL accept one supported AI report language independently
from the UI language. The selected report language SHALL be included in the
versioned AI request and stored audit metadata without changing deterministic
facts or scoring.

#### Scenario: Polish report requested from English UI
- **WHEN** the recruiter selects English UI and Polish AI report language
- **THEN** controls remain English and newly generated AI explanations use Polish

### Requirement: Complete owner-scoped retention and reopen state
Every retention purge path SHALL identify the concrete expired analysis IDs and delete the complete SQLite candidate-analysis graph together with process-local retry context, lock, and in-flight registry state. Persist-triggered and retention-setting-triggered purge SHALL use the same cleanup contract. Reading an owned stored analysis SHALL hydrate completed company, education, and LinkedIn discovery results from their separate tables without returning access-token hashes, capability tokens, secrets, or another owner's data. Legacy LinkedIn confirmation and comparison rows MAY remain stored for backward-compatible cleanup but MUST NOT be exposed through the current API.

#### Scenario: Persist triggers retention cleanup
- **WHEN** persisting a new analysis purges an expired analysis
- **THEN** the purge returns the expired analysis ID and removes its database rows and process-local retry state

#### Scenario: Retention setting becomes shorter
- **WHEN** a retention update makes an existing analysis expired
- **THEN** the same complete database and process-local cleanup occurs before the update returns

#### Scenario: Recruiter reopens a completed researched analysis
- **WHEN** the owner reads a stored analysis after refresh or reopen
- **THEN** completed company, education, and LinkedIn results are hydrated from their category tables
- **AND** an absent or wrong owner token receives no analysis or research data

### Requirement: Return bounded document understanding in analysis reports

Every newly completed analysis response SHALL include a top-level `document_understanding` value conforming exactly to `document-understanding-v1`, or `null` only when understanding is unavailable or the stored report predates the capability. The API SHALL apply the same sanitizer used by persistence and SHALL NOT reconstruct a missing understanding payload from AI facts during report reads.

#### Scenario: New analysis completes
- **WHEN** the API returns a newly analyzed supported CV
- **THEN** `document_understanding` is a sanitized V1 object or a truthful unavailable state

#### Scenario: Legacy analysis is loaded
- **WHEN** a stored report predates the understanding contract
- **THEN** the API returns `document_understanding: null` and preserves all legacy report fields

#### Scenario: Stored understanding is invalid
- **WHEN** a stored understanding value fails its closed schema, bounds, cross-reference, or defense-in-depth privacy validation
- **THEN** the API suppresses that object, records only a safe error code, and preserves otherwise valid report surfaces
