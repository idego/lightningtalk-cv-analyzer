## ADDED Requirements

### Requirement: Persistent asynchronous analysis lifecycle
The API SHALL store single and batch analyses. It SHALL return a stable ID and state for each file so clients can get results after submission.

#### Scenario: Batch accepted
- **WHEN** the API accepts a supported batch
- **THEN** it returns one stable analysis ID per file
- **AND** each file enters `pending` or `running` on its own

#### Scenario: Mixed batch processing
- **WHEN** one file fails ingestion or AI analysis
- **THEN** that file shows its error and other files continue

### Requirement: Progressive report retrieval
The API SHALL return the current base report and research state without waiting for all research jobs.

#### Scenario: Base report ready while research is pending
- **WHEN** document analysis is complete and research is still running
- **THEN** the API returns the base report and pending research states

#### Scenario: Research result completes
- **WHEN** a research job reaches a terminal state
- **THEN** the next report response includes its result or error

### Requirement: Optional research activation
The API SHALL let an authenticated user request any subset of company, education/certification, and LinkedIn research for a completed base analysis.

#### Scenario: Research category requested
- **WHEN** a user requests an eligible category
- **THEN** the system stores the request and returns its current state without creating a duplicate job
