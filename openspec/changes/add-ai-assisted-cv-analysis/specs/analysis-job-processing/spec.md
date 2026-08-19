## Purpose

Defines durable job processing across configurable workers. Jobs do not share candidate context.

## ADDED Requirements

### Requirement: Durable job lifecycle
The system SHALL store each background job. It SHALL expose the job as `pending`, `running`, `completed`, `failed`, or `insufficient_evidence`.

#### Scenario: Job accepted
- **WHEN** the system accepts an analysis or research job
- **THEN** the job survives an API or worker restart

#### Scenario: Job reaches a terminal state
- **WHEN** a job completes, fails, or lacks evidence
- **THEN** the system stores its terminal state and result or error

### Requirement: Configurable worker concurrency
The system SHALL accept any queue length and limit concurrent work through configuration.

#### Scenario: Queue exceeds worker capacity
- **WHEN** pending jobs exceed the concurrency limit
- **THEN** extra jobs wait for a worker slot

#### Scenario: Worker count changes
- **WHEN** the operator changes worker capacity
- **THEN** capacity changes without a change to job or report behavior

### Requirement: Document analysis priority
The scheduler SHALL give document-analysis jobs priority over research jobs.

#### Scenario: Document and research jobs are pending
- **WHEN** a worker asks for the next job
- **THEN** it claims a document-analysis job before a research job

### Requirement: Exclusive and recoverable job ownership
Only one worker MUST own an active job lease. Another worker can claim the job after its lease expires.

#### Scenario: Two workers request work concurrently
- **WHEN** two workers try to claim the same job
- **THEN** exactly one worker gets the job

#### Scenario: Worker stops before completion
- **WHEN** the worker stops renewing its lease
- **THEN** the system allows a bounded retry after lease expiry

### Requirement: Idempotent job completion
A retry or duplicate completion MUST NOT add duplicate findings or category results.

#### Scenario: Completion is delivered twice
- **WHEN** the system receives the same completion twice
- **THEN** the report contains one result for that job

### Requirement: Fresh context per job
Each job SHALL use only its stored input, versioned instructions, and required analysis data. It MUST NOT inherit another job's conversation or candidate data.

#### Scenario: Worker processes consecutive candidates
- **WHEN** a worker finishes one candidate job and claims another
- **THEN** the second request contains no context from the first candidate
