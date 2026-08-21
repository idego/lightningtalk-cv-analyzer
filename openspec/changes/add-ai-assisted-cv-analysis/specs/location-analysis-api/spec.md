## MODIFIED Requirements

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

## ADDED Requirements

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
