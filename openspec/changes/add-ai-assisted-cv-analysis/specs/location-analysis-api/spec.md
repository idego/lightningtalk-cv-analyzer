## MODIFIED Requirements

### Requirement: Synchronous analysis endpoints
The API SHALL keep the existing synchronous single and batch endpoints. A successful response SHALL include the deterministic report, structured facts, AI document findings, a complete flag checklist, and a stable analysis ID used by later research actions.

#### Scenario: Single analysis succeeds
- **WHEN** the API accepts one supported CV with enough text
- **THEN** it returns the completed base report and analysis ID in the same request

#### Scenario: Batch analysis succeeds
- **WHEN** the API accepts a supported batch within the configured V1 limit
- **THEN** it processes each file through the same pipeline and returns one completed result or isolated error per file

#### Scenario: Batch exceeds the V1 limit
- **WHEN** a submitted batch exceeds the configured maximum file count or request size
- **THEN** the API rejects it with a clear limit message before starting analysis

### Requirement: Structured JSON candidate result
The API SHALL return each candidate's structured contact, education, and employment facts, complete flag checklist, evidence, and completed research results as JSON. The HTML report SHALL use this same report model.

#### Scenario: Report returned as JSON
- **WHEN** an analysis or research action succeeds
- **THEN** the response contains every available fact, flag, reason, evidence item, configuration version, and research category result

## ADDED Requirements

### Requirement: Synchronous research actions
The API SHALL let an authenticated user request company, education/certification, or LinkedIn research for a stored analysis. Each endpoint SHALL return the completed category result or a bounded error in the same request.

#### Scenario: Eligible category requested
- **WHEN** the user requests research for an existing analysis
- **THEN** the API validates the stored research candidates, performs that category, stores the completed result, and returns it

#### Scenario: Research request times out
- **WHEN** the category exceeds its configured request timeout
- **THEN** the API returns a retryable error and does not store a partial category result as complete
