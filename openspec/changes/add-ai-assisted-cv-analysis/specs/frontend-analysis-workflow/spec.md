## ADDED Requirements

### Requirement: Synchronous AI-assisted analysis experience
The analyze UI SHALL keep the current upload flow. It SHALL show a loading state while the existing API processes the submitted file or batch and SHALL render results after the response completes.

#### Scenario: Single CV analysis completes
- **WHEN** the API returns the AI-assisted report
- **THEN** the UI replaces the loading state with that report

#### Scenario: Batch contains file errors
- **WHEN** the batch response contains successful reports and failed files
- **THEN** the UI shows each returned report and each isolated error

### Requirement: Finding hierarchy
The UI SHALL group findings as `requires attention`, `worth knowing`, and `remaining signals`. It SHALL collapse `remaining signals` by default but keep all findings available.

#### Scenario: Low-importance findings exist
- **WHEN** a report has low-importance findings
- **THEN** the UI keeps them in the collapsed `remaining signals` section

### Requirement: Complete candidate flag checklist
The UI SHALL show a per-candidate checklist containing every detected location, LinkedIn, company, education, deterministic, and AI-assisted flag with a short reason.

#### Scenario: Candidate has findings from several sources
- **WHEN** document analysis, fixed rules, or research return flags
- **THEN** the report lists all flags and identifies their source and reason

### Requirement: Readable HTML report
The UI SHALL render each candidate result as a readable HTML report backed by the same report data returned by the API.

#### Scenario: Candidate report is ready
- **WHEN** the recruiter opens a completed analysis
- **THEN** the UI shows structured facts, the flag checklist, evidence, and available research results

### Requirement: User-controlled research actions
The UI SHALL provide separate actions for company, education/certification, and LinkedIn research after the base report is ready. It SHALL show a request-level loading state and keep other report content visible.

#### Scenario: User starts one research category
- **WHEN** the user starts one category
- **THEN** only that action becomes busy
- **AND** the base report and other completed categories remain visible

#### Scenario: Research succeeds
- **WHEN** the API returns a completed category result
- **THEN** the UI adds or replaces that category without a full page reload

#### Scenario: Research fails
- **WHEN** the request returns an error
- **THEN** the UI shows the category error, keeps the report, and lets the user retry
